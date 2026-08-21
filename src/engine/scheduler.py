import os
import time
import psutil
from typing import Optional, List
from ..core.models import SchedulerAction, SafetyDecision, SimulationResult, ProcessEvent
from ..core.database import EventStore

class LinuxSchedulerActionEngine:
    def __init__(self, db: Optional[EventStore] = None):
        self.db = db

    def apply_scheduling_action(
        self,
        event: ProcessEvent,
        safety_decision: SafetyDecision,
        simulation_result: SimulationResult,
        confidence: float
    ) -> Optional[SchedulerAction]:
        """
        Executes OS-level scheduling primitives (sched_setaffinity, renice)
        ONLY if safety and simulation passed.
        """
        if not safety_decision.approved or not simulation_result.approved:
            return None

        pid = event.pid
        prev_affinity = [0, 1]
        prev_nice = 0
        real_process = True
        try:
            p = psutil.Process(pid)
            prev_affinity = p.cpu_affinity() if hasattr(p, "cpu_affinity") else [0, 1]
            prev_nice = p.nice()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            real_process = False

        target_core = safety_decision.target_core if safety_decision.target_core is not None else 0
        new_affinity = [target_core]
        new_nice = safety_decision.recommended_nice

        action = SchedulerAction(
            pid=pid,
            process_name=event.process_name,
            previous_priority=prev_nice,
            new_priority=new_nice,
            previous_affinity=prev_affinity,
            new_affinity=new_affinity,
            reason=f"Preemptive allocation: {safety_decision.rule_name} (Twin: {simulation_result.simulation_state})",
            confidence=confidence,
            timestamp=time.time(),
            applied=True,
            rolled_back=False
        )

        if real_process:
            try:
                # 1. Apply CPU affinity
                if hasattr(os, "sched_setaffinity"):
                    os.sched_setaffinity(pid, set(new_affinity))
                elif hasattr(p, "cpu_affinity"):
                    p.cpu_affinity(new_affinity)

                # 2. Apply nice priority if permissible
                try:
                    p.nice(new_nice)
                except (psutil.AccessDenied, PermissionError):
                    pass
            except Exception as e:
                action.applied = False
                action.reason += f" | Execution error: {e}"

        if self.db:
            self.db.record_scheduler_action(action)

        return action

    def rollback_action(self, action: SchedulerAction) -> bool:
        """Restores previous affinity and nice priority."""
        if not action.applied or action.rolled_back:
            return False

        try:
            p = psutil.Process(action.pid)
            if action.previous_affinity:
                if hasattr(os, "sched_setaffinity"):
                    os.sched_setaffinity(action.pid, set(action.previous_affinity))
                elif hasattr(p, "cpu_affinity"):
                    p.cpu_affinity(action.previous_affinity)

            try:
                p.nice(action.previous_priority)
            except Exception:
                pass

            action.rolled_back = True
            if self.db and action.action_id:
                self.db.update_action_rollback(action.action_id)
            return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            action.rolled_back = True
            return True
