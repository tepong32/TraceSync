from dataclasses import dataclass


@dataclass(slots=True)
class ComparisonResult:
    relative_path: str
    status: str