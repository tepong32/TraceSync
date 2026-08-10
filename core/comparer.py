from models.compare_status import CompareStatus
from models.comparison_result import ComparisonResult
from core.comparison_confidence import build_decision


def compare_folders(
    local_files: dict,
    server_files: dict,
) -> list[ComparisonResult]:
    """
    Compare two scanned folders and return comparison results.
    """

    results = []

    all_paths = set(local_files.keys()) | set(server_files.keys())

    for relative_path in sorted(all_paths):

        local_record = local_files.get(relative_path)
        server_record = server_files.get(relative_path)

        if local_record and not server_record:
            result = ComparisonResult(
                relative_path=relative_path,
                status=CompareStatus.LOCAL_ONLY,
                local_record=local_record,
                server_record=None,
            )
            result.decision = build_decision(result)
            results.append(result)
            continue

        if server_record and not local_record:
            result = ComparisonResult(
                relative_path=relative_path,
                status=CompareStatus.SERVER_ONLY,
                local_record=None,
                server_record=server_record,
            )
            result.decision = build_decision(result)
            results.append(result)
            continue

        if local_record.modified_time > server_record.modified_time:
            status = CompareStatus.LOCAL_NEWER

        elif server_record.modified_time > local_record.modified_time:
            status = CompareStatus.SERVER_NEWER

        else:
            status = CompareStatus.SAME

        result = ComparisonResult(
            relative_path=relative_path,
            status=status,
            local_record=local_record,
            server_record=server_record,
        )
        result.decision = build_decision(result)
        results.append(result)

    return results
