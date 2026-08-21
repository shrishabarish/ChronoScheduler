import unittest
import time
import subprocess
import os
import sys

# Ensure src is on path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.core.models import ProcessEvent
from src.core.database import EventStore
from src.telemetry.psutil_monitor import PsutilProcessMonitor

class TestPhase1CoreTelemetryStorage(unittest.TestCase):
    def setUp(self):
        self.db = EventStore(":memory:")
        self.monitor = PsutilProcessMonitor(polling_interval=0.02)

    def tearDown(self):
        self.monitor.stop()

    def test_1_normalized_event_creation(self):
        """Verify ProcessEvent model structure and serialization."""
        event = ProcessEvent(
            pid=1234,
            ppid=1,
            process_name="code",
            executable="/usr/bin/code",
            cpu_affinity=[0, 1],
            memory_rss_bytes=1024 * 1024 * 50
        )
        self.assertEqual(event.pid, 1234)
        self.assertEqual(event.process_name, "code")
        self.assertEqual(event.cpu_affinity, [0, 1])
        d = event.to_dict()
        self.assertEqual(d["executable"], "/usr/bin/code")

    def test_2_event_persistence_and_retrieval(self):
        """Verify M2 SQLite storage and retrieval."""
        event = ProcessEvent(
            pid=5678,
            ppid=100,
            process_name="python3",
            executable="/usr/bin/python3",
            cpu_affinity=[1],
            memory_rss_bytes=2048000
        )
        event_id = self.db.record_process_event(event)
        self.assertIsNotNone(event_id)
        self.assertGreater(event_id, 0)

        recent = self.db.get_recent_process_events(limit=10)
        self.assertEqual(len(recent), 1)
        retrieved = recent[0]
        self.assertEqual(retrieved.pid, 5678)
        self.assertEqual(retrieved.process_name, "python3")
        self.assertEqual(retrieved.cpu_affinity, [1])

    def test_3_process_launch_detection(self):
        """Verify M1 detects live process launch."""
        detected_events = []

        def callback(event: ProcessEvent):
            detected_events.append(event)

        self.monitor.start(callback)
        time.sleep(0.1)  # Allow monitor snapshot

        # Spawn a short-lived test subprocess
        proc = subprocess.Popen(["sleep", "0.3"])
        proc.wait()

        time.sleep(0.2)  # Allow monitor to catch it
        self.monitor.stop()

        # Check if sleep was detected
        sleep_events = [e for e in detected_events if "sleep" in e.process_name]
        self.assertGreaterEqual(len(sleep_events), 1, "Failed to detect sleep process launch")
        self.assertEqual(sleep_events[0].process_name, "sleep")

    def test_4_continuous_execution_and_resilience(self):
        """Verify monitor runs continuously and handles multiple spawns without crashing."""
        detected = []
        self.monitor.start(lambda e: detected.append(e))
        time.sleep(0.05)

        for _ in range(3):
            p = subprocess.Popen(["echo", "chronosched_test"])
            p.wait()
            time.sleep(0.05)

        time.sleep(0.1)
        self.monitor.stop()
        self.assertTrue(self.monitor._running is False)

    def test_5_duplicate_handling(self):
        """Verify that known PIDs are not continuously re-emitted."""
        detected = []
        self.monitor.start(lambda e: detected.append(e))
        time.sleep(0.1)
        initial_count = len(detected)
        time.sleep(0.1)
        # Without new processes, count should not explode
        self.assertEqual(len(detected), initial_count)

if __name__ == "__main__":
    unittest.main()
