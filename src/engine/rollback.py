import time
import threading
from typing import Dict, Optional, Callable, List
from ..core.models import SchedulerAction, FeedbackEvent, DependencyEdge
from ..core.database import EventStore
from ..graph.temporal_graph import TemporalDependencyGraph
from ..engine.scheduler import LinuxSchedulerActionEngine
from ..engine.confidence import ConfidenceEngine
from ..core.config import config

class PendingVerification:
    def __init__(
        self,
        action: SchedulerAction,
        source_process: str,
        predicted_process: str,
        edge: Optional[DependencyEdge],
        timeout_sec: float = config.prediction_timeout_sec
    ):
        self.action = action
        self.source_process = source_process
        self.predicted_process = predicted_process
        self.edge = edge
        self.start_time = time.time()
        self.timeout_sec = timeout_sec
        self.resolved = False

class RollbackAndFeedbackEngine:
    def __init__(
        self,
        scheduler_engine: LinuxSchedulerActionEngine,
        graph: TemporalDependencyGraph,
        confidence_engine: ConfidenceEngine,
        db: Optional[EventStore] = None
    ):
        self.scheduler = scheduler_engine
        self.graph = graph
        self.confidence_engine = confidence_engine
        self.db = db
        # Active verifications: action_id -> PendingVerification
        self.pending_actions: Dict[int, PendingVerification] = {}
        self._lock = threading.Lock()

    def register_action(
        self,
        action: SchedulerAction,
        source_process: str,
        predicted_process: str,
        edge: Optional[DependencyEdge],
        timeout_sec: float = config.prediction_timeout_sec
    ):
        with self._lock:
            pv = PendingVerification(action, source_process, predicted_process, edge, timeout_sec)
            action_key = action.action_id or id(action)
            self.pending_actions[action_key] = pv

    def on_process_launch_observed(self, actual_process_name: str, launch_time: Optional[float] = None) -> List[FeedbackEvent]:
        """
        Called whenever a new process launches in the system.
        If it matches a pending prediction, records SUCCESS and reinforces edge.
        """
        now = launch_time or time.time()
        resolved_feedbacks: List[FeedbackEvent] = []

        with self._lock:
            to_remove = []
            for action_key, pv in self.pending_actions.items():
                if pv.resolved:
                    to_remove.append(action_key)
                    continue

                if actual_process_name.lower() == pv.predicted_process.lower():
                    # SUCCESS: Impending process actually launched!
                    pv.resolved = True
                    latency_ms = (now - pv.start_time) * 1000.0
                    fb = FeedbackEvent(
                        action_id=pv.action.action_id or 0,
                        predicted_process=pv.predicted_process,
                        actual_process=actual_process_name,
                        success=True,
                        latency_observed_ms=latency_ms,
                        timestamp=now
                    )
                    
                    if pv.edge:
                        self.confidence_engine.update_confidence_feedback(pv.edge, success=True)
                        if self.db:
                            self.db.upsert_dependency_edge(pv.edge)

                    if self.db:
                        self.db.record_feedback(fb)

                    resolved_feedbacks.append(fb)
                    to_remove.append(action_key)

            for k in to_remove:
                if k in self.pending_actions:
                    del self.pending_actions[k]

        return resolved_feedbacks

    def check_timeouts_and_rollback(self, current_time: Optional[float] = None) -> List[FeedbackEvent]:
        """
        Called periodically. Any action whose timeout expired without 
        the predicted process launching triggers an immediate ROLLBACK and PENALTY.
        """
        now = current_time or time.time()
        expired_feedbacks: List[FeedbackEvent] = []

        with self._lock:
            to_remove = []
            for action_key, pv in self.pending_actions.items():
                if not pv.resolved and (now - pv.start_time) >= pv.timeout_sec:
                    # TIMEOUT: Predicted process never launched -> Rollback!
                    pv.resolved = True
                    self.scheduler.rollback_action(pv.action)
                    
                    fb = FeedbackEvent(
                        action_id=pv.action.action_id or 0,
                        predicted_process=pv.predicted_process,
                        actual_process=None,
                        success=False,
                        latency_observed_ms=pv.timeout_sec * 1000.0,
                        timestamp=now
                    )

                    if pv.edge:
                        self.confidence_engine.update_confidence_feedback(pv.edge, success=False)
                        if self.db:
                            self.db.upsert_dependency_edge(pv.edge)

                    if self.db:
                        self.db.record_feedback(fb)

                    expired_feedbacks.append(fb)
                    to_remove.append(action_key)

            for k in to_remove:
                if k in self.pending_actions:
                    del self.pending_actions[k]

        return expired_feedbacks
