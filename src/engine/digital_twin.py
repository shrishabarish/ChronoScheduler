import logging
from typing import Dict, Optional, Any
from ..core.models import SimulationResult, SafetyDecision, HardwareSnapshot
from ..core.database import EventStore

logger = logging.getLogger("ChronoSched.DigitalTwin")

class DigitalTwinSimulator:
    def __init__(self, db: Optional[EventStore] = None):
        self.db = db
        # Canonical baseline process profiles
        self.process_profiles: Dict[str, Dict[str, float]] = {
            "pylance": {"cpu_delta": 25.0, "mem_delta_mb": 180.0, "latency_ms": 1.2},
            "python": {"cpu_delta": 15.0, "mem_delta_mb": 50.0, "latency_ms": 0.8},
            "python3": {"cpu_delta": 15.0, "mem_delta_mb": 50.0, "latency_ms": 0.8},
            "git": {"cpu_delta": 10.0, "mem_delta_mb": 30.0, "latency_ms": 0.5},
            "gcc": {"cpu_delta": 45.0, "mem_delta_mb": 250.0, "latency_ms": 2.5},
            "clang": {"cpu_delta": 45.0, "mem_delta_mb": 260.0, "latency_ms": 2.4},
            "ld": {"cpu_delta": 30.0, "mem_delta_mb": 150.0, "latency_ms": 1.8},
            "node": {"cpu_delta": 20.0, "mem_delta_mb": 120.0, "latency_ms": 1.0},
            "rustc": {"cpu_delta": 50.0, "mem_delta_mb": 300.0, "latency_ms": 3.0},
            "cargo": {"cpu_delta": 20.0, "mem_delta_mb": 80.0, "latency_ms": 1.0},
            "default": {"cpu_delta": 10.0, "mem_delta_mb": 60.0, "latency_ms": 1.0}
        }
        self._load_profiles_from_db()

    def _load_profiles_from_db(self):
        if self.db:
            try:
                db_profiles = self.db.get_all_process_profiles()
                for proc, data in db_profiles.items():
                    self.process_profiles[proc.lower()] = {
                        "cpu_delta": data["cpu_delta"],
                        "mem_delta_mb": data["mem_delta_mb"],
                        "latency_ms": data["latency_ms"]
                    }
            except Exception as err:
                logger.debug(f"Failed loading dynamic profiles from DB: {err}")

    def record_observed_footprint(
        self,
        process_name: str,
        cpu_delta: float,
        mem_delta_mb: float,
        latency_ms: float
    ):
        """Dynamically learns and adapts process footprint metrics."""
        proc_key = process_name.lower()
        if self.db:
            self.db.upsert_process_profile(proc_key, cpu_delta, mem_delta_mb, latency_ms)
            updated = self.db.get_process_profile(proc_key)
            if updated:
                self.process_profiles[proc_key] = {
                    "cpu_delta": updated["cpu_delta"],
                    "mem_delta_mb": updated["mem_delta_mb"],
                    "latency_ms": updated["latency_ms"]
                }
        else:
            self.process_profiles[proc_key] = {
                "cpu_delta": cpu_delta,
                "mem_delta_mb": mem_delta_mb,
                "latency_ms": latency_ms
            }

    def simulate(
        self,
        predicted_process: str,
        safety_decision: SafetyDecision,
        hardware: HardwareSnapshot
    ) -> SimulationResult:
        if not safety_decision.approved:
            return SimulationResult(
                approved=False,
                predicted_cpu_delta=0.0,
                predicted_memory_delta_mb=0.0,
                latency_estimate_ms=0.0,
                thermal_risk="HIGH",
                simulation_state="REJECT_SAFETY_FAILED"
            )

        proc_key = predicted_process.lower()
        profile = self.process_profiles.get(proc_key, self.process_profiles["default"])
        cpu_delta = profile["cpu_delta"]
        mem_delta_mb = profile["mem_delta_mb"]
        latency_ms = profile["latency_ms"]

        # 1. Simulate core-specific saturation
        target_core = safety_decision.target_core if safety_decision.target_core is not None else 0
        current_core_load = 0.0
        if target_core < len(hardware.cpu_percent_per_core):
            current_core_load = hardware.cpu_percent_per_core[target_core]
        else:
            current_core_load = hardware.cpu_percent_total

        projected_core_load = current_core_load + cpu_delta

        # 2. Check memory headroom safety (MB available)
        available_mb = hardware.memory_available_bytes / (1024 * 1024)
        if mem_delta_mb > available_mb * 0.8:
            return SimulationResult(
                approved=False,
                predicted_cpu_delta=cpu_delta,
                predicted_memory_delta_mb=mem_delta_mb,
                latency_estimate_ms=latency_ms,
                thermal_risk="HIGH",
                simulation_state="REJECT_MEMORY_PRESSURE"
            )
        
        # 3. Thermal risk estimation
        if projected_core_load > 90.0 or hardware.cpu_percent_total > 80.0:
            thermal_risk = "HIGH"
        elif projected_core_load > 60.0:
            thermal_risk = "MEDIUM"
        else:
            thermal_risk = "LOW"

        # 4. Safe simulation bounds: projected core load must not exceed 98%
        approved = projected_core_load < 98.0
        simulation_state = "SAFE" if approved else "REJECT_CORE_SATURATION"

        return SimulationResult(
            approved=approved,
            predicted_cpu_delta=cpu_delta,
            predicted_memory_delta_mb=mem_delta_mb,
            latency_estimate_ms=latency_ms,
            thermal_risk=thermal_risk,
            simulation_state=simulation_state
        )

