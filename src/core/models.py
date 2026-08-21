import time
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any

@dataclass
class ProcessEvent:
    pid: int
    ppid: int
    process_name: str
    executable: str
    timestamp: float = field(default_factory=time.time)
    cpu_percent: float = 0.0
    memory_rss_bytes: int = 0
    cpu_affinity: List[int] = field(default_factory=list)
    process_state: str = "running"
    parent_name: Optional[str] = None
    event_id: Optional[int] = None
    source: str = "psutil"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

@dataclass
class DependencyEdge:
    source_process: str
    target_process: str
    frequency: int = 1
    total_delay_seconds: float = 0.0
    average_delay_seconds: float = 0.0
    success_count: int = 0
    failure_count: int = 0
    success_rate: float = 1.0
    recency_timestamp: float = field(default_factory=time.time)
    prediction_probability: float = 0.0
    confidence: float = 0.0
    edge_id: Optional[int] = None

    def update_transition(self, delay: float, current_time: float):
        self.frequency += 1
        self.total_delay_seconds += delay
        self.average_delay_seconds = self.total_delay_seconds / self.frequency
        self.recency_timestamp = current_time

    def record_feedback(self, success: bool, learning_rate: float = 0.1, penalty: float = 0.2):
        if success:
            self.success_count += 1
            self.confidence = min(1.0, self.confidence + learning_rate * (1.0 - self.confidence))
        else:
            self.failure_count += 1
            self.confidence = max(0.0, self.confidence - penalty * self.confidence)
        
        total = self.success_count + self.failure_count
        if total > 0:
            self.success_rate = self.success_count / total

@dataclass
class PredictionResult:
    source_process: str
    predicted_process: str
    probability: float
    confidence: float
    expected_delay_seconds: float
    timestamp: float = field(default_factory=time.time)
    prediction_id: Optional[int] = None

@dataclass
class SafetyDecision:
    approved: bool
    reasons: List[str]
    rule_name: str
    hardware_state: Dict[str, Any]
    target_core: Optional[int] = None
    recommended_nice: int = 0

@dataclass
class SimulationResult:
    approved: bool
    predicted_cpu_delta: float
    predicted_memory_delta_mb: float
    latency_estimate_ms: float
    thermal_risk: str
    simulation_state: str

@dataclass
class SchedulerAction:
    pid: int
    process_name: str
    previous_priority: int
    new_priority: int
    previous_affinity: List[int]
    new_affinity: List[int]
    reason: str
    confidence: float
    timestamp: float = field(default_factory=time.time)
    action_id: Optional[int] = None
    applied: bool = False
    rolled_back: bool = False

@dataclass
class FeedbackEvent:
    action_id: int
    predicted_process: str
    actual_process: Optional[str]
    success: bool
    latency_observed_ms: float
    timestamp: float = field(default_factory=time.time)
    feedback_id: Optional[int] = None

@dataclass
class HardwareSnapshot:
    cpu_percent_total: float
    cpu_percent_per_core: List[float]
    memory_percent: float
    memory_available_bytes: int
    thermal_throttled: bool
    battery_saver_active: bool
    timestamp: float = field(default_factory=time.time)
