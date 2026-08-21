import random
import time
from typing import List, Tuple
from ..core.models import ProcessEvent

# Canonical multi-step developer workflow chains for validation
WORKFLOW_CHAINS = [
    [("code", 0.0), ("pylance", 2.0)],
    [("terminal", 0.0), ("python3", 1.5)],
    [("build_tool", 0.0), ("gcc", 1.8), ("ld", 0.8)],
    [("browser", 0.0), ("gpu_process", 1.0)],
    [("editor", 0.0), ("format_daemon", 1.2)],
    [("git_client", 0.0), ("ssh", 1.4)],
]

NOISE_PROCESSES = ["dbus-daemon", "systemd-resolved", "cron", "rsyslogd", "cupsd"]

def generate_validation_traces(
    num_sessions: int = 80,
    noise_ratio: float = 0.10,
    seed: int = 42
) -> List[ProcessEvent]:
    """
    Generates a deterministic sequence of realistic cross-session process launches
    interleaved with system noise.
    """
    rng = random.Random(seed)
    events: List[ProcessEvent] = []
    current_time = 100000.0
    pid_counter = 1000

    for session in range(num_sessions):
        # Sample 3-5 workflows per session
        selected_chains = rng.sample(WORKFLOW_CHAINS, k=rng.randint(3, len(WORKFLOW_CHAINS)))
        
        for chain in selected_chains:
            for step_idx, (proc_name, delay) in enumerate(chain):
                # Apply delay with slight natural jitter
                jitter = rng.uniform(-0.15, 0.15) if delay > 0 else 0.0
                actual_delay = max(0.2, delay + jitter) if delay > 0 else 0.0
                current_time += actual_delay
                pid_counter += 1

                events.append(ProcessEvent(
                    pid=pid_counter,
                    ppid=pid_counter - 1 if step_idx > 0 else 1,
                    process_name=proc_name,
                    executable=f"/usr/bin/{proc_name}",
                    timestamp=current_time
                ))

                # Inject occasional system noise
                if rng.random() < noise_ratio:
                    pid_counter += 1
                    noise_name = rng.choice(NOISE_PROCESSES)
                    events.append(ProcessEvent(
                        pid=pid_counter,
                        ppid=1,
                        process_name=noise_name,
                        executable=f"/usr/sbin/{noise_name}",
                        timestamp=current_time + 0.3
                    ))

            # Inter-workflow gap (user working inside the application)
            current_time += rng.uniform(20.0, 45.0)

        # Inter-session pause (user idle / context switch)
        current_time += rng.uniform(60.0, 240.0)

    return events
