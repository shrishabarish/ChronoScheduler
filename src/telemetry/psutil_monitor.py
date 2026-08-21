import time
import threading
import psutil
from typing import Callable, Set, Optional
from .base import BaseTelemetry
from ..core.models import ProcessEvent

class PsutilProcessMonitor(BaseTelemetry):
    def __init__(self, polling_interval: float = 0.05, filter_kernel_threads: bool = True):
        self.polling_interval = polling_interval
        self.filter_kernel_threads = filter_kernel_threads
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._known_pids: Set[int] = set()
        self._lock = threading.Lock()

    def _is_kernel_thread(self, proc: psutil.Process) -> bool:
        try:
            # On Linux, kernel threads have ppid 2 or ppid 0 (except init/systemd)
            ppid = proc.ppid()
            if ppid == 2 or (ppid == 0 and proc.pid != 1):
                return True
            # Empty cmdline or bracketed name often indicates kernel thread
            name = proc.name()
            if name.startswith("[") and name.endswith("]"):
                return True
            return False
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return True

    def _get_process_event(self, pid: int) -> Optional[ProcessEvent]:
        try:
            p = psutil.Process(pid)
            if self.filter_kernel_threads and self._is_kernel_thread(p):
                return None
            
            try:
                exe = p.exe()
            except (psutil.AccessDenied, psutil.NoSuchProcess):
                exe = p.name()
            
            try:
                affinity = p.cpu_affinity()
            except (psutil.AccessDenied, psutil.NoSuchProcess, AttributeError):
                affinity = []

            try:
                mem_rss = p.memory_info().rss
            except (psutil.AccessDenied, psutil.NoSuchProcess):
                mem_rss = 0

            try:
                parent = p.parent()
                parent_name = parent.name() if parent else None
            except (psutil.AccessDenied, psutil.NoSuchProcess):
                parent_name = None

            return ProcessEvent(
                pid=p.pid,
                ppid=p.ppid(),
                process_name=p.name(),
                executable=exe or p.name(),
                timestamp=time.time(),
                cpu_percent=0.0,
                memory_rss_bytes=mem_rss,
                cpu_affinity=affinity,
                process_state=p.status(),
                parent_name=parent_name,
                source="psutil"
            )
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return None

    def _poll_loop(self, callback: Callable[[ProcessEvent], None]):
        # Initial snapshot of existing PIDs so we only emit NEW processes
        try:
            self._known_pids = set(psutil.pids())
        except Exception:
            self._known_pids = set()

        while self._running:
            try:
                current_pids = set(psutil.pids())
                new_pids = current_pids - self._known_pids
                
                for pid in new_pids:
                    event = self._get_process_event(pid)
                    if event:
                        callback(event)
                
                with self._lock:
                    self._known_pids = current_pids
            except Exception as e:
                pass  # Graceful error handling, never crash
            
            time.sleep(self.polling_interval)

    def start(self, callback: Callable[[ProcessEvent], None]):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._poll_loop, args=(callback,), daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
