import unittest
import time
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.core.models import ProcessEvent, SafetyDecision, SimulationResult, DependencyEdge
from src.core.database import EventStore
from src.graph.temporal_graph import TemporalDependencyGraph
from src.engine.confidence import ConfidenceEngine
from src.engine.scheduler import LinuxSchedulerActionEngine
from src.engine.rollback import RollbackAndFeedbackEngine

class TestPhase6And7SchedulerRollbackFeedback(unittest.TestCase):
    def setUp(self):
        self.db = EventStore(":memory:")
        self.graph = TemporalDependencyGraph(db=self.db)
        self.confidence = ConfidenceEngine()
        self.scheduler = LinuxSchedulerActionEngine(db=self.db)
        self.rollback = RollbackAndFeedbackEngine(
            scheduler_engine=self.scheduler,
            graph=self.graph,
            confidence_engine=self.confidence,
            db=self.db
        )

    def test_1_scheduler_action_execution(self):
        # Use our own current PID
        my_pid = os.getpid()
        event = ProcessEvent(pid=my_pid, ppid=1, process_name="python3", executable="python3")
        safety = SafetyDecision(
            approved=True,
            reasons=["ALL_RULES_PASSED"],
            rule_name="ALL_RULES_PASSED",
            hardware_state={},
            target_core=0,
            recommended_nice=0
        )
        sim = SimulationResult(
            approved=True,
            predicted_cpu_delta=10.0,
            predicted_memory_delta_mb=50.0,
            latency_estimate_ms=1.0,
            thermal_risk="LOW",
            simulation_state="SAFE"
        )
        action = self.scheduler.apply_scheduling_action(event, safety, sim, confidence=0.88)
        self.assertIsNotNone(action)
        self.assertTrue(action.applied)
        self.assertEqual(action.new_affinity, [0])

    def test_2_successful_prediction_reinforcement(self):
        edge = DependencyEdge(
            source_process="vscode",
            target_process="pylance",
            confidence=0.70,
            success_count=2,
            failure_count=0
        )
        self.graph.edges["vscode"] = {"pylance": edge}
        
        my_pid = os.getpid()
        event = ProcessEvent(pid=my_pid, ppid=1, process_name="vscode", executable="vscode")
        safety = SafetyDecision(approved=True, reasons=[], rule_name="PASS", hardware_state={}, target_core=0, recommended_nice=0)
        sim = SimulationResult(approved=True, predicted_cpu_delta=5, predicted_memory_delta_mb=20, latency_estimate_ms=1, thermal_risk="LOW", simulation_state="SAFE")
        
        action = self.scheduler.apply_scheduling_action(event, safety, sim, confidence=0.70)
        self.rollback.register_action(action, "vscode", "pylance", edge, timeout_sec=2.0)

        # Process actually launches within timeout
        feedbacks = self.rollback.on_process_launch_observed("pylance")
        self.assertEqual(len(feedbacks), 1)
        self.assertTrue(feedbacks[0].success)
        self.assertGreater(edge.confidence, 0.70)

    def test_3_timeout_rollback_and_penalty(self):
        edge = DependencyEdge(
            source_process="terminal",
            target_process="docker",
            confidence=0.80,
            success_count=3,
            failure_count=0
        )
        self.graph.edges["terminal"] = {"docker": edge}

        my_pid = os.getpid()
        event = ProcessEvent(pid=my_pid, ppid=1, process_name="terminal", executable="bash")
        safety = SafetyDecision(approved=True, reasons=[], rule_name="PASS", hardware_state={}, target_core=0, recommended_nice=0)
        sim = SimulationResult(approved=True, predicted_cpu_delta=5, predicted_memory_delta_mb=20, latency_estimate_ms=1, thermal_risk="LOW", simulation_state="SAFE")
        
        action = self.scheduler.apply_scheduling_action(event, safety, sim, confidence=0.80)
        self.rollback.register_action(action, "terminal", "docker", edge, timeout_sec=0.1)

        # Wait for timeout to expire
        time.sleep(0.15)
        feedbacks = self.rollback.check_timeouts_and_rollback()
        
        self.assertEqual(len(feedbacks), 1)
        self.assertFalse(feedbacks[0].success)
        self.assertTrue(action.rolled_back)
        self.assertLess(edge.confidence, 0.80)

if __name__ == "__main__":
    unittest.main()
