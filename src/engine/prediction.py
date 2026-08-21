import time
from typing import Optional, List
from ..core.models import ProcessEvent, PredictionResult
from ..graph.temporal_graph import TemporalDependencyGraph
from ..core.database import EventStore

class PredictionEngine:
    def __init__(self, graph: TemporalDependencyGraph, db: Optional[EventStore] = None):
        self.graph = graph
        self.db = db

    def predict(self, event: ProcessEvent, current_time: Optional[float] = None) -> Optional[PredictionResult]:
        now = current_time or event.timestamp
        source = event.process_name
        
        edges = self.graph.get_outbound_edges(source)
        if not edges:
            return None

        # Re-compute probabilities with current recency decay
        self.graph.update_probabilities_for_source(source, now)

        # Select candidate with highest prediction probability & confidence
        best_edge = max(edges, key=lambda e: e.prediction_probability * e.confidence)
        
        if best_edge.prediction_probability <= 0:
            return None

        result = PredictionResult(
            source_process=source,
            predicted_process=best_edge.target_process,
            probability=best_edge.prediction_probability,
            confidence=best_edge.confidence,
            expected_delay_seconds=best_edge.average_delay_seconds,
            timestamp=now
        )

        if self.db:
            self.db.record_prediction(result)

        return result
