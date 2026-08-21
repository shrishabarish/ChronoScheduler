import psutil
from typing import Dict, Any, List, Optional
from ..core.models import SafetyDecision, HardwareSnapshot
from ..core.config import config

class NeuroSymbolicSafetyEngine:
    def __init__(
        self,
        max_memory_percent: float = config.max_memory_percent,
        high_cpu_percent: float = config.high_cpu_percent,
        reject_on_thermal_throttle: bool = config.reject_on_thermal_throttle
    ):
        self.max_memory_percent = max_memory_percent
        self.high_cpu_percent = high_cpu_percent
        self.reject_on_thermal_throttle = reject_on_thermal_throttle

    def capture_hardware_snapshot(self) -> HardwareSnapshot:
        mem = psutil.virtual_memory()
        cpu_total = psutil.cpu_percent(interval=None)
        cpu_per_core = psutil.cpu_percent(interval=None, percpu=True)
        
        # Check thermal throttling / battery if available
        thermal_throttled = False
        try:
            temps = psutil.sensors_temperatures() if hasattr(psutil, "sensors_temperatures") else {}
            for name, entries in temps.items():
                for entry in entries:
                    if entry.critical and entry.current >= entry.critical:
                        thermal_throttled = True
        except Exception:
            thermal_throttled = False

        battery_saver = False
        try:
            battery = psutil.sensors_battery() if hasattr(psutil, "sensors_battery") else None
            if battery and not battery.power_plugged and battery.percent < 20.0:
                battery_saver = True
        except Exception:
            battery_saver = False

        return HardwareSnapshot(
            cpu_percent_total=cpu_total,
            cpu_percent_per_core=cpu_per_core,
            memory_percent=mem.percent,
            memory_available_bytes=mem.available,
            thermal_throttled=thermal_throttled,
            battery_saver_active=battery_saver
        )

    def evaluate(
        self,
        predicted_process: str,
        confidence: float,
        hardware: Optional[HardwareSnapshot] = None
    ) -> SafetyDecision:
        hw = hardware or self.capture_hardware_snapshot()
        reasons: List[str] = []
        approved = True
        target_core = config.default_performance_core
        recommended_nice = config.default_preemptive_nice

        # Rule 1: Memory Constraint (Hard Safety Gate)
        if hw.memory_percent > self.max_memory_percent:
            approved = False
            reasons.append(f"RULE_REJECT_MEMORY: Memory usage ({hw.memory_percent:.1f}%) exceeds safety limit ({self.max_memory_percent:.1f}%)")

        # Rule 2: CPU Saturation Constraint
        if hw.cpu_percent_total > self.high_cpu_percent:
            approved = False
            reasons.append(f"RULE_REJECT_CPU: CPU usage ({hw.cpu_percent_total:.1f}%) exceeds high threshold ({self.high_cpu_percent:.1f}%)")

        # Rule 3: Thermal Throttling Constraint
        if self.reject_on_thermal_throttle and hw.thermal_throttled:
            approved = False
            reasons.append("RULE_REJECT_THERMAL: System reports active thermal throttling")

        # Rule 4: Battery Saver Constraint
        if hw.battery_saver_active:
            target_core = config.default_efficiency_core
            recommended_nice = 0  # Standard priority to conserve power
            reasons.append("RULE_ADAPT_BATTERY: Battery low/saver active -> assigned to Efficiency Core")

        # Rule 5: Latency-Critical Optimization
        if approved and not hw.battery_saver_active:
            target_core = config.default_performance_core
            recommended_nice = -5
            reasons.append(f"RULE_PERF_ALLOC: Latency critical -> assigned to Performance Core {target_core} with nice {recommended_nice}")

        rule_summary = "ALL_RULES_PASSED" if approved else "; ".join(reasons)

        return SafetyDecision(
            approved=approved,
            reasons=reasons,
            rule_name=rule_summary,
            hardware_state={
                "cpu_percent": hw.cpu_percent_total,
                "memory_percent": hw.memory_percent,
                "thermal_throttled": hw.thermal_throttled,
                "battery_saver": hw.battery_saver_active
            },
            target_core=target_core if approved else None,
            recommended_nice=recommended_nice if approved else 0
        )
