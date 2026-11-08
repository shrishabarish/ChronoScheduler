import os
import time
import json
import threading
import logging
from typing import Optional, Callable, Any

logger = logging.getLogger("ChronoSched")
from .core.models import ProcessEvent, SafetyDecision, SimulationResult, SchedulerAction
from .core.config import config
from .core.database import EventStore
from .telemetry.psutil_monitor import PsutilProcessMonitor
from .graph.temporal_graph import TemporalDependencyGraph
from .engine.prediction import PredictionEngine
from .engine.confidence import ConfidenceEngine
from .engine.safety import NeuroSymbolicSafetyEngine
from .engine.digital_twin import DigitalTwinSimulator
from .engine.scheduler import LinuxSchedulerActionEngine
from .engine.rollback import RollbackAndFeedbackEngine

class ChronoSchedDaemon:
    def __init__(self, db_path: str = config.db_path, on_pipeline_step: Optional[Callable[[str, Any], None]] = None):
        self.db = EventStore(db_path)
        self.graph = TemporalDependencyGraph(db=self.db)
        self.predictor = PredictionEngine(graph=self.graph, db=self.db)
        self.confidence_engine = ConfidenceEngine(threshold=config.confidence_threshold)
        self.safety_engine = NeuroSymbolicSafetyEngine()
        self.digital_twin = DigitalTwinSimulator(db=self.db)
        self.scheduler = LinuxSchedulerActionEngine(db=self.db)
        self.rollback_engine = RollbackAndFeedbackEngine(
            scheduler_engine=self.scheduler,
            graph=self.graph,
            confidence_engine=self.confidence_engine,
            db=self.db
        )
        self.telemetry = PsutilProcessMonitor(
            polling_interval=config.polling_interval_sec,
            filter_kernel_threads=config.filter_kernel_threads
        )
        self.on_pipeline_step = on_pipeline_step
        self._running = False
        self._timeout_thread: Optional[threading.Thread] = None

    def _notify(self, step_name: str, payload: Any):
        if self.on_pipeline_step:
            try:
                self.on_pipeline_step(step_name, payload)
            except Exception:
                pass

    def handle_process_event(self, event: ProcessEvent):
        """
        The Form-B Closed Loop:
        Telemetry -> Graph -> Prediction -> Confidence -> Safety -> Digital Twin -> Scheduler -> Feedback/Rollback
        """
        now = event.timestamp

        # 1. Telemetry & Persistence
        self.db.record_process_event(event)
        self._notify("telemetry_event", event)

        # 2. Check pending verifications for feedback on actual successor launch
        resolved_feedbacks = self.rollback_engine.on_process_launch_observed(event.process_name, launch_time=now)
        for fb in resolved_feedbacks:
            self._notify("feedback_success", fb)

        # 3. Update Temporal Dependency Graph
        self.graph.add_process_event(event, current_time=now)
        self._notify("graph_updated", {"source": event.process_name})

        # 4. Probabilistic Prediction
        prediction = self.predictor.predict(event, current_time=now)
        if not prediction:
            self._notify("prediction_skipped", {"reason": "no_outbound_edges"})
            return
        self._notify("prediction_generated", prediction)

        # 5. Confidence Gating
        passed_conf, conf_reason = self.confidence_engine.evaluate_gating(prediction)
        if not passed_conf:
            self._notify("confidence_gated", {"prediction": prediction, "reason": conf_reason})
            return

        # 6. Neuro-Symbolic Safety Rules
        safety_decision = self.safety_engine.evaluate(prediction.predicted_process, prediction.confidence)
        self._notify("safety_decision", safety_decision)
        if not safety_decision.approved:
            self._notify("safety_rejected", {"reasons": safety_decision.reasons})
            return

        # 7. Digital Twin Pre-Execution Simulation
        hw_snapshot = self.safety_engine.capture_hardware_snapshot()
        sim_result = self.digital_twin.simulate(prediction.predicted_process, safety_decision, hw_snapshot)
        self._notify("digital_twin_simulation", sim_result)
        if not sim_result.approved:
            self._notify("digital_twin_rejected", {"state": sim_result.simulation_state})
            return

        # 8. Linux Scheduler Execution (sched_setaffinity / nice)
        action = self.scheduler.apply_scheduling_action(event, safety_decision, sim_result, prediction.confidence)
        if action:
            self._notify("scheduler_action_applied", action)
            # 9. Register action for verification window & rollback on timeout
            edge = self.graph.edges.get(event.process_name, {}).get(prediction.predicted_process)
            self.rollback_engine.register_action(
                action=action,
                source_process=event.process_name,
                predicted_process=prediction.predicted_process,
                edge=edge,
                timeout_sec=config.prediction_timeout_sec
            )

    def _timeout_monitor_loop(self):
        while self._running:
            expired_feedbacks = self.rollback_engine.check_timeouts_and_rollback()
            for fb in expired_feedbacks:
                self._notify("rollback_timeout_penalty", fb)
            time.sleep(0.2)

    def start(self):
        self._running = True
        self._timeout_thread = threading.Thread(target=self._timeout_monitor_loop, daemon=True)
        self._timeout_thread.start()
        self.telemetry.start(self.handle_process_event)
        print(">>> ChronoSched Closed-Loop Daemon Online")

    def stop(self):
        self._running = False
        self.telemetry.stop()
        if self._timeout_thread and self._timeout_thread.is_alive():
            self._timeout_thread.join(timeout=1.0)
        print(">>> ChronoSched Daemon Stopped")
