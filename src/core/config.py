import os
from dataclasses import dataclass

@dataclass
class ChronoConfig:
    # Database
    db_path: str = os.getenv("CHRONOSCHED_DB", "/home/vboxuser/Desktop/ChronoScheduler/data/chronosched.db")
    
    # Telemetry
    polling_interval_sec: float = 0.05
    filter_kernel_threads: bool = True
    
    # Temporal Graph
    max_transition_window_sec: float = 6.0  # Max delay between tightly dependent processes
    temporal_decay_halflife_sec: float = 86400.0  # 1 day halflife for recency decay
    max_graph_edges: int = 5000
    prune_threshold_weight: float = 0.01
    
    # Confidence Engine
    confidence_threshold: float = 0.35  # Gate to reach safety / digital twin
    learning_rate: float = 0.15
    failure_penalty: float = 0.25
    
    # Safety Engine Constraints
    max_memory_percent: float = 90.0
    high_cpu_percent: float = 85.0
    reject_on_thermal_throttle: bool = True
    
    # Scheduler Execution & Rollback
    prediction_timeout_sec: float = 5.0  # Time to wait for predicted process before rollback
    default_performance_core: int = 0
    default_efficiency_core: int = 1
    default_preemptive_nice: int = -5

config = ChronoConfig()
