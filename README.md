# ⏱️ ChronoScheduler: Predictive CPU Resource Allocation & Digital Twin

[![CI Test Suite](https://github.com/shrishabarish/ChronoScheduler/actions/workflows/ci.yml/badge.svg)](https://github.com/shrishabarish/ChronoScheduler/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![Linux](https://img.shields.io/badge/platform-Linux-lightgrey.svg)](https://www.kernel.org/)

**ChronoScheduler** is an intelligent, low-overhead Linux process scheduling daemon that anticipates process launches and proactively configures CPU core affinities (`sched_setaffinity`) and priority (`nice`) **before** execution bottlenecks occur.

By combining an **Online Temporal Dependency Graph (DAG)**, **Neuro-Symbolic Safety Rules**, a **Digital Twin Pre-Execution Simulator**, and an **Automatic Rollback Watchdog**, ChronoScheduler cuts initialization latency while preventing core saturation and thermal throttling.

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

## 📊 Benchmark Results

Evaluated against synthetic and real-world multi-stage developer workflow traces:

| Metric | Measured Value | Target | Status |
| :--- | :--- | :--- | :--- |
| **Prediction Accuracy** | **93.44%** | $\ge 85.0\%$ | ✅ Passed |
| **Precision** | **86.78%** | $\ge 80.0\%$ | ✅ Passed |
| **Recall** | **100.0%** | $\ge 90.0\%$ | ✅ Passed |
| **False Negative Rate** | **0.0%** | $\le 10.0\%$ | ✅ Passed |
| **Inference Latency** | **0.008 ms** | $\le 1.0\text{ ms}$ | ✅ Passed |

---

## 🚀 Quick Start

### 1. Prerequisites
- **OS**: Linux (tested on Ubuntu 20.04+, Debian, Fedora, Arch)
- **Python**: Python 3.9 or higher

### 2. Installation
```bash
# Clone the repository
git clone https://github.com/shrishabarish/ChronoScheduler.git
cd ChronoScheduler

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Run the Interactive Live Demo & Web Dashboard
```bash
python3 scripts/run_live_demo.py
```
Open [`frontend/index.html`](file:///home/vboxuser/Desktop/ChronoScheduler/frontend/index.html) in your web browser to view the real-time visual dashboard and graph inspector.

### 4. Run Benchmark Suite
```bash
python3 scripts/run_benchmark.py
```

### 5. Run Automated Tests
```bash
python3 -m unittest discover -s tests -p "test_*.py"
```

---

## 📁 Repository Structure

```
ChronoScheduler/
├── .github/
│   └── workflows/
│       └── ci.yml                 # GitHub Actions CI workflow
├── backend/
│   ├── daemon.py                  # Standalone lightweight eBPF daemon
│   └── requirements.txt           # Backend package requirements
├── config/                        # Configuration settings
├── data/                          # SQLite event storage (gitignored)
├── frontend/
│   └── index.html                 # Glassmorphic real-time Web Dashboard
├── results/
│   └── benchmark_summary.json     # Benchmark evaluation metrics
├── scripts/
│   ├── run_benchmark.py           # Benchmark runner
│   └── run_live_demo.py           # Interactive CLI & WebSocket live demo
├── src/
│   ├── core/                      # Configuration, models, and SQLite store
│   ├── engine/                    # Prediction, Confidence, Safety, Twin, Rollback
│   ├── graph/                     # Temporal dependency graph DAG
│   ├── server/                    # Lightweight RFC 6455 WebSocket server
│   ├── telemetry/                 # psutil & eBPF process listeners
│   ├── validation/                # Validation traces and metrics generator
│   └── daemon.py                  # ChronoSched closed-loop daemon
├── tests/                         # Full automated test suite (21 tests)
├── .gitignore                     # Git ignore rules
├── CONTRIBUTING.md                # Contribution guidelines
├── LICENSE                        # MIT License
├── pyproject.toml                 # Package setup configuration
├── README.md                      # Project documentation
└── requirements.txt               # Root Python dependencies
```

---

## ⚙️ Configuration Options

Parameters can be adjusted in [`src/core/config.py`](file:///home/vboxuser/Desktop/ChronoScheduler/src/core/config.py) or via environment variables:

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
