from typing import Tuple
from ..core.models import PredictionResult, DependencyEdge
from ..core.config import config

class ConfidenceEngine:
    def __init__(self, threshold: float = config.confidence_threshold):
        self.threshold = threshold

    def evaluate_gating(self, prediction: PredictionResult) -> Tuple[bool, str]:
        """
        Determines whether a prediction meets the confidence threshold 
        to proceed to Neuro-Symbolic Safety and Digital Twin simulation.
        """
        if prediction.confidence >= self.threshold:
            return True, f"Confidence {prediction.confidence:.2f} >= threshold {self.threshold:.2f}"
        else:
            return False, f"Confidence {prediction.confidence:.2f} < threshold {self.threshold:.2f} (Rejected by Confidence Gate)"

    def update_confidence_feedback(
        self,
        edge: DependencyEdge,
        success: bool,
        learning_rate: float = config.learning_rate,
        penalty: float = config.failure_penalty
    ):
        """
        Adaptive Confidence Update:
        Confidence(t+1) = Confidence(t) + LearningRate * Reward - Penalty * Failure
        """
        edge.record_feedback(success=success, learning_rate=learning_rate, penalty=penalty)
