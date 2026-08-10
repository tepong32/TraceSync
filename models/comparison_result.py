from dataclasses import dataclass
from models.comparison_decision import ComparisonDecision

from models.compare_status import CompareStatus
from models.file_record import FileRecord


@dataclass(slots=True)
class ComparisonResult:
    relative_path: str
    status: CompareStatus

    local_record: FileRecord | None = None
    server_record: FileRecord | None = None
    decision: ComparisonDecision | None = None
