import os
import time
import json
import asyncio
import websockets
from bcc import BPF

# [Kernel Engineer]: Strict eBPF C program embedded for BCC JIT compilation
bpf_text = """
#include <uapi/linux/ptrace.h>
#include <linux/sched.h>
#include <linux/fs.h>

#define MAX_FNAME_LEN 256
#define MAX_COMM_LEN 16

struct exec_telemetry_event {
    u32 pid;
    u32 tgid;
    u32 uid;
    char comm[MAX_COMM_LEN];
    char fname[MAX_FNAME_LEN];
};

BPF_PERF_OUTPUT(exec_events);

int hook_sys_execve(struct pt_regs *ctx, 
                    const char __user *filename,
                    const char __user *const __user *argv,
                    const char __user *const __user *envp) 
{
    struct exec_telemetry_event event = {};
    
    u64 id = bpf_get_current_pid_tgid();
    event.pid = id >> 32;
    event.tgid = id;
    event.uid = bpf_get_current_uid_gid();
    
    if (bpf_get_current_comm(&event.comm, sizeof(event.comm)) != 0) {
        return 0; 
    }
    
    if (bpf_probe_read_user_str(&event.fname, sizeof(event.fname), (void *)filename) < 0) {
        return 0;
    }
    
    exec_events.perf_submit(ctx, &event, sizeof(event));
    return 0;
}
"""

# [AI/Systems Architect]: Daemon logic
connected_clients = set()

async def broadcast(message):
    if connected_clients:
        await asyncio.gather(*(client.send(json.dumps(message)) for client in connected_clients))

def process_bpf_events(loop):
    print("Compiling eBPF program...")
    try:
        b = BPF(text=bpf_text)
        b.attach_kprobe(event=b.get_syscall_fnname("execve"), fn_name="hook_sys_execve")
        print("eBPF program attached. Listening for execve (target: 'sleep')...")
    except Exception as e:
        print(f"Error loading BPF. Are you running as root? Error: {e}")
        return

    def print_event(cpu, data, size):
        event = b["exec_events"].event(data)
        cmd = event.comm.decode('utf-8', 'replace')
        fname = event.fname.decode('utf-8', 'replace')
        pid = event.pid
        
        # MVP Logic: Intercept only 'sleep' commands to avoid terminal noise
        if cmd == "sleep":
            target_core = 1
            action = f"PyReason: Confidence 0.98 -> Affining to Core {target_core}"
            try:
                os.sched_setaffinity(pid, {target_core})
                success = True
            except Exception as e:
                action = f"Failed to affine: {e}"
                success = False

            payload = {
                "timestamp": time.strftime("%H:%M:%S"),
                "pid": pid,
                "command": cmd,
                "file": fname,
                "action": action,
                "success": success,
                "core": target_core if success else None
            }
            print(f"Intercepted: {payload}")
            asyncio.run_coroutine_threadsafe(broadcast(payload), loop)

    b["exec_events"].open_perf_buffer(print_event)

    # Poll ring buffer
    while True:
        try:
            b.perf_buffer_poll(timeout=100) # Poll with small timeout
        except KeyboardInterrupt:
            exit()

async def handler(websocket, path="/"):
    connected_clients.add(websocket)
    try:
        await websocket.wait_closed()
    finally:
        connected_clients.remove(websocket)

async def main():
    loop = asyncio.get_running_loop()
    
    server = await websockets.serve(handler, "localhost", 8765)
    print("WebSocket Server started on ws://localhost:8765")
    
    # Run the blocking BPF poll in a separate thread
    await loop.run_in_executor(None, process_bpf_events, loop)

if __name__ == "__main__":
    if os.geteuid() != 0:
        print("ERROR: This script must be run as root (sudo) for eBPF kernel hooking.")
        exit(1)
    asyncio.run(main())
