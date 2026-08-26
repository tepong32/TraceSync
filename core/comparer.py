from core.comparison_evidence import have_comparable_hashes, has_reliable_timestamp
from core.storage_provider import ProviderCapability
from models.compare_status import CompareStatus
from models.comparison_result import ComparisonResult
from core.comparison_confidence import build_decision
from models.file_record import FileRecord


_NO_CAPABILITIES: frozenset[ProviderCapability] = frozenset()


def compare_folders(
    local_files: dict[str, FileRecord],
    server_files: dict[str, FileRecord],
    local_capabilities: frozenset[ProviderCapability] | None = None,
    server_capabilities: frozenset[ProviderCapability] | None = None,
) -> list[ComparisonResult]:
    """
    Compare two scanned folders and return comparison results.
    """

    if local_capabilities is None:
        local_capabilities = _NO_CAPABILITIES
    if server_capabilities is None:
        server_capabilities = _NO_CAPABILITIES
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
            result.decision = build_decision(
                result,
                local_capabilities,
                server_capabilities,
            )
            results.append(result)
            continue

        if server_record and not local_record:
            result = ComparisonResult(
                relative_path=relative_path,
                status=CompareStatus.SERVER_ONLY,
                local_record=None,
                server_record=server_record,
            )
            result.decision = build_decision(
                result,
                local_capabilities,
                server_capabilities,
            )
            results.append(result)
            continue

        local_metadata = local_record.metadata
        server_metadata = server_record.metadata
        hashes_available = have_comparable_hashes(
            local_metadata,
            server_metadata,
            local_capabilities,
            server_capabilities,
        )
        if hashes_available and local_metadata.content_hash == server_metadata.content_hash:
            status = CompareStatus.SAME
        elif (
            has_reliable_timestamp(local_metadata, local_capabilities)
            and has_reliable_timestamp(server_metadata, server_capabilities)
        ):
            if local_metadata.modified_time > server_metadata.modified_time:
                status = CompareStatus.LOCAL_NEWER
            elif server_metadata.modified_time > local_metadata.modified_time:
                status = CompareStatus.SERVER_NEWER
            elif hashes_available:
                status = CompareStatus.NEEDS_REVIEW
            else:
                status = CompareStatus.SAME
        else:
            status = CompareStatus.NEEDS_REVIEW

        result = ComparisonResult(
            relative_path=relative_path,
            status=status,
            local_record=local_record,
            server_record=server_record,
        )
        result.decision = build_decision(
            result,
            local_capabilities,
            server_capabilities,
        )
        results.append(result)

    return results
