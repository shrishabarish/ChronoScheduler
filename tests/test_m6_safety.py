import unittest
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.core.models import HardwareSnapshot
from src.engine.safety import NeuroSymbolicSafetyEngine

class TestPhase4SafetyEngine(unittest.TestCase):
    def setUp(self):
        self.safety = NeuroSymbolicSafetyEngine(max_memory_percent=90.0, high_cpu_percent=85.0)

    def test_1_normal_hardware_approval(self):
        hw = HardwareSnapshot(
            cpu_percent_total=25.0,
            cpu_percent_per_core=[20.0, 30.0],
            memory_percent=45.0,
            memory_available_bytes=4000000000,
            thermal_throttled=False,
            battery_saver_active=False
        )
        decision = self.safety.evaluate("pylance", confidence=0.92, hardware=hw)
        self.assertTrue(decision.approved)
        self.assertEqual(decision.target_core, 0)
        self.assertEqual(decision.recommended_nice, -5)

    def test_2_memory_exceeded_rejection(self):
        hw = HardwareSnapshot(
            cpu_percent_total=30.0,
            cpu_percent_per_core=[30.0, 30.0],
            memory_percent=95.0,  # Exceeds 90%
            memory_available_bytes=500000000,
            thermal_throttled=False,
            battery_saver_active=False
        )
        decision = self.safety.evaluate("pylance", confidence=0.95, hardware=hw)
        self.assertFalse(decision.approved)
        self.assertTrue(any("RULE_REJECT_MEMORY" in r for r in decision.reasons))

    def test_3_thermal_throttling_rejection(self):
        hw = HardwareSnapshot(
            cpu_percent_total=40.0,
            cpu_percent_per_core=[40.0, 40.0],
            memory_percent=50.0,
            memory_available_bytes=4000000000,
            thermal_throttled=True,
            battery_saver_active=False
        )
        decision = self.safety.evaluate("gcc", confidence=0.88, hardware=hw)
        self.assertFalse(decision.approved)
        self.assertTrue(any("RULE_REJECT_THERMAL" in r for r in decision.reasons))

    def test_4_battery_saver_efficiency_core(self):
        hw = HardwareSnapshot(
            cpu_percent_total=15.0,
            cpu_percent_per_core=[15.0, 15.0],
            memory_percent=40.0,
            memory_available_bytes=4000000000,
            thermal_throttled=False,
            battery_saver_active=True
        )
        decision = self.safety.evaluate("git", confidence=0.85, hardware=hw)
        self.assertTrue(decision.approved)
        self.assertEqual(decision.target_core, 1)  # Efficiency core

if __name__ == "__main__":
    unittest.main()
