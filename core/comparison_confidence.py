from core.comparison_evidence import have_comparable_hashes, has_reliable_timestamp
from core.storage_provider import ProviderCapability
from models.compare_status import CompareStatus
from models.comparison_decision import ComparisonDecision, ConfidenceLevel
from models.comparison_result import ComparisonResult


TIMESTAMP_UNCERTAINTY_SECONDS = 2.0


_NO_CAPABILITIES: frozenset[ProviderCapability] = frozenset()


def build_decision(
    result: ComparisonResult,
    local_capabilities: frozenset[ProviderCapability] | None = None,
    server_capabilities: frozenset[ProviderCapability] | None = None,
) -> ComparisonDecision:
    if local_capabilities is None:
        local_capabilities = _NO_CAPABILITIES
    if server_capabilities is None:
        server_capabilities = _NO_CAPABILITIES
    if result.local_record is None and result.server_record is not None:
        return ComparisonDecision(
            recommendation="Copy Server → Local is likely correct.",
            confidence=ConfidenceLevel.HIGH,
            reason="This file exists on the Server side only.",
            status=result.status,
        )

    if result.server_record is None and result.local_record is not None:
        return ComparisonDecision(
            recommendation="Copy Local → Server is likely correct.",
            confidence=ConfidenceLevel.HIGH,
            reason="This file exists on the Local side only.",
            status=result.status,
        )

    if result.status == CompareStatus.SAME:
        if result.local_record and result.server_record:
            if (
                have_comparable_hashes(
                    result.local_record.metadata,
                    result.server_record.metadata,
                    local_capabilities,
                    server_capabilities,
                )
                and result.local_record.metadata.content_hash
                == result.server_record.metadata.content_hash
            ):
                return ComparisonDecision(
                    recommendation="No action is likely required.",
                    confidence=ConfidenceLevel.HIGH,
                    reason="The provider-reported content hashes match.",
                    status=result.status,
                )
            if (
                has_reliable_timestamp(
                    result.local_record.metadata,
                    local_capabilities,
                )
                and has_reliable_timestamp(
                    result.server_record.metadata,
                    server_capabilities,
                )
            ):
                if result.local_record.size != result.server_record.size:
                    return ComparisonDecision(
                        recommendation="Review before synchronizing.",
                        confidence=ConfidenceLevel.LOW,
                        reason=(
                            "The timestamps match but file sizes differ. "
                            "Content may have changed without time precision changes."
                        ),
                        status=result.status,
                    )

                return ComparisonDecision(
                    recommendation="No action is likely required.",
                    confidence=ConfidenceLevel.HIGH,
                    reason="Timestamps and file sizes appear aligned.",
                    status=result.status,
                )

            return _build_insufficient_evidence_decision(
                result,
                local_capabilities,
                server_capabilities,
            )

    if result.status == CompareStatus.NEEDS_REVIEW:
        return _build_insufficient_evidence_decision(
            result,
            local_capabilities,
            server_capabilities,
        )

    if result.status in {CompareStatus.LOCAL_NEWER, CompareStatus.SERVER_NEWER}:
        decision = _build_directional_decision(
            result,
            local_capabilities,
            server_capabilities,
        )
        if decision:
            return decision

    return ComparisonDecision(
        recommendation="Review before synchronizing.",
        confidence=ConfidenceLevel.MEDIUM,
        reason="TraceSync could not confidently classify this difference from available metadata.",
        status=result.status,
    )


def _build_directional_decision(
    result: ComparisonResult,
    local_capabilities: frozenset[ProviderCapability],
    server_capabilities: frozenset[ProviderCapability],
) -> ComparisonDecision | None:
    if result.local_record is None or result.server_record is None:
        return None

    if (
        not has_reliable_timestamp(result.local_record.metadata, local_capabilities)
        or not has_reliable_timestamp(
            result.server_record.metadata,
            server_capabilities,
        )
    ):
        return None
    time_delta = abs(result.local_record.modified_time - result.server_record.modified_time)
    size_changed = result.local_record.size != result.server_record.size
    if time_delta <= TIMESTAMP_UNCERTAINTY_SECONDS and size_changed:
        return ComparisonDecision(
            recommendation="Review before synchronizing.",
            confidence=ConfidenceLevel.LOW,
            reason=(
                "The files were modified within a few seconds of each other, "
                "and their sizes differ. This can be a precision or race condition."
            ),
            status=result.status,
        )

    if time_delta <= TIMESTAMP_UNCERTAINTY_SECONDS and not size_changed:
        return ComparisonDecision(
            recommendation=_recommended_action(result.status),
            confidence=ConfidenceLevel.MEDIUM,
            reason="The modification times are extremely close; verify before syncing.",
            status=result.status,
        )

    return ComparisonDecision(
        recommendation=_recommended_action(result.status),
        confidence=ConfidenceLevel.HIGH,
        reason="This is a likely safe direction based on available timestamps.",
        status=result.status,
    )


def _build_insufficient_evidence_decision(
    result: ComparisonResult,
    local_capabilities: frozenset[ProviderCapability],
    server_capabilities: frozenset[ProviderCapability],
) -> ComparisonDecision:
    local_record = result.local_record
    server_record = result.server_record
    if local_record is not None and server_record is not None:
        hashes_available = have_comparable_hashes(
            local_record.metadata,
            server_record.metadata,
            local_capabilities,
            server_capabilities,
        )
        if hashes_available and (
            local_record.metadata.content_hash != server_record.metadata.content_hash
        ):
            reason = (
                "The content hashes differ, but reliable timestamps are unavailable "
                "to determine the safe copy direction."
            )
        elif (
            local_record.size is not None
            and server_record.size is not None
            and local_record.size != server_record.size
        ):
            reason = (
                "The file sizes differ, but reliable timestamps or comparable hashes "
                "are unavailable to determine the safe copy direction."
            )
        else:
            reason = (
                "The providers did not supply enough reliable comparison evidence "
                "to determine whether these files match or which copy is newer."
            )
    else:
        reason = "TraceSync could not determine a safe comparison result."
    return ComparisonDecision(
        recommendation="Review before synchronizing.",
        confidence=ConfidenceLevel.LOW,
        reason=reason,
        status=result.status,
    )


def _recommended_action(status: CompareStatus) -> str:
    if status == CompareStatus.LOCAL_NEWER:
        return "Copy Local → Server is likely correct."
    if status == CompareStatus.SERVER_NEWER:
        return "Copy Server → Local is likely correct."
    return "Review before synchronizing."
