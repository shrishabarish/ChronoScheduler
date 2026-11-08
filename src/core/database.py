import os
import sqlite3
import json
import time
from typing import List, Optional, Dict, Any
from .models import (
    ProcessEvent, DependencyEdge, PredictionResult,
    SchedulerAction, FeedbackEvent, HardwareSnapshot
)

class EventStore:
    def __init__(self, db_path: str = ":memory:"):
        self.db_path = db_path
        self._conn = None
        if self.db_path == ":memory:":
            self._conn = sqlite3.connect(":memory:", check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        if self._conn is not None:
            return self._conn
        if self.db_path != ":memory:":
            db_dir = os.path.dirname(self.db_path)
            if db_dir:
                os.makedirs(db_dir, exist_ok=True)
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # M2 Table: process_events
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS process_events (
                event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                pid INTEGER NOT NULL,
                ppid INTEGER NOT NULL,
                process_name TEXT NOT NULL,
                executable TEXT NOT NULL,
                timestamp REAL NOT NULL,
                cpu_percent REAL,
                memory_rss_bytes INTEGER,
                cpu_affinity TEXT,
                process_state TEXT,
                parent_name TEXT,
                source TEXT
            )
            """)

            # M2 Table: dependency_edges
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS dependency_edges (
                edge_id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_process TEXT NOT NULL,
                target_process TEXT NOT NULL,
                frequency INTEGER DEFAULT 1,
                total_delay_seconds REAL DEFAULT 0.0,
                average_delay_seconds REAL DEFAULT 0.0,
                success_count INTEGER DEFAULT 0,
                failure_count INTEGER DEFAULT 0,
                success_rate REAL DEFAULT 1.0,
                recency_timestamp REAL NOT NULL,
                prediction_probability REAL DEFAULT 0.0,
                confidence REAL DEFAULT 0.0,
                UNIQUE(source_process, target_process)
            )
            """)

            # M2 Table: predictions
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS predictions (
                prediction_id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_process TEXT NOT NULL,
                predicted_process TEXT NOT NULL,
                probability REAL NOT NULL,
                confidence REAL NOT NULL,
                expected_delay_seconds REAL NOT NULL,
                timestamp REAL NOT NULL
            )
            """)

            # M2 Table: scheduler_actions
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS scheduler_actions (
                action_id INTEGER PRIMARY KEY AUTOINCREMENT,
                pid INTEGER NOT NULL,
                process_name TEXT NOT NULL,
                previous_priority INTEGER NOT NULL,
                new_priority INTEGER NOT NULL,
                previous_affinity TEXT NOT NULL,
                new_affinity TEXT NOT NULL,
                reason TEXT NOT NULL,
                confidence REAL NOT NULL,
                timestamp REAL NOT NULL,
                applied INTEGER DEFAULT 0,
                rolled_back INTEGER DEFAULT 0
            )
            """)

            # M2 Table: feedback_events
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS feedback_events (
                feedback_id INTEGER PRIMARY KEY AUTOINCREMENT,
                action_id INTEGER NOT NULL,
                predicted_process TEXT NOT NULL,
                actual_process TEXT,
                success INTEGER NOT NULL,
                latency_observed_ms REAL NOT NULL,
                timestamp REAL NOT NULL
            )
            """)

            # M2 Table: hardware_snapshots
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS hardware_snapshots (
                snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
                cpu_percent_total REAL NOT NULL,
                cpu_percent_per_core TEXT NOT NULL,
                memory_percent REAL NOT NULL,
                memory_available_bytes INTEGER NOT NULL,
                thermal_throttled INTEGER NOT NULL,
                battery_saver_active INTEGER NOT NULL,
                timestamp REAL NOT NULL
            )
            """)

            # Digital Twin Table: process_profiles
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS process_profiles (
                process_name TEXT PRIMARY KEY,
                cpu_delta REAL NOT NULL,
                mem_delta_mb REAL NOT NULL,
                latency_ms REAL NOT NULL,
                sample_count INTEGER DEFAULT 1,
                last_updated REAL NOT NULL
            )
            """)
            conn.commit()

    def record_process_event(self, event: ProcessEvent) -> int:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO process_events (
                pid, ppid, process_name, executable, timestamp,
                cpu_percent, memory_rss_bytes, cpu_affinity, process_state,
                parent_name, source
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                event.pid, event.ppid, event.process_name, event.executable,
                event.timestamp, event.cpu_percent, event.memory_rss_bytes,
                json.dumps(event.cpu_affinity), event.process_state,
                event.parent_name, event.source
            ))
            conn.commit()
            event.event_id = cursor.lastrowid
            return event.event_id

    def get_recent_process_events(self, limit: int = 100) -> List[ProcessEvent]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM process_events ORDER BY timestamp DESC LIMIT ?", (limit,))
            rows = cursor.fetchall()
            events = []
            for r in rows:
                events.append(ProcessEvent(
                    event_id=r["event_id"],
                    pid=r["pid"],
                    ppid=r["ppid"],
                    process_name=r["process_name"],
                    executable=r["executable"],
                    timestamp=r["timestamp"],
                    cpu_percent=r["cpu_percent"],
                    memory_rss_bytes=r["memory_rss_bytes"],
                    cpu_affinity=json.loads(r["cpu_affinity"]) if r["cpu_affinity"] else [],
                    process_state=r["process_state"],
                    parent_name=r["parent_name"],
                    source=r["source"]
                ))
            return events

    def upsert_dependency_edge(self, edge: DependencyEdge):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO dependency_edges (
                source_process, target_process, frequency, total_delay_seconds,
                average_delay_seconds, success_count, failure_count,
                success_rate, recency_timestamp, prediction_probability, confidence
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(source_process, target_process) DO UPDATE SET
                frequency=excluded.frequency,
                total_delay_seconds=excluded.total_delay_seconds,
                average_delay_seconds=excluded.average_delay_seconds,
                success_count=excluded.success_count,
                failure_count=excluded.failure_count,
                success_rate=excluded.success_rate,
                recency_timestamp=excluded.recency_timestamp,
                prediction_probability=excluded.prediction_probability,
                confidence=excluded.confidence
            """, (
                edge.source_process, edge.target_process, edge.frequency,
                edge.total_delay_seconds, edge.average_delay_seconds,
                edge.success_count, edge.failure_count, edge.success_rate,
                edge.recency_timestamp, edge.prediction_probability, edge.confidence
            ))
            conn.commit()

    def get_all_dependency_edges(self) -> List[DependencyEdge]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM dependency_edges")
            rows = cursor.fetchall()
            edges = []
            for r in rows:
                edges.append(DependencyEdge(
                    edge_id=r["edge_id"],
                    source_process=r["source_process"],
                    target_process=r["target_process"],
                    frequency=r["frequency"],
                    total_delay_seconds=r["total_delay_seconds"],
                    average_delay_seconds=r["average_delay_seconds"],
                    success_count=r["success_count"],
                    failure_count=r["failure_count"],
                    success_rate=r["success_rate"],
                    recency_timestamp=r["recency_timestamp"],
                    prediction_probability=r["prediction_probability"],
                    confidence=r["confidence"]
                ))
            return edges

    def record_prediction(self, pred: PredictionResult) -> int:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO predictions (
                source_process, predicted_process, probability, confidence,
                expected_delay_seconds, timestamp
            ) VALUES (?, ?, ?, ?, ?, ?)
            """, (
                pred.source_process, pred.predicted_process, pred.probability,
                pred.confidence, pred.expected_delay_seconds, pred.timestamp
            ))
            conn.commit()
            pred.prediction_id = cursor.lastrowid
            return pred.prediction_id

    def record_scheduler_action(self, action: SchedulerAction) -> int:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO scheduler_actions (
                pid, process_name, previous_priority, new_priority,
                previous_affinity, new_affinity, reason, confidence, timestamp,
                applied, rolled_back
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                action.pid, action.process_name, action.previous_priority,
                action.new_priority, json.dumps(action.previous_affinity),
                json.dumps(action.new_affinity), action.reason, action.confidence,
                action.timestamp, 1 if action.applied else 0, 1 if action.rolled_back else 0
            ))
            conn.commit()
            action.action_id = cursor.lastrowid
            return action.action_id

    def update_action_rollback(self, action_id: int):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE scheduler_actions SET rolled_back = 1 WHERE action_id = ?", (action_id,))
            conn.commit()

    def record_feedback(self, fb: FeedbackEvent) -> int:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO feedback_events (
                action_id, predicted_process, actual_process, success,
                latency_observed_ms, timestamp
            ) VALUES (?, ?, ?, ?, ?, ?)
            """, (
                fb.action_id, fb.predicted_process, fb.actual_process,
                1 if fb.success else 0, fb.latency_observed_ms, fb.timestamp
            ))
            conn.commit()
            fb.feedback_id = cursor.lastrowid
            return fb.feedback_id

    def upsert_process_profile(self, process_name: str, cpu_delta: float, mem_delta_mb: float, latency_ms: float):
        process_key = process_name.lower()
        now = time.time()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT cpu_delta, mem_delta_mb, latency_ms, sample_count FROM process_profiles WHERE process_name = ?", (process_key,))
            row = cursor.fetchone()
            if row:
                old_cpu, old_mem, old_lat, count = row["cpu_delta"], row["mem_delta_mb"], row["latency_ms"], row["sample_count"]
                new_count = count + 1
                # Exponential moving average / online cumulative average
                avg_cpu = ((old_cpu * count) + cpu_delta) / new_count
                avg_mem = ((old_mem * count) + mem_delta_mb) / new_count
                avg_lat = ((old_lat * count) + latency_ms) / new_count
                cursor.execute("""
                UPDATE process_profiles SET
                    cpu_delta = ?, mem_delta_mb = ?, latency_ms = ?, sample_count = ?, last_updated = ?
                WHERE process_name = ?
                """, (avg_cpu, avg_mem, avg_lat, new_count, now, process_key))
            else:
                cursor.execute("""
                INSERT INTO process_profiles (
                    process_name, cpu_delta, mem_delta_mb, latency_ms, sample_count, last_updated
                ) VALUES (?, ?, ?, ?, 1, ?)
                """, (process_key, cpu_delta, mem_delta_mb, latency_ms, now))
            conn.commit()

    def get_process_profile(self, process_name: str) -> Optional[Dict[str, float]]:
        process_key = process_name.lower()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT cpu_delta, mem_delta_mb, latency_ms, sample_count FROM process_profiles WHERE process_name = ?", (process_key,))
            row = cursor.fetchone()
            if row:
                return {
                    "cpu_delta": row["cpu_delta"],
                    "mem_delta_mb": row["mem_delta_mb"],
                    "latency_ms": row["latency_ms"],
                    "sample_count": row["sample_count"]
                }
            return None

    def get_all_process_profiles(self) -> Dict[str, Dict[str, float]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT process_name, cpu_delta, mem_delta_mb, latency_ms, sample_count FROM process_profiles")
            rows = cursor.fetchall()
            return {
                r["process_name"]: {
                    "cpu_delta": r["cpu_delta"],
                    "mem_delta_mb": r["mem_delta_mb"],
                    "latency_ms": r["latency_ms"],
                    "sample_count": r["sample_count"]
                }
                for r in rows
            }

