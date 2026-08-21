#!/usr/bin/env python3
import sys
import os
import time
import threading
import psutil

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.core.models import ProcessEvent
from src.core.config import config
from src.daemon import ChronoSchedDaemon
from src.server.ws_server import LightweightWebSocketServer

def broadcast_pipeline_update(ws_server: LightweightWebSocketServer, daemon: ChronoSchedDaemon):
    """Periodically broadcasts graph edges and hardware state to dashboard."""
    while True:
        try:
            edges_payload = []
            for src, targets in daemon.graph.edges.items():
                for tgt, edge in targets.items():
                    edges_payload.append({
                        "source": src,
                        "target": tgt,
                        "frequency": edge.frequency,
                        "avg_delay": edge.average_delay_seconds,
                        "confidence": edge.confidence,
                        "success_rate": edge.success_rate
                    })
            ws_server.broadcast_sync("graph_state", {"edges": edges_payload})

            mem = psutil.virtual_memory()
            cpu = psutil.cpu_percent(interval=None)
            ws_server.broadcast_sync("hardware_state", {
                "cpu": round(cpu, 1),
                "mem": round(mem.percent, 1),
                "temp": "Normal",
                "cores": [0, 1]
            })
        except Exception:
            pass
        time.sleep(1.0)

def main():
    print("=" * 70)
    print("  CHRONOSCHED: PREEMPTIVE CPU RESOURCE ALLOCATION SYSTEM")
    print("  Form-B Closed-Loop Real-Time Observability Runner")
    print("=" * 70)

    # 1. Start WebSocket Server
    ws_server = LightweightWebSocketServer(host="127.0.0.1", port=8765)
    ws_server.start()
    print("[+] WebSocket Server started on ws://127.0.0.1:8765")

    # Current pipeline state container for broadcast
    current_pipeline = {}

    def pipeline_callback(step_name: str, payload: any):
        if step_name == "telemetry_event":
            current_pipeline["event"] = {
                "pid": payload.pid,
                "process_name": payload.process_name,
                "executable": payload.executable
            }
            ws_server.broadcast_sync("telemetry_event", current_pipeline["event"])
        elif step_name == "prediction_generated":
            current_pipeline["prediction"] = {
                "source_process": payload.source_process,
                "predicted_process": payload.predicted_process,
                "probability": payload.probability,
                "confidence": payload.confidence
            }
        elif step_name == "safety_decision":
            current_pipeline["safety"] = {
                "approved": payload.approved,
                "rule_name": payload.rule_name
            }
        elif step_name == "digital_twin_simulation":
            current_pipeline["simulation"] = {
                "approved": payload.approved,
                "predicted_cpu_delta": payload.predicted_cpu_delta,
                "latency_estimate_ms": payload.latency_estimate_ms,
                "simulation_state": payload.simulation_state
            }
        elif step_name == "scheduler_action_applied":
            current_pipeline["action"] = {
                "action_id": payload.action_id or 1,
                "pid": payload.pid,
                "process_name": payload.process_name,
                "new_affinity": payload.new_affinity,
                "new_priority": payload.new_priority,
                "applied": payload.applied
            }
            # Broadcast the complete 5-stage pipeline
            ws_server.broadcast_sync("pipeline_execution", dict(current_pipeline))
            print(f"    ↳ [PIPELINE] Predicted: {current_pipeline['prediction']['predicted_process']} (Conf: {current_pipeline['prediction']['confidence']:.2f}) -> Pinned to Core {payload.new_affinity[0]}")
        elif step_name == "feedback_success":
            ws_server.broadcast_sync("feedback_success", {
                "action_id": payload.action_id,
                "predicted_process": payload.predicted_process,
                "latency_ms": payload.latency_observed_ms
            })
            print(f"    ↳ [FEEDBACK] Success! '{payload.predicted_process}' launched (+Reward applied, confidence boosted)")
        elif step_name == "rollback_timeout_penalty":
            ws_server.broadcast_sync("rollback_timeout_penalty", {
                "action_id": payload.action_id,
                "predicted_process": payload.predicted_process
            })
            print(f"    ↳ [WATCHDOG] Timeout expired for '{payload.predicted_process}' -> Rolled back scheduler state (-Penalty)")

    # 2. Instantiate Daemon
    daemon = ChronoSchedDaemon(db_path=":memory:", on_pipeline_step=pipeline_callback)

    # 3. Pre-train canonical workflows so the graph is instantly populated
    print("[+] Pre-training canonical developer workflow graph...")
    base_t = time.time() - 3600.0
    for i in range(6):
        t = base_t + (i * 25.0)
        # code -> pylance
        daemon.graph.add_process_event(ProcessEvent(pid=1000+i, ppid=1, process_name="code", executable="/usr/bin/code", timestamp=t), current_time=t)
        daemon.graph.add_process_event(ProcessEvent(pid=2000+i, ppid=1000+i, process_name="pylance", executable="/usr/bin/pylance", timestamp=t+2.0), current_time=t+2.0)
        # terminal -> python3
        daemon.graph.add_process_event(ProcessEvent(pid=3000+i, ppid=1, process_name="terminal", executable="/usr/bin/bash", timestamp=t+6.0), current_time=t+6.0)
        daemon.graph.add_process_event(ProcessEvent(pid=4000+i, ppid=3000+i, process_name="python3", executable="/usr/bin/python3", timestamp=t+7.5), current_time=t+7.5)
        # build_tool -> gcc -> ld
        daemon.graph.add_process_event(ProcessEvent(pid=5000+i, ppid=1, process_name="build_tool", executable="/usr/bin/make", timestamp=t+10.0), current_time=t+10.0)
        daemon.graph.add_process_event(ProcessEvent(pid=6000+i, ppid=5000+i, process_name="gcc", executable="/usr/bin/gcc", timestamp=t+11.8), current_time=t+11.8)
        daemon.graph.add_process_event(ProcessEvent(pid=7000+i, ppid=6000+i, process_name="ld", executable="/usr/bin/ld", timestamp=t+12.6), current_time=t+12.6)

    # 4. Start background telemetry and status sync
    daemon.start()
    sync_thread = threading.Thread(target=broadcast_pipeline_update, args=(ws_server, daemon), daemon=True)
    sync_thread.start()

    print("\n" + "-" * 70)
    print("  DASHBOARD URL: file:///home/vboxuser/Desktop/ChronoScheduler/frontend/index.html")
    print("  Open this file in your browser to watch live telemetry.")
    print("-" * 70 + "\n")

    print("Options:")
    print(" [1] Simulate VSCode launch -> Predicts Pylance -> Core allocation")
    print(" [2] Simulate Pylance launch -> Triggers +Reward Success Feedback")
    print(" [3] Simulate Terminal launch & wait 5s -> Triggers -Penalty Timeout Rollback")
    print(" [4] Run live loop (watches real system processes)")
    print(" [q] Quit\n")

    while True:
        try:
            choice = input("ChronoSched> ").strip()
            now = time.time()
            if choice == "1":
                print("\n>>> [EVENT] User launched 'code' (PID 8812)")
                daemon.handle_process_event(ProcessEvent(pid=8812, ppid=1, process_name="code", executable="/usr/bin/code", timestamp=now))
            elif choice == "2":
                print("\n>>> [EVENT] Impending process 'pylance' launched (PID 8813)")
                daemon.handle_process_event(ProcessEvent(pid=8813, ppid=8812, process_name="pylance", executable="/usr/bin/pylance", timestamp=now))
            elif choice == "3":
                print("\n>>> [EVENT] User launched 'terminal' (PID 9901) -> Waiting for timeout...")
                daemon.handle_process_event(ProcessEvent(pid=9901, ppid=1, process_name="terminal", executable="/usr/bin/bash", timestamp=now))
            elif choice == "4":
                print("\n>>> Monitoring live OS process spawns in background. Press Ctrl+C to return to menu.")
                time.sleep(30)
            elif choice.lower() == "q":
                break
        except (KeyboardInterrupt, EOFError):
            break

    daemon.stop()
    print("\n[+] ChronoSched shutdown complete.")

if __name__ == "__main__":
    main()
