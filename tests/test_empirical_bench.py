import unittest
import os
import sys
import tempfile
import shutil

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.core.database import EventStore
from src.core.models import ProcessEvent, SafetyDecision, HardwareSnapshot
from src.engine.digital_twin import DigitalTwinSimulator
from src.validation.empirical_bench import EmpiricalBenchmarkRunner
from src.validation.export_patent_report import export_patent_results, generate_patent_section8_markdown

class TestEmpiricalBenchAndProfiles(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_chrono.db")
        self.db = EventStore(self.db_path)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_dynamic_digital_twin_profiling(self):
        twin = DigitalTwinSimulator(db=self.db)
        # Record observed runtime footprint for a custom compiler
        twin.record_observed_footprint("custom_compiler", cpu_delta=35.0, mem_delta_mb=190.0, latency_ms=1.5)
        
        # Verify in memory
        self.assertIn("custom_compiler", twin.process_profiles)
        self.assertEqual(twin.process_profiles["custom_compiler"]["cpu_delta"], 35.0)

        # Verify persisted in database
        persisted = self.db.get_process_profile("custom_compiler")
        self.assertIsNotNone(persisted)
        self.assertEqual(persisted["sample_count"], 1)

        # Record second observation and verify exponential/cumulative average update
        twin.record_observed_footprint("custom_compiler", cpu_delta=45.0, mem_delta_mb=210.0, latency_ms=2.5)
        updated = self.db.get_process_profile("custom_compiler")
        self.assertEqual(updated["sample_count"], 2)
        self.assertEqual(updated["cpu_delta"], 40.0) # (35 + 45)/2
        self.assertEqual(updated["mem_delta_mb"], 200.0) # (190 + 210)/2

    def test_digital_twin_memory_rejection(self):
        twin = DigitalTwinSimulator(db=self.db)
        # Create a low available memory snapshot (only 50MB available)
        hw = HardwareSnapshot(
            cpu_percent_total=10.0,
            cpu_percent_per_core=[10.0, 10.0],
            memory_percent=95.0,
            memory_available_bytes=50 * 1024 * 1024, # 50 MB
            thermal_throttled=False,
            battery_saver_active=False
        )
        safe_dec = SafetyDecision(
            approved=True,
            reasons=[],
            rule_name="ALL_PASSED",
            hardware_state={},
            target_core=0
        )
        # GCC requires 250MB, but only 50MB available -> Should reject memory pressure
        sim_res = twin.simulate("gcc", safe_dec, hw)
        self.assertFalse(sim_res.approved)
        self.assertEqual(sim_res.simulation_state, "REJECT_MEMORY_PRESSURE")

    def test_empirical_benchmark_run(self):
        runner = EmpiricalBenchmarkRunner(iterations=5)
        res = runner.run_benchmark()
        
        self.assertGreater(res.iterations, 0)
        self.assertGreater(res.cfs_mean_latency_ms, 0.0)
        self.assertGreater(res.chrono_mean_latency_ms, 0.0)
        self.assertGreaterEqual(res.prediction_accuracy_percent, 85.0)
        self.assertLess(res.mean_inference_overhead_us, 1000.0) # < 1 ms

        # Test patent report generator
        md = generate_patent_section8_markdown(res)
        self.assertIn("Form-B Section 8", md)
        self.assertIn("Cold Start Latency", md)

        # Test exporter
        json_p, md_p = export_patent_results(res, output_dir=self.temp_dir)
        self.assertTrue(os.path.exists(json_p))
        self.assertTrue(os.path.exists(md_p))

if __name__ == "__main__":
    unittest.main()
