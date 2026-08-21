from typing import Dict, Optional, Any
from ..core.models import SimulationResult, SafetyDecision, HardwareSnapshot

class DigitalTwinSimulator:
    def __init__(self):
        # Historical profile lookup for process footprint estimates (in MB and typical CPU load %)
        self.process_profiles: Dict[str, Dict[str, float]] = {
            "pylance": {"cpu_delta": 25.0, "mem_delta_mb": 180.0, "latency_ms": 1.2},
            "python": {"cpu_delta": 15.0, "mem_delta_mb": 50.0, "latency_ms": 0.8},
            "python3": {"cpu_delta": 15.0, "mem_delta_mb": 50.0, "latency_ms": 0.8},
            "git": {"cpu_delta": 10.0, "mem_delta_mb": 30.0, "latency_ms": 0.5},
            "gcc": {"cpu_delta": 45.0, "mem_delta_mb": 250.0, "latency_ms": 2.5},
            "node": {"cpu_delta": 20.0, "mem_delta_mb": 120.0, "latency_ms": 1.0},
            "default": {"cpu_delta": 10.0, "mem_delta_mb": 60.0, "latency_ms": 1.0}
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

        profile = self.process_profiles.get(predicted_process.lower(), self.process_profiles["default"])
        cpu_delta = profile["cpu_delta"]
        mem_delta_mb = profile["mem_delta_mb"]
        latency_ms = profile["latency_ms"]

        # Simulate core-specific saturation
        target_core = safety_decision.target_core if safety_decision.target_core is not None else 0
        current_core_load = 0.0
        if target_core < len(hardware.cpu_percent_per_core):
            current_core_load = hardware.cpu_percent_per_core[target_core]
        else:
            current_core_load = hardware.cpu_percent_total

        projected_core_load = current_core_load + cpu_delta
        
        # Thermal risk estimation
        if projected_core_load > 90.0 or hardware.cpu_percent_total > 80.0:
            thermal_risk = "HIGH"
        elif projected_core_load > 60.0:
            thermal_risk = "MEDIUM"
        else:
            thermal_risk = "LOW"

        # Safe simulation bounds: projected core load must not exceed 98%
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
