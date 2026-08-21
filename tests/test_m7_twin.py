import unittest
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.core.models import HardwareSnapshot, SafetyDecision
from src.engine.digital_twin import DigitalTwinSimulator

class TestPhase5DigitalTwin(unittest.TestCase):
    def setUp(self):
        self.twin = DigitalTwinSimulator()

    def test_1_safe_simulation(self):
        hw = HardwareSnapshot(
            cpu_percent_total=20.0,
            cpu_percent_per_core=[20.0, 20.0],
            memory_percent=35.0,
            memory_available_bytes=4000000000,
            thermal_throttled=False,
            battery_saver_active=False
        )
        safety = SafetyDecision(
            approved=True,
            reasons=["ALL_RULES_PASSED"],
            rule_name="ALL_RULES_PASSED",
            hardware_state={},
            target_core=0,
            recommended_nice=-5
        )
        sim = self.twin.simulate("pylance", safety, hw)
        self.assertTrue(sim.approved)
        self.assertEqual(sim.simulation_state, "SAFE")
        self.assertEqual(sim.thermal_risk, "LOW")

    def test_2_core_saturation_rejection(self):
        hw = HardwareSnapshot(
            cpu_percent_total=80.0,
            cpu_percent_per_core=[85.0, 30.0],  # Core 0 already at 85%
            memory_percent=50.0,
            memory_available_bytes=4000000000,
            thermal_throttled=False,
            battery_saver_active=False
        )
        safety = SafetyDecision(
            approved=True,
            reasons=["ALL_RULES_PASSED"],
            rule_name="ALL_RULES_PASSED",
            hardware_state={},
            target_core=0,  # Target core 0 + gcc delta (45%) = 130% > 95%
            recommended_nice=-5
        )
        sim = self.twin.simulate("gcc", safety, hw)
        self.assertFalse(sim.approved)
        self.assertEqual(sim.simulation_state, "REJECT_CORE_SATURATION")
        self.assertEqual(sim.thermal_risk, "HIGH")

if __name__ == "__main__":
    unittest.main()
