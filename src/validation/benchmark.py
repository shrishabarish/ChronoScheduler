import time
from typing import Dict, Any, List
from ..core.models import ProcessEvent
from ..graph.temporal_graph import TemporalDependencyGraph
from ..engine.prediction import PredictionEngine
from ..engine.confidence import ConfidenceEngine
from ..validation.traces import generate_validation_traces, WORKFLOW_CHAINS

class BenchmarkRunner:
    def __init__(self, train_split: float = 0.60):
        self.train_split = train_split
        self.graph = TemporalDependencyGraph()
        self.predictor = PredictionEngine(self.graph)
        self.confidence_engine = ConfidenceEngine(threshold=0.30)

    def run_benchmark(self, num_sessions: int = 80, seed: int = 42) -> Dict[str, Any]:
        all_events = generate_validation_traces(num_sessions=num_sessions, seed=seed)
        split_idx = int(len(all_events) * self.train_split)
        
        train_events = all_events[:split_idx]
        val_events = all_events[split_idx:]

        # 1. Warm up graph with Training Split
        for evt in train_events:
            self.graph.add_process_event(evt, current_time=evt.timestamp)

        # 2. Extract ground truth transitions from workflow chains
        valid_transitions = {}
        for chain in WORKFLOW_CHAINS:
            for k in range(len(chain) - 1):
                src = chain[k][0]
                tgt = chain[k + 1][0]
                valid_transitions[src] = tgt

        true_positives = 0
        false_positives = 0
        false_negatives = 0
        true_negatives = 0
        latencies_ms: List[float] = []

        # 3. Evaluate on Validation Split
        for i in range(len(val_events) - 1):
            current_event = val_events[i]
            actual_next_event = val_events[i + 1]
            
            # Feed current event to graph
            self.graph.add_process_event(current_event, current_time=current_event.timestamp)

            # Measure prediction inference latency
            start_t = time.perf_counter()
            prediction = self.predictor.predict(current_event, current_time=current_event.timestamp)
            latency_ms = (time.perf_counter() - start_t) * 1000.0
            latencies_ms.append(latency_ms)

            # Determine ground truth for this transition
            delay = actual_next_event.timestamp - current_event.timestamp
            has_actual_dependent_launch = (
                delay <= 6.0 and
                current_event.process_name in valid_transitions and
                actual_next_event.process_name == valid_transitions[current_event.process_name]
            )

            if prediction is not None:
                passed, _ = self.confidence_engine.evaluate_gating(prediction)
                if passed:
                    if has_actual_dependent_launch and prediction.predicted_process == actual_next_event.process_name:
                        true_positives += 1
                    else:
                        false_positives += 1
                else:
                    if has_actual_dependent_launch:
                        false_negatives += 1
                    else:
                        true_negatives += 1
            else:
                if has_actual_dependent_launch:
                    false_negatives += 1
                else:
                    true_negatives += 1

        total_predictions = true_positives + false_positives
        total_actual_positives = true_positives + false_negatives
        total_evals = true_positives + false_positives + true_negatives + false_negatives

        accuracy = (true_positives + true_negatives) / total_evals if total_evals > 0 else 0.0
        precision = true_positives / total_predictions if total_predictions > 0 else 0.0
        recall = true_positives / total_actual_positives if total_actual_positives > 0 else 0.0
        
        actual_negatives = true_negatives + false_positives
        fpr = false_positives / actual_negatives if actual_negatives > 0 else 0.0
        fnr = false_negatives / total_actual_positives if total_actual_positives > 0 else 0.0
        
        avg_latency_ms = sum(latencies_ms) / len(latencies_ms) if latencies_ms else 0.0

        return {
            "total_events_evaluated": len(val_events),
            "accuracy": round(accuracy, 4),
            "accuracy_percent": round(accuracy * 100, 2),
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "false_positive_rate": round(fpr, 4),
            "false_negative_rate": round(fnr, 4),
            "average_latency_ms": round(avg_latency_ms, 3),
            "target_met": (accuracy >= 0.80)
        }
