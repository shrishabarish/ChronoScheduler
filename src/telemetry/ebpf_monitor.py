import os
import time
import threading
from typing import Callable, Optional
from .base import BaseTelemetry
from ..core.models import ProcessEvent

# Embedded eBPF C program adhering strictly to Principal Kernel Engineer constraints
EBPF_EXECVE_C = """
#include <uapi/linux/ptrace.h>
#include <linux/sched.h>
#include <linux/fs.h>

#define MAX_FNAME_LEN 256
#define MAX_COMM_LEN 16

/* Strict explicit struct definition (Never use typedefs) */
struct exec_telemetry_event {
    u32 pid;
    u32 tgid;
    u32 uid;
    char comm[MAX_COMM_LEN];
    char fname[MAX_FNAME_LEN];
};

/* BPF Perf Ring Buffer for asynchronous user-space delivery */
BPF_PERF_OUTPUT(exec_events);

int hook_sys_execve(struct pt_regs *ctx, 
                    const char __user *filename,
                    const char __user *const __user *argv,
                    const char __user *const __user *envp) 
{
    /* Static allocation on BPF stack (Zero malloc/calloc) */
    struct exec_telemetry_event event = {};
    
    u64 id = bpf_get_current_pid_tgid();
    event.pid = id >> 32;
    event.tgid = id;
    event.uid = bpf_get_current_uid_gid();
    
    /* Safely read process command name */
    if (bpf_get_current_comm(&event.comm, sizeof(event.comm)) != 0) {
        bpf_trace_printk("ChronoSched: Failed to read comm for PID %d\\n", event.pid);
        return 0; /* Safe return, no exit */
    }
    
    /* Safely read binary filename being executed */
    if (bpf_probe_read_user_str(&event.fname, sizeof(event.fname), (void *)filename) < 0) {
        bpf_trace_printk("ChronoSched: Failed to read filename for PID %d\\n", event.pid);
        return 0; /* Safe return, no exit */
    }
    
    /* Submit event to perf ring buffer */
    exec_events.perf_submit(ctx, &event, sizeof(event));
    
    return 0;
}
"""

class EbpfProcessMonitor(BaseTelemetry):
    """
    Phase B: eBPF Kernel Telemetry Provider.
    Attaches to sys_execve syscall via BCC ring buffer for zero-latency kernel event capture.
    """
    def __init__(self):
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._bpf = None

    def start(self, callback: Callable[[ProcessEvent], None]):
        if self._running:
            return

        # Check for root privilege
        if os.geteuid() != 0:
            print("[eBPF Monitor] Warning: eBPF requires root (sudo). Falling back gracefully.")
            return

        try:
            from bcc import BPF
            self._bpf = BPF(text=EBPF_EXECVE_C)
            fn_name = self._bpf.get_syscall_fnname("execve")
            self._bpf.attach_kprobe(event=fn_name, fn_name="hook_sys_execve")
            print(f"[eBPF Monitor] Attached probe to {fn_name} successfully.")
        except Exception as e:
            print(f"[eBPF Monitor] Error initializing BPF: {e}")
            return

        def _perf_event_handler(cpu, data, size):
            event = self._bpf["exec_events"].event(data)
            cmd = event.comm.decode("utf-8", "replace").strip("\x00")
            fname = event.fname.decode("utf-8", "replace").strip("\x00")
            
            proc_event = ProcessEvent(
                pid=event.pid,
                ppid=1,
                process_name=cmd,
                executable=fname or cmd,
                timestamp=time.time(),
                source="ebpf_ringbuffer"
            )
            callback(proc_event)

        self._bpf["exec_events"].open_perf_buffer(_perf_event_handler)
        self._running = True

        def _poll_loop():
            while self._running:
                try:
                    self._bpf.perf_buffer_poll(timeout=50)
                except Exception:
                    pass

        self._thread = threading.Thread(target=_poll_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        self._bpf = None
