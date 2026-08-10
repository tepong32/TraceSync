from models.compare_status import CompareStatus
from models.comparison_decision import ComparisonDecision, ConfidenceLevel
from models.comparison_result import ComparisonResult


TIMESTAMP_UNCERTAINTY_SECONDS = 2.0


def build_decision(result: ComparisonResult) -> ComparisonDecision:
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

    if result.status in {CompareStatus.LOCAL_NEWER, CompareStatus.SERVER_NEWER}:
        decision = _build_directional_decision(result)
        if decision:
            return decision

    return ComparisonDecision(
        recommendation="Review before synchronizing.",
        confidence=ConfidenceLevel.MEDIUM,
        reason="TraceSync could not confidently classify this difference from available metadata.",
        status=result.status,
    )


def _build_directional_decision(result: ComparisonResult) -> ComparisonDecision | None:
    if result.local_record is None or result.server_record is None:
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


def _recommended_action(status: CompareStatus) -> str:
    if status == CompareStatus.LOCAL_NEWER:
        return "Copy Local → Server is likely correct."
    if status == CompareStatus.SERVER_NEWER:
        return "Copy Server → Local is likely correct."
    return "Review before synchronizing."
