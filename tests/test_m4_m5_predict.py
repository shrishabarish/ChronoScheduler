import unittest
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.core.models import ProcessEvent
from src.core.database import EventStore
from src.graph.temporal_graph import TemporalDependencyGraph
from src.engine.prediction import PredictionEngine
from src.engine.confidence import ConfidenceEngine

class TestPhase3PredictionConfidence(unittest.TestCase):
    def setUp(self):
        self.db = EventStore(":memory:")
        self.graph = TemporalDependencyGraph(db=self.db)
        self.predictor = PredictionEngine(graph=self.graph, db=self.db)
        self.confidence_engine = ConfidenceEngine(threshold=0.60)

    def _train_sequence(self, source: str, target: str, count: int, delay: float = 1.0):
        t = 1000.0
        for i in range(count):
            t_src = t + (i * 10.0)
            t_tgt = t_src + delay
            self.graph.add_process_event(ProcessEvent(pid=100+i, ppid=1, process_name=source, executable=source, timestamp=t_src), current_time=t_src)
            self.graph.add_process_event(ProcessEvent(pid=200+i, ppid=100+i, process_name=target, executable=target, timestamp=t_tgt), current_time=t_tgt)

    def test_1_prediction_accuracy_on_known_pattern(self):
        # Train: code -> pylance 5 times
        self._train_sequence("code", "pylance", 5, delay=2.0)

        # Trigger event: user starts code
        trigger_event = ProcessEvent(pid=999, ppid=1, process_name="code", executable="code", timestamp=2000.0)
        prediction = self.predictor.predict(trigger_event, current_time=2000.0)

        self.assertIsNotNone(prediction)
        self.assertEqual(prediction.source_process, "code")
        self.assertEqual(prediction.predicted_process, "pylance")
        self.assertGreater(prediction.probability, 0.8)
        self.assertGreater(prediction.confidence, 0.6)

    def test_2_confidence_gating(self):
        # Train only 1 time -> low frequency -> low confidence
        self._train_sequence("editor", "spellcheck", 1, delay=1.0)

        trigger_event = ProcessEvent(pid=888, ppid=1, process_name="editor", executable="editor", timestamp=3000.0)
        prediction = self.predictor.predict(trigger_event, current_time=3000.0)

        self.assertIsNotNone(prediction)
        passed, reason = self.confidence_engine.evaluate_gating(prediction)
        self.assertFalse(passed)
        self.assertIn("Rejected", reason)

    def test_3_adaptive_confidence_feedback(self):
        self._train_sequence("vscode", "pylance", 3, delay=1.5)
        edge = self.graph.edges["vscode"]["pylance"]
        initial_conf = edge.confidence

        # Success feedback increases confidence
        self.confidence_engine.update_confidence_feedback(edge, success=True)
        self.assertGreaterEqual(edge.confidence, initial_conf)

        # Failure feedback penalizes confidence
        prev_conf = edge.confidence
        self.confidence_engine.update_confidence_feedback(edge, success=False)
        self.assertLess(edge.confidence, prev_conf)

if __name__ == "__main__":
    unittest.main()
