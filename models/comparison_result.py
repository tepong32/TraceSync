from dataclasses import dataclass

from models.compare_status import CompareStatus


@dataclass(slots=True)
class ComparisonResult:
    relative_path: str
    status: CompareStatus