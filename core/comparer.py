from models.comparison_result import ComparisonResult


LOCAL_NEWER = "Local Newer"
SERVER_NEWER = "Server Newer"
SAME = "Same"
LOCAL_ONLY = "Local Only"
SERVER_ONLY = "Server Only"


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
            results.append(
                ComparisonResult(
                    relative_path=relative_path,
                    status=LOCAL_ONLY,
                )
            )
            continue

        if server_record and not local_record:
            results.append(
                ComparisonResult(
                    relative_path=relative_path,
                    status=SERVER_ONLY,
                )
            )
            continue

        if local_record.modified_time > server_record.modified_time:
            status = LOCAL_NEWER

        elif server_record.modified_time > local_record.modified_time:
            status = SERVER_NEWER

        else:
            status = SAME

        results.append(
            ComparisonResult(
                relative_path=relative_path,
                status=status,
            )
        )

    return results