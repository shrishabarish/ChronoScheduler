import sys
import os
import argparse
import time

# Ensure project root is in sys.path for direct execution
_proj_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _proj_root not in sys.path:
    sys.path.insert(0, _proj_root)

try:
    from .daemon import ChronoSchedDaemon
    from .core.config import config
    from .core.database import EventStore
    from .core.models import ProcessEvent
    from .server.ws_server import LightweightWebSocketServer
    from .validation.empirical_bench import EmpiricalBenchmarkRunner
    from .validation.export_patent_report import export_patent_results
except ImportError:
    from src.daemon import ChronoSchedDaemon
    from src.core.config import config
    from src.core.database import EventStore
    from src.core.models import ProcessEvent
    from src.server.ws_server import LightweightWebSocketServer
    from src.validation.empirical_bench import EmpiricalBenchmarkRunner
    from src.validation.export_patent_report import export_patent_results

def cmd_run(args):
    """Starts the ChronoSched background daemon with live process monitoring."""
    print(">>> Starting ChronoSched Closed-Loop Daemon...")
    daemon = ChronoSchedDaemon()
    daemon.start()
    print(">>> ChronoSched is actively monitoring process lifecycle. Press Ctrl+C to terminate.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n>>> Stopping ChronoSched Daemon...")
        daemon.stop()

def cmd_bench(args):
    """Runs the empirical benchmark harness and outputs results."""
    print(">>> Initializing ChronoSched Empirical Benchmark Harness...")
    runner = EmpiricalBenchmarkRunner(iterations=args.iterations)
    res = runner.run_benchmark()
    json_p, md_p = export_patent_results(res)
    print(f"\n[+] Empirical Benchmark Complete!")
    print(f"    - Cold Start Latency Reduction : {res.latency_reduction_percent:.2f}%")
    print(f"    - Inference Overhead          : {res.mean_inference_overhead_us:.2f} µs")
    print(f"    - Prediction Accuracy         : {res.prediction_accuracy_percent:.2f}%")
    print(f"    - Section 8 Report            : {md_p}")

def cmd_inspect(args=None):
    """Inspects the SQLite-backed DAG dependency graph."""
    db = EventStore(config.db_path)
    edges = db.get_all_dependency_edges()
    print(f"\n=== ChronoSched Learned Dependency Graph ({len(edges)} edges) ===")
    if not edges:
        print("  (Graph is empty or newly initialized)")
        return
    print(f"{'Source':<15} -> {'Target':<15} | {'Freq':<5} | {'Confidence':<10} | {'Prob':<6} | {'Avg Delay (s)':<12}")
    print("-" * 75)
    for e in edges:
        print(f"{e.source_process:<15} -> {e.target_process:<15} | {e.frequency:<5} | {e.confidence:<10.2f} | {e.prediction_probability:<6.2f} | {e.average_delay_seconds:<12.3f}")

def cmd_profiles(args=None):
    """Inspects the learned process resource profiles in the Digital Twin."""
    db = EventStore(config.db_path)
    profiles = db.get_all_process_profiles()
    print(f"\n=== ChronoSched Digital Twin Learned Profiles ({len(profiles)} processes) ===")
    if not profiles:
        print("  (No dynamic profiles recorded yet)")
        return
    print(f"{'Process':<15} | {'CPU Delta (%)':<15} | {'Memory (MB)':<12} | {'Latency (ms)':<12} | {'Samples':<8}")
    print("-" * 75)
    for name, p in profiles.items():
        print(f"{name:<15} | {p['cpu_delta']:<15.1f} | {p['mem_delta_mb']:<12.1f} | {p['latency_ms']:<12.2f} | {p['sample_count']:<8}")

def cmd_demo(args=None):
    """Starts the interactive live demo with WebSocket telemetry and auto-opens browser."""
    import webbrowser
    import platform
    import threading
    import psutil

    os_name = f"{platform.system()} {platform.release()} ({platform.machine()})"
    cpu_count = psutil.cpu_count(logical=True) or 2
    mem = psutil.virtual_memory()

    print("\n" + "=" * 76)
    print("      CHRONOSCHEDULER: PREEMPTIVE CPU RESOURCE ALLOCATION SYSTEM")
    print("      Closed-Loop Neuro-Symbolic Scheduling & Digital Twin Pipeline")
    print("=" * 76)
    print(f"  * Platform Detected : {os_name}")
    print(f"  * Logical CPU Cores : {cpu_count} Cores (Target Pin Core: 0)")
    print(f"  * System Memory     : {mem.total / (1024**3):.1f} GB ({mem.percent}% used)")
    print(f"  * SQLite Database   : {config.db_path}")
    print(f"  * WebSocket Server  : ws://127.0.0.1:8765 [Online]")
    print("=" * 76)

    # 1. Daemon instance
    daemon_holder = {"daemon": None}

    def handle_client_message(action: str, payload: dict):
        d = daemon_holder.get("daemon")
        if not d:
            return
        now = time.time()
        pid = payload.get("pid", 8800 + int(now % 1000))
        if action == "simulate_vscode":
            print(f"\n[WEB-UI] >> User launched 'code' (PID {pid})")
            d.handle_process_event(ProcessEvent(pid=pid, ppid=1, process_name="code", executable="code", timestamp=now))
        elif action == "simulate_pylance":
            print(f"\n[WEB-UI] >> Impending process 'pylance' launched (PID {pid+1})")
            d.handle_process_event(ProcessEvent(pid=pid+1, ppid=pid, process_name="pylance", executable="pylance", timestamp=now))
        elif action == "simulate_build":
            print(f"\n[WEB-UI] >> User launched 'build_tool' (PID {pid})")
            d.handle_process_event(ProcessEvent(pid=pid, ppid=1, process_name="build_tool", executable="build_tool", timestamp=now))
        elif action == "simulate_gcc":
            print(f"\n[WEB-UI] >> Impending process 'gcc' launched (PID {pid+1})")
            d.handle_process_event(ProcessEvent(pid=pid+1, ppid=pid, process_name="gcc", executable="gcc", timestamp=now))
        elif action == "simulate_timeout":
            print(f"\n[WEB-UI] >> User launched 'terminal' (PID {pid}) -> Waiting for timeout...")
            d.handle_process_event(ProcessEvent(pid=pid, ppid=1, process_name="terminal", executable="bash", timestamp=now))
        elif action == "custom_process":
            proc_name = payload.get("process_name", "custom_app")
            print(f"\n[WEB-UI] >> Custom process '{proc_name}' launched (PID {pid})")
            d.handle_process_event(ProcessEvent(pid=pid, ppid=1, process_name=proc_name, executable=proc_name, timestamp=now))

    # 2. WebSocket server
    ws_server = LightweightWebSocketServer(host="127.0.0.1", port=8765, on_client_message=handle_client_message)
    ws_server.start()

    def pipeline_callback(step_name: str, payload: any):
        cur_t = time.strftime("%H:%M:%S")
        if step_name == "telemetry_event":
            print(f"[{cur_t}] [TELEMETRY] Process '{payload.process_name}' detected (PID: {payload.pid})")
            ws_server.broadcast_sync("telemetry_event", {
                "pid": payload.pid,
                "process_name": payload.process_name,
                "executable": payload.executable
            })
        elif step_name == "prediction_generated":
            print(f"[{cur_t}] [PREDICT]   Impending '{payload.predicted_process}' | Prob: {payload.probability*100:.1f}% | Conf: {payload.confidence:.2f} | Est Delay: {payload.predicted_delay_seconds:.2f}s")
            ws_server.broadcast_sync("prediction_generated", {
                "source_process": payload.source_process,
                "predicted_process": payload.predicted_process,
                "probability": payload.probability,
                "confidence": payload.confidence,
                "predicted_delay_seconds": payload.predicted_delay_seconds
            })
        elif step_name == "safety_decision":
            status_str = "APPROVED" if payload.approved else f"REJECTED ({', '.join(payload.reasons)})"
            print(f"[{cur_t}] [SAFETY]    Rule Check: {status_str} -> Target Core {payload.target_core}")
            ws_server.broadcast_sync("safety_decision", {
                "approved": payload.approved,
                "rule_name": payload.rule_name,
                "reasons": payload.reasons,
                "target_core": payload.target_core
            })
        elif step_name == "digital_twin_simulation":
            print(f"[{cur_t}] [TWIN-SIM]  Simulation: {payload.simulation_state} (CPU Delta: +{payload.predicted_cpu_delta:.1f}%)")
            ws_server.broadcast_sync("digital_twin_simulation", {
                "approved": payload.approved,
                "simulation_state": payload.simulation_state,
                "predicted_cpu_delta": payload.predicted_cpu_delta,
                "predicted_latency_ms": payload.predicted_latency_ms
            })
        elif step_name == "scheduler_action_applied":
            print(f"[{cur_t}] [CPU-PIN]   AFFINITY LOCKED -> Cores {payload.new_affinity} (PID: {payload.pid})")
            ws_server.broadcast_sync("scheduler_action_applied", {
                "pid": payload.pid,
                "process_name": payload.process_name,
                "previous_affinity": payload.previous_affinity,
                "new_affinity": payload.new_affinity,
                "reason": payload.reason
            })
        elif step_name == "feedback_success":
            print(f"[{cur_t}] [REWARD]    True positive verified for '{payload.successor_process}' -> Confidence increased to {payload.new_confidence:.2f}")
            ws_server.broadcast_sync("feedback_success", {
                "successor": payload.successor_process,
                "status": "TRUE_POSITIVE (+Reward)",
                "new_confidence": payload.new_confidence
            })
        elif step_name == "feedback_timeout":
            proc_n = payload.action.process_name if hasattr(payload, 'action') else "process"
            print(f"[{cur_t}] [ROLLBACK]  Timeout window expired for '{proc_n}' -> Core affinity restored & penalty applied")
            ws_server.broadcast_sync("feedback_timeout", {
                "successor": proc_n,
                "status": "FALSE_POSITIVE_TIMEOUT (-Rollback)",
                "new_confidence": payload.new_confidence if hasattr(payload, 'new_confidence') else 0.5
            })

    def broadcast_periodic(ws, d):
        while True:
            try:
                edges_payload = []
                for src, targets in d.graph.edges.items():
                    for tgt, edge in targets.items():
                        edges_payload.append({
                            "source": src,
                            "target": tgt,
                            "frequency": edge.frequency,
                            "avg_delay": edge.average_delay_seconds,
                            "confidence": edge.confidence,
                            "success_rate": edge.success_rate
                        })
                ws.broadcast_sync("graph_state", {"edges": edges_payload})

                m = psutil.virtual_memory()
                c = psutil.cpu_percent(interval=None)
                ws.broadcast_sync("hardware_state", {
                    "cpu": round(c, 1),
                    "mem": round(m.percent, 1),
                    "temp": "Normal",
                    "cores": [0, 1]
                })
            except Exception:
                pass
            time.sleep(1.0)

    daemon = ChronoSchedDaemon(db_path=config.db_path, on_pipeline_step=pipeline_callback)
    daemon_holder["daemon"] = daemon

    # Pre-train canonical workflows if database is fresh
    if not daemon.graph.edges:
        print("[+] Initializing baseline developer DAG transition matrix...")
        base_t = time.time() - 3600.0
        for i in range(5):
            t = base_t + (i * 20.0)
            daemon.graph.add_process_event(ProcessEvent(pid=1000+i, ppid=1, process_name="code", executable="code", timestamp=t), current_time=t)
            daemon.graph.add_process_event(ProcessEvent(pid=2000+i, ppid=1000+i, process_name="pylance", executable="pylance", timestamp=t+1.8), current_time=t+1.8)
            daemon.graph.add_process_event(ProcessEvent(pid=3000+i, ppid=1, process_name="build_tool", executable="build_tool", timestamp=t+10.0), current_time=t+10.0)
            daemon.graph.add_process_event(ProcessEvent(pid=4000+i, ppid=3000+i, process_name="gcc", executable="gcc", timestamp=t+11.5), current_time=t+11.5)

    daemon.start()

    t_sync = threading.Thread(target=broadcast_periodic, args=(ws_server, daemon), daemon=True)
    t_sync.start()

    # Auto-open dashboard in browser
    exe_dir = os.path.dirname(os.path.abspath(sys.executable if getattr(sys, 'frozen', False) else __file__))
    possible_paths = [
        os.path.join(exe_dir, "Dashboard.html"),
        os.path.abspath("Dashboard.html"),
        os.path.abspath("frontend/index.html"),
        os.path.join(exe_dir, "frontend", "index.html"),
        os.path.join(os.path.dirname(__file__), "..", "frontend", "index.html"),
        os.path.join(getattr(sys, "_MEIPASS", ""), "frontend", "index.html")
    ]
    html_path = next((p for p in possible_paths if os.path.exists(p)), None)
    if html_path:
        print(f"[+] Opening Live Visual Dashboard: file://{html_path}")
        webbrowser.open(f"file://{html_path}")

    print("\n" + "-" * 76)
    print("  COMMAND PROMPT INTERACTIVE CONTROLS:")
    print("   [1] Simulate 'code' launch      -> Predicts 'pylance' -> Preemptively Pins Core")
    print("   [2] Simulate 'pylance' launch   -> Verifies Success -> Triggers Reward (+Confidence)")
    print("   [3] Simulate 'terminal' launch  -> Triggers Timeout -> Rollback Watchdog (-Penalty)")
    print("   [4] Inspect Learned DAG Dependency Graph & Probability Matrix")
    print("   [5] Run Full Empirical Benchmark Evaluation")
    print("   [M] Background Monitoring Mode (watches real operating system processes)")
    print("   [Q] Quit ChronoScheduler")
    print("-" * 76 + "\n")

    while True:
        try:
            cmd = input("ChronoSched> ").strip()
            now = time.time()
            if not cmd:
                continue
            if cmd == "1":
                print("\n>>> [TRIGGER] User launched 'code' (PID 8812)")
                daemon.handle_process_event(ProcessEvent(pid=8812, ppid=1, process_name="code", executable="code", timestamp=now))
            elif cmd == "2":
                print("\n>>> [TRIGGER] Impending process 'pylance' launched (PID 8813)")
                daemon.handle_process_event(ProcessEvent(pid=8813, ppid=8812, process_name="pylance", executable="pylance", timestamp=now))
            elif cmd == "3":
                print("\n>>> [TRIGGER] User launched 'terminal' (PID 9901) -> Waiting for timeout...")
                daemon.handle_process_event(ProcessEvent(pid=9901, ppid=1, process_name="terminal", executable="bash", timestamp=now))
            elif cmd == "4":
                cmd_inspect(args)
            elif cmd == "5":
                cmd_bench(argparse.Namespace(iterations=20))
            elif cmd.lower() == "m":
                print("\n>>> Monitoring live OS process spawns in background. Press Enter or Ctrl+C to return to menu.")
                try:
                    input()
                except (KeyboardInterrupt, EOFError):
                    pass
            elif cmd.lower() == "q":
                break
            else:
                print(f"Unknown command '{cmd}'. Available: 1, 2, 3, 4, 5, M, Q")
        except (KeyboardInterrupt, EOFError):
            break

    daemon.stop()
    print("\n[+] ChronoSched shutdown complete. All CPU affinities restored.")

def main():
    parser = argparse.ArgumentParser(prog="chronosched", description="ChronoScheduler: Preemptive CPU Resource Allocation Daemon")
    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # Demo / Default
    p_demo = subparsers.add_parser("demo", help="Run interactive live demo & open dashboard")

    # Run
    p_run = subparsers.add_parser("run", help="Run the ChronoSched daemon in background")

    # Bench
    p_bench = subparsers.add_parser("bench", help="Run the empirical latency & accuracy benchmark")
    p_bench.add_argument("--iterations", type=int, default=30, help="Number of benchmark iterations per workload")

    # Inspect
    p_inspect = subparsers.add_parser("inspect", help="Inspect learned DAG dependency edges")

    # Profiles
    p_prof = subparsers.add_parser("profiles", help="Inspect learned Digital Twin process profiles")

    # If launched with no arguments (e.g. double clicked .exe), default to demo!
    if len(sys.argv) == 1:
        cmd_demo()
        return

    args = parser.parse_args()
    if args.command == "demo":
        cmd_demo(args)
    elif args.command == "run":
        cmd_run(args)
    elif args.command == "bench":
        cmd_bench(args)
    elif args.command == "inspect":
        cmd_inspect(args)
    elif args.command == "profiles":
        cmd_profiles(args)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
