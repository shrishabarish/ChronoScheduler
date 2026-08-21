import unittest
import time
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.core.models import ProcessEvent
from src.core.database import EventStore
from src.graph.temporal_graph import TemporalDependencyGraph

class TestPhase2TemporalGraph(unittest.TestCase):
    def setUp(self):
        self.db = EventStore(":memory:")
        self.graph = TemporalDependencyGraph(db=self.db)

    def test_1_edge_creation_and_delay_tracking(self):
        base_time = 1000.0
        # Event 1: code (VSCode)
        e1 = ProcessEvent(pid=1001, ppid=1, process_name="code", executable="/usr/bin/code", timestamp=base_time)
        self.graph.add_process_event(e1, current_time=base_time)

        # Event 2: pylance 2.5 seconds later
        e2 = ProcessEvent(pid=1002, ppid=1001, process_name="pylance", executable="/usr/bin/pylance", timestamp=base_time + 2.5)
        self.graph.add_process_event(e2, current_time=base_time + 2.5)

        edges = self.graph.get_outbound_edges("code")
        self.assertEqual(len(edges), 1)
        edge = edges[0]
        self.assertEqual(edge.target_process, "pylance")
        self.assertEqual(edge.frequency, 1)
        self.assertAlmostEqual(edge.average_delay_seconds, 2.5, places=2)

    def test_2_multiple_transitions_and_weights(self):
        base_time = 2000.0
        # Sequence 1: code -> pylance (2.0s)
        self.graph.add_process_event(ProcessEvent(pid=1, ppid=0, process_name="code", executable="code", timestamp=base_time), current_time=base_time)
        self.graph.add_process_event(ProcessEvent(pid=2, ppid=1, process_name="pylance", executable="pylance", timestamp=base_time + 2.0), current_time=base_time + 2.0)

        # Sequence 2: code -> pylance (4.0s)
        t2 = base_time + 10.0
        self.graph.add_process_event(ProcessEvent(pid=3, ppid=0, process_name="code", executable="code", timestamp=t2), current_time=t2)
        self.graph.add_process_event(ProcessEvent(pid=4, ppid=3, process_name="pylance", executable="pylance", timestamp=t2 + 4.0), current_time=t2 + 4.0)

        # Sequence 3: code -> git (1.0s)
        t3 = base_time + 20.0
        self.graph.add_process_event(ProcessEvent(pid=5, ppid=0, process_name="code", executable="code", timestamp=t3), current_time=t3)
        self.graph.add_process_event(ProcessEvent(pid=6, ppid=5, process_name="git", executable="git", timestamp=t3 + 1.0), current_time=t3 + 1.0)

        edges = {e.target_process: e for e in self.graph.get_outbound_edges("code")}
        self.assertIn("pylance", edges)
        self.assertIn("git", edges)
        self.assertEqual(edges["pylance"].frequency, 2)
        self.assertAlmostEqual(edges["pylance"].average_delay_seconds, 3.0, places=2)
        self.assertEqual(edges["git"].frequency, 1)
        
        # Pylance was observed 2x vs git 1x, so P(pylance|code) > P(git|code)
        self.assertGreater(edges["pylance"].prediction_probability, edges["git"].prediction_probability)

    def test_3_temporal_decay(self):
        base_time = 1000.0
        self.graph.add_process_event(ProcessEvent(pid=1, ppid=0, process_name="terminal", executable="bash", timestamp=base_time), current_time=base_time)
        self.graph.add_process_event(ProcessEvent(pid=2, ppid=1, process_name="make", executable="make", timestamp=base_time + 1.0), current_time=base_time + 1.0)

        edge = self.graph.edges["terminal"]["make"]
        weight_fresh = self.graph.calculate_edge_weight(edge, current_time=base_time + 1.0)
        # 1 day later
        weight_aged = self.graph.calculate_edge_weight(edge, current_time=base_time + 1.0 + 86400.0)
        self.assertLess(weight_aged, weight_fresh)
        self.assertAlmostEqual(weight_aged / weight_fresh, 0.367879, places=3)

if __name__ == "__main__":
    unittest.main()
