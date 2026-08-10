from dataclasses import dataclass
from enum import Enum

from models.compare_status import CompareStatus


class ConfidenceLevel(str, Enum):
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


@dataclass(slots=True)
class ComparisonDecision:
    recommendation: str
    confidence: ConfidenceLevel
    reason: str
    status: CompareStatus
