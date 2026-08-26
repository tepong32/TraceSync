from enum import Enum

from core.storage_provider import ProviderCapability
from models.comparison_metadata import ComparisonMetadata


class EvidenceMatch(str, Enum):
    MATCH = "match"
    CHANGED = "changed"
    INSUFFICIENT = "insufficient"


def has_reliable_timestamp(
    metadata: ComparisonMetadata,
    capabilities: frozenset[ProviderCapability],
) -> bool:
    return (
        ProviderCapability.TIMESTAMPS in capabilities
        and metadata.timestamp_reliable
        and metadata.modified_time is not None
    )


def has_content_hash(
    metadata: ComparisonMetadata,
    capabilities: frozenset[ProviderCapability],
) -> bool:
    return (
        ProviderCapability.HASHING in capabilities
        and metadata.content_hash is not None
        and metadata.hash_algorithm is not None
    )


def have_comparable_hashes(
    first: ComparisonMetadata,
    second: ComparisonMetadata,
    first_capabilities: frozenset[ProviderCapability],
    second_capabilities: frozenset[ProviderCapability],
) -> bool:
    return (
        has_content_hash(first, first_capabilities)
        and has_content_hash(second, second_capabilities)
        and first.hash_algorithm.casefold() == second.hash_algorithm.casefold()
    )


def compare_snapshot(
    current: ComparisonMetadata,
    expected: ComparisonMetadata,
    capabilities: frozenset[ProviderCapability],
) -> EvidenceMatch:
    """Compare two observations of one provider item using its strongest evidence."""
    if (
        ProviderCapability.VERSION_HISTORY in capabilities
        and current.version_id is not None
        and expected.version_id is not None
    ):
        return _match(current.version_id, expected.version_id)

    if have_comparable_hashes(
        current,
        expected,
        capabilities,
        capabilities,
    ):
        return _match(current.content_hash, expected.content_hash)

    if has_reliable_timestamp(current, capabilities) and has_reliable_timestamp(
        expected,
        capabilities,
    ):
        if current.modified_time != expected.modified_time:
            return EvidenceMatch.CHANGED
        if (
            current.size is not None
            and expected.size is not None
            and current.size != expected.size
        ):
            return EvidenceMatch.CHANGED
        return EvidenceMatch.MATCH

    if (
        current.size is not None
        and expected.size is not None
        and current.size != expected.size
    ):
        return EvidenceMatch.CHANGED
    return EvidenceMatch.INSUFFICIENT


def _match(current: str, expected: str) -> EvidenceMatch:
    if current == expected:
        return EvidenceMatch.MATCH
    return EvidenceMatch.CHANGED
