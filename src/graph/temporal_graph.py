import time
import math
from typing import Dict, List, Optional, Tuple
from ..core.models import ProcessEvent, DependencyEdge
from ..core.database import EventStore
from ..core.config import config

class TemporalDependencyGraph:
    def __init__(self, db: Optional[EventStore] = None):
        self.db = db
        # Adjacency map: source_process -> {target_process -> DependencyEdge}
        self.edges: Dict[str, Dict[str, DependencyEdge]] = {}
        # Recent process events buffer for sliding window dependency detection
        self.recent_events: List[ProcessEvent] = []
        self._load_from_db()

    def _load_from_db(self):
        if not self.db:
            return
        persisted_edges = self.db.get_all_dependency_edges()
        for edge in persisted_edges:
            if edge.source_process not in self.edges:
                self.edges[edge.source_process] = {}
            self.edges[edge.source_process][edge.target_process] = edge

    def calculate_recency(self, edge: DependencyEdge, current_time: Optional[float] = None) -> float:
        """Exponential decay: Recency = exp(-dt / halflife)"""
        now = current_time or time.time()
        dt = max(0.0, now - edge.recency_timestamp)
        return math.exp(-dt / config.temporal_decay_halflife_sec)

    def calculate_edge_weight(self, edge: DependencyEdge, current_time: Optional[float] = None) -> float:
        """EdgeWeight = Frequency * SuccessRate * Recency"""
        recency = self.calculate_recency(edge, current_time)
        return edge.frequency * edge.success_rate * recency

    def update_probabilities_for_source(self, source: str, current_time: Optional[float] = None):
        """Compute transition probability across all outbound edges for a given source process."""
        if source not in self.edges or not self.edges[source]:
            return
        
        target_edges = self.edges[source]
        total_weight = sum(self.calculate_edge_weight(e, current_time) for e in target_edges.values())
        
        if total_weight > 0:
            for target, edge in target_edges.items():
                weight = self.calculate_edge_weight(edge, current_time)
                edge.prediction_probability = weight / total_weight
                # Form-B Confidence: Frequency dampening requires repeated patterns (>= 3 for high confidence)
                recency = self.calculate_recency(edge, current_time)
                freq_factor = min(1.0, max(0.0, (edge.frequency - 1) / 3.0))
                edge.confidence = min(1.0, edge.prediction_probability * edge.success_rate * recency * freq_factor)
        else:
            for edge in target_edges.values():
                edge.prediction_probability = 1.0 / len(target_edges)
                edge.confidence = 0.0

    def add_process_event(self, event: ProcessEvent, current_time: Optional[float] = None):
        now = current_time or event.timestamp
        
        # 1. Clean up events older than max_transition_window_sec
        cutoff = now - config.max_transition_window_sec
        self.recent_events = [e for e in self.recent_events if e.timestamp >= cutoff]

        # 2. Link to the immediate predecessor process in the sliding window
        if self.recent_events:
            # Find the closest preceding distinct process
            pred_event = None
            for p in reversed(self.recent_events):
                if p.process_name != event.process_name:
                    pred_event = p
                    break

            if pred_event:
                source = pred_event.process_name
                target = event.process_name
                delay = now - pred_event.timestamp

                if delay <= config.max_transition_window_sec:
                    if source not in self.edges:
                        self.edges[source] = {}

                    if target not in self.edges[source]:
                        edge = DependencyEdge(
                            source_process=source,
                            target_process=target,
                            frequency=1,
                            total_delay_seconds=delay,
                            average_delay_seconds=delay,
                            success_count=1,
                            failure_count=0,
                            success_rate=1.0,
                            recency_timestamp=now
                        )
                        self.edges[source][target] = edge
                    else:
                        edge = self.edges[source][target]
                        edge.update_transition(delay, now)

                    self.update_probabilities_for_source(source, now)
                    
                    if self.db:
                        self.db.upsert_dependency_edge(self.edges[source][target])

        # 3. Add current event to sliding window
        self.recent_events.append(event)
        
        # 4. Prune if graph exceeds capacity
        self.prune_obsolete_edges()

    def get_outbound_edges(self, source: str) -> List[DependencyEdge]:
        if source not in self.edges:
            return []
        return list(self.edges[source].values())

    def prune_obsolete_edges(self):
        total_edges = sum(len(targets) for targets in self.edges.values())
        if total_edges <= config.max_graph_edges:
            return

        now = time.time()
        all_edge_refs = []
        for source, targets in self.edges.items():
            for target, edge in targets.items():
                weight = self.calculate_edge_weight(edge, now)
                all_edge_refs.append((source, target, weight))

        # Sort by weight ascending and drop lowest
        all_edge_refs.sort(key=lambda x: x[2])
        edges_to_remove = total_edges - config.max_graph_edges
        for i in range(edges_to_remove):
            s, t, _ = all_edge_refs[i]
            del self.edges[s][t]
            if not self.edges[s]:
                del self.edges[s]
