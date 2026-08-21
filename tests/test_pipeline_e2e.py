import unittest
import time
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.core.models import ProcessEvent
from src.daemon import ChronoSchedDaemon

class TestClosedLoopPipelineE2E(unittest.TestCase):
    def setUp(self):
        self.steps_logged = []
        def step_callback(step_name, payload):
            self.steps_logged.append((step_name, payload))

        self.daemon = ChronoSchedDaemon(db_path=":memory:", on_pipeline_step=step_callback)
        from src.core.models import HardwareSnapshot
        self.daemon.safety_engine.capture_hardware_snapshot = lambda: HardwareSnapshot(
            cpu_percent_total=15.0,
            cpu_percent_per_core=[15.0, 15.0],
            memory_percent=30.0,
            memory_available_bytes=4000000000,
            thermal_throttled=False,
            battery_saver_active=False
        )
        # Pre-train historical relationship: code -> pylance 4 times
        base_t = 1000.0
        for i in range(4):
            t_src = base_t + (i * 10.0)
            t_tgt = t_src + 2.0
            self.daemon.graph.add_process_event(ProcessEvent(pid=100+i, ppid=1, process_name="code", executable="/usr/bin/code", timestamp=t_src), current_time=t_src)
            self.daemon.graph.add_process_event(ProcessEvent(pid=200+i, ppid=100+i, process_name="pylance", executable="/usr/bin/pylance", timestamp=t_tgt), current_time=t_tgt)

    def test_full_form_b_closed_loop(self):
        my_pid = os.getpid()
        now = 2000.0

        # Step 1: User launches VSCode (represented by our active PID)
        event_code = ProcessEvent(pid=my_pid, ppid=1, process_name="code", executable="/usr/bin/code", timestamp=now)
        self.daemon.handle_process_event(event_code)

        # Check telemetry event recorded
        logged_step_names = [s[0] for s in self.steps_logged]
        self.assertIn("telemetry_event", logged_step_names)
        self.assertIn("prediction_generated", logged_step_names)
        self.assertIn("safety_decision", logged_step_names)
        self.assertIn("digital_twin_simulation", logged_step_names)
        self.assertIn("scheduler_action_applied", logged_step_names)

        # Verify active pending verification exists
        self.assertEqual(len(self.daemon.rollback_engine.pending_actions), 1)

        # Step 10: Pylance launches 1.5 seconds later
        pylance_time = now + 1.5
        event_pylance = ProcessEvent(pid=my_pid + 1, ppid=my_pid, process_name="pylance", executable="/usr/bin/pylance", timestamp=pylance_time)
        self.daemon.handle_process_event(event_pylance)

        # Verify feedback success was triggered and recorded
        updated_step_names = [s[0] for s in self.steps_logged]
        self.assertIn("feedback_success", updated_step_names)
        self.assertEqual(len(self.daemon.rollback_engine.pending_actions), 0)

        # Verify confidence was reinforced in the graph
        edge = self.daemon.graph.edges["code"]["pylance"]
        self.assertGreater(edge.confidence, 0.70)
        self.assertEqual(edge.frequency, 5)
        self.assertGreaterEqual(edge.success_count, 2)

if __name__ == "__main__":
    unittest.main()
