# Contributing to ChronoScheduler

Thank you for your interest in contributing to **ChronoScheduler**! We welcome bug reports, feature suggestions, documentation enhancements, and pull requests.

---

## Development Setup

1. **Clone the Repository**:
   ```bash
   git clone https://github.com/shrishabarish/ChronoScheduler.git
   cd ChronoScheduler
   ```

2. **Create a Virtual Environment**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Run the Test Suite**:
   ```bash
   python3 -m unittest discover -s tests
   ```

---

## Project Architecture Overview

ChronoScheduler implements a closed-loop Form-B runtime pipeline:
- **`src/telemetry/`**: Monitors process lifecycles via `psutil` or eBPF.
- **`src/graph/`**: Maintains dynamic online Temporal Dependency Graphs (DAG).
- **`src/engine/`**: Handles prediction, confidence gating, neuro-symbolic safety rules, digital twin hardware pre-simulation, Linux CPU affinity allocation, and rollback/feedback verification.
- **`src/server/`**: Zero-dependency RFC 6455 WebSocket server for real-time visualization.
- **`frontend/`**: Live glassmorphic web dashboard for real-time telemetry streaming.

---

## Submitting Pull Requests

1. Create a feature branch (`git checkout -b feature/your-feature-name`).
2. Implement your changes following existing code style.
3. Ensure all tests pass (`python3 -m unittest discover tests`).
4. Commit your changes with clear, descriptive commit messages.
5. Push to your fork and open a Pull Request against `main`.
