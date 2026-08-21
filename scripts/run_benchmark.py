#!/usr/bin/env python3
import sys
import os
import json

# Ensure project root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.validation.benchmark import BenchmarkRunner

def main():
    print("=" * 60)
    print("CHRONOSCHED FORM-B VALIDATION & ACCURACY BENCHMARK")
    print("=" * 60)
    print("Target Requirement: >= 80% Prediction Accuracy\n")

    runner = BenchmarkRunner(train_split=0.70)
    results = runner.run_benchmark(num_sessions=80, seed=42)

    print(f"Total Validation Events : {results['total_events_evaluated']}")
    print(f"Prediction Accuracy     : {results['accuracy_percent']}%  (Target: >= 80.0%)")
    print(f"Precision               : {results['precision']:.4f}")
    print(f"Recall                  : {results['recall']:.4f}")
    print(f"False Positive Rate     : {results['false_positive_rate']:.4f}")
    print(f"False Negative Rate     : {results['false_negative_rate']:.4f}")
    print(f"Average Latency         : {results['average_latency_ms']} ms")
    print("=" * 60)
    
    if results["target_met"]:
        print(">>> STATUS: BENCHMARK PASSED (Accuracy >= 80% Achieved)")
    else:
        print(">>> STATUS: BENCHMARK FAILED")
    print("=" * 60)

    # Persist benchmark result in results/
    os.makedirs("/home/vboxuser/Desktop/ChronoScheduler/results", exist_ok=True)
    with open("/home/vboxuser/Desktop/ChronoScheduler/results/benchmark_summary.json", "w") as f:
        json.dump(results, f, indent=2)

if __name__ == "__main__":
    main()
