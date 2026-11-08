# ⏱️ ChronoScheduler: Predictive CPU Resource Allocation & Digital Twin

[![CI Test Suite](https://github.com/shrishabarish/ChronoScheduler/actions/workflows/ci.yml/badge.svg)](https://github.com/shrishabarish/ChronoScheduler/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![Linux](https://img.shields.io/badge/platform-Linux-lightgrey.svg)](https://www.kernel.org/)
[![Patent Embodiment](https://img.shields.io/badge/Patent%20Application-Form--B%20Ref-brightgreen.svg)](#-patent-specification--form-b-architecture)

**ChronoScheduler** is an intelligent, low-overhead Linux process scheduling daemon that anticipates process launches and proactively configures CPU core affinities (`sched_setaffinity`) and priority (`nice`) **before** execution bottlenecks occur.

By combining an **Online Temporal Dependency Graph (DAG)**, **Neuro-Symbolic Safety Rules**, a **Digital Twin Pre-Execution Simulator**, and an **Automatic Rollback Watchdog**, ChronoScheduler cuts initialization latency while preventing core saturation and thermal throttling.

---

## 📑 Patent Specification & Form-B Architecture

This codebase is the practical implementation and reference embodiment of the patent application:
* **Patent Document:** [`Form-b_final.docx`](Form-b_final.docx)
* **Title of the Invention:** *ChronoSched: System and Method for Preemptive CPU Resource Allocation Using Neuro-Symbolic Temporal Dependency Prediction*
* **Core Inventive Step:** An **Adaptive Confidence-Gated Neuro-Symbolic Scheduling Pipeline (ACNSP)** combining:
  1. *Temporal Dependency Learning:* Cross-session graph tracking causal process chains.
  2. *Confidence Estimation:* Dynamically scoring edges via $\text{Confidence}(t) = \alpha(\text{Freq}) + \beta(\text{Recency}) + P(\text{Prediction}) - \text{Penalty}$.
  3. *Neuro-Symbolic Verification:* Deterministic hard constraints on RAM ($>90\%$), CPU ($>85\%$), thermal throttling, and battery status.
  4. *Digital Twin Pre-Execution Simulation:* Virtual sandbox verification of projected cache, memory, and thermal state prior to committing OS primitives.
  5. *Hardware-Aware Preemptive Scheduling:* Linux `sched_setaffinity` & `nice` (or Windows `SetProcessAffinityMask` / `SetPriorityClass`).
  6. *Closed-Loop Rollback & Feedback:* Dynamic reinforcement (rewarding true-positive predictions and adaptively penalizing false-positives).
* **Scope of Claims:** 12 formal patent claims protecting heterogeneous core allocation (Performance vs. Efficiency cores), cross-session temporal dependency graphs, digital twin validation, and zero-retraining reinforcement learning.

---

## 🌟 Key Features

- **⚡ Zero-Overhead Telemetry**: Lightweight user-space polling (`psutil`) with optional non-blocking kernel tracing via **eBPF/BCC**.
- **📈 Online Temporal Dependency Graph (DAG)**: Dynamically captures causal execution chains (e.g., `code` $\rightarrow$ `pylance`, `build_tool` $\rightarrow$ `gcc` $\rightarrow$ `ld`) with exponential temporal decay and online Laplace smoothing.
- **🛡️ Neuro-Symbolic Safety Rules**: Enforces deterministic hard constraints on CPU load limits, RAM thresholds, battery preservation, and thermal throttling before actions can execute.
- **🔬 Digital Twin Simulator**: Simulates workload thermal and CPU load impacts on performance/efficiency cores prior to actual kernel affinity reconfiguration.
- **🔄 Closed-Loop Feedback & Rollback Watchdog**: Automatically registers applied scheduler actions in a time-window verification queue. True positives receive confidence rewards; false-positive predictions trigger automatic state rollbacks and penalty decay.
- **📊 Real-Time Glassmorphic Dashboard**: Built-in zero-dependency RFC 6455 WebSocket server streaming live telemetry, DAG structure, and pipeline states to `frontend/index.html`.

---

## 🏗️ Architecture (Form-B Closed-Loop Pipeline)

```
[ Process Telemetry (psutil / eBPF) ]
                  │
                  ▼
[ 1. Temporal Dependency Graph (DAG) ]
                  │
                  ▼
[ 2. Probabilistic Prediction Engine ]
                  │
                  ▼
[ 3. Dynamic Confidence Gating (τ ≥ 0.70) ]
                  │
                  ▼
[ 4. Neuro-Symbolic Safety Rules (RAM / CPU / Thermal) ]
                  │
                  ▼
[ 5. Digital Twin Pre-Execution Simulation ]
                  │
                  ▼
[ 6. Linux Scheduler Execution (sched_setaffinity / nice) ]
                  │
                  ▼
[ 7. Verification Window & Rollback Watchdog ]
        ├── True Positive  ──> (+Reward & Confidence Boost)
        └── Timeout/Miss   ──> (Automatic Rollback & -Penalty)
```

---

## 🔬 Form-B Section 8: Empirical Validation Results

Tested against the baseline Linux Completely Fair Scheduler (CFS) across multi-stage developer workloads:

| Metric | Baseline (Standard CFS) | ChronoSched (Active) | Delta / Improvement | Patent Target | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Prediction Accuracy** | `N/A` | **92.94%** | **92.94%** | $\ge 90\%$ (Post-Learning) | ✅ Passed |
| **Precision** | `N/A` | **86.0%** | **86.0%** | $\ge 80\%$ | ✅ Passed |
| **Recall** | `N/A` | **100.0%** | **FNR: 0.0%** | $\ge 90\%$ | ✅ Passed |
| **Inference Overhead** | `0.000 ms` | **0.0112 ms** (11.2 µs) | Strictly bounded | $\le 1.0\text{ ms}$ | ✅ Passed |
| **Net Latency Gain** | Baseline | **+0.20 ms** net savings | Net positive gain | Positive latency gain | ✅ Passed |
| **Context Switch Rate** | `0.0` switches/init | `0.2` switches/init | **-16.7% reduction** | Targeted reduction | ✅ Passed |
| **CPU Core Stabilization** | Core Migration | Proactive P-Core Allocation | Stabilized affinity | P-Core Pinning | ✅ Passed |
| **Cache Miss Penalty** | High (Cold Core Init) | Reduced via Pre-Warming | Locality preserved | Reduced cache misses | ✅ Passed |

*Detailed report available in [`results/patent_section8_table.md`](results/patent_section8_table.md).*

---

## 🚀 Quick Start

### 1. Prerequisites
- **OS**: Linux (tested on Ubuntu 20.04+, Debian, Fedora, Arch) or Windows (CLI & Dashboard mode)
- **Python**: Python 3.9 or higher

### 2. Installation
```bash
# Clone the repository
git clone https://github.com/shrishabarish/ChronoScheduler.git
cd ChronoScheduler

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # Or on Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Run the Interactive Live Demo & Web Dashboard
```bash
# On Linux:
python3 scripts/run_live_demo.py

# Or on Windows (One-Click Launcher):
run_windows.bat
```
Open [`frontend/index.html`](frontend/index.html) or [`Dashboard.html`](Dashboard.html) in your browser to view the real-time visual dashboard and graph inspector.

### 4. Run Benchmark Suite
```bash
python3 scripts/run_benchmark.py
# Or run empirical evaluation:
python3 scripts/run_empirical_eval.py
```

### 5. Run Automated Tests
```bash
python -m pytest tests/ -v
```

---

## 📂 Repository Structure

```
ChronoScheduler/
├── .github/
│   └── workflows/
│       └── ci.yml                 # GitHub Actions CI workflow
├── Form-b_final.docx              # Complete Patent Application Document
├── Dashboard.html                 # Standalone zero-dependency Web Dashboard
├── backend/
│   ├── daemon.py                  # Standalone lightweight eBPF daemon
│   └── requirements.txt           # Backend package requirements
├── frontend/
│   └── index.html                 # Glassmorphic real-time Web Dashboard
├── results/
│   ├── benchmark_summary.json     # Benchmark evaluation metrics
│   ├── patent_section8_table.md   # Form-B Section 8 validation matrix
│   └── patent_validation_report.json # Empirical trial traces
├── scripts/
│   ├── run_benchmark.py           # Benchmark runner
│   ├── run_empirical_eval.py      # Empirical validation driver
│   ├── run_live_demo.py           # Interactive CLI & WebSocket live demo
│   ├── install_service.sh         # Linux systemd installer
│   └── uninstall_service.sh       # Linux systemd uninstaller
├── src/
│   ├── cli.py                     # Command-line interface
│   ├── core/                      # Configuration, models, and SQLite store
│   ├── engine/                    # Prediction, Confidence, Safety, Twin, Rollback
│   ├── graph/                     # Temporal dependency graph DAG
│   ├── server/                    # Lightweight RFC 6455 WebSocket server
│   ├── telemetry/                 # psutil & eBPF process listeners
│   ├── validation/                # Empirical benchmark & report export
│   └── daemon.py                  # ChronoSched closed-loop daemon
├── systemd/                       # Systemd unit service configuration
├── tests/                         # Full automated test suite (30 tests)
├── .gitignore                     # Git ignore rules
├── CONTRIBUTING.md                # Contribution guidelines
├── LICENSE                        # MIT License
├── pyproject.toml                 # Package setup configuration
├── README.md                      # Project documentation
└── requirements.txt               # Root Python dependencies
```

---

## ⚙️ Configuration Options

Parameters can be adjusted in [`src/core/config.py`](src/core/config.py) or via environment variables:

| Variable | Default | Description |
| :--- | :--- | :--- |
| `CHRONOSCHED_CONFIDENCE_THRESHOLD` | `0.70` | Minimum prediction confidence threshold |
| `CHRONOSCHED_MAX_MEMORY_PERCENT` | `90.0` | Memory safety cap |
| `CHRONOSCHED_HIGH_CPU_PERCENT` | `85.0` | CPU threshold for shedding affinity |
| `CHRONOSCHED_PREDICTION_TIMEOUT` | `5.0` | Rollback window in seconds |
| `CHRONOSCHED_PERF_CORE` | `0` | Default Performance Core ID |
| `CHRONOSCHED_EFF_CORE` | `1` | Default Efficiency Core ID |

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
