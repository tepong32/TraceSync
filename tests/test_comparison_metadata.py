import unittest

from core.comparer import compare_folders
from core.comparison_evidence import EvidenceMatch, compare_snapshot
from core.storage_provider import ProviderCapability
from models.compare_status import CompareStatus
from models.comparison_decision import ConfidenceLevel
from models.comparison_metadata import ComparisonMetadata
from models.file_record import FileRecord
from models.storage_location import StorageLocation


def make_record(
    provider_type: str,
    native_id: str,
    *,
    size: int | None = 10,
    modified_time: float | None = None,
    content_hash: str | None = None,
    hash_algorithm: str | None = None,
    version_id: str | None = None,
    timestamp_reliable: bool = False,
) -> FileRecord:
    location = StorageLocation(provider_type, native_id, f"Files/{native_id}.dat")
    metadata = ComparisonMetadata(
        size=size,
        modified_time=modified_time,
        content_hash=content_hash,
        hash_algorithm=hash_algorithm,
        version_id=version_id,
        timestamp_reliable=timestamp_reliable,
    )
    return FileRecord.from_location(
        location,
        "report.dat",
        modified_time,
        size,
        comparison_metadata=metadata,
    )


class ComparisonMetadataTests(unittest.TestCase):
    def test_metadata_holds_provider_evidence_without_provider_specific_fields(self):
        metadata = ComparisonMetadata(
            size=25,
            modified_time=None,
            content_hash="sha256:abc",
            hash_algorithm="sha256",
            version_id="version-7",
            timestamp_reliable=False,
        )

        self.assertEqual(metadata.size, 25)
        self.assertEqual(metadata.content_hash, "sha256:abc")
        self.assertEqual(metadata.hash_algorithm, "sha256")
        self.assertEqual(metadata.version_id, "version-7")
        self.assertFalse(metadata.timestamp_reliable)

    def test_matching_hashes_establish_equality_without_timestamps(self):
        local = make_record(
            "test-a", "local", content_hash="same", hash_algorithm="sha256"
        )
        server = make_record(
            "test-b", "server", content_hash="same", hash_algorithm="sha256"
        )
        hashing = frozenset({ProviderCapability.HASHING})

        result = compare_folders(
            {"report.dat": local},
            {"report.dat": server},
            hashing,
            hashing,
        )[0]

        self.assertEqual(result.status, CompareStatus.SAME)
        self.assertEqual(result.decision.confidence, ConfidenceLevel.HIGH)
        self.assertIn("hashes match", result.decision.reason)

    def test_different_hashes_without_timestamps_require_review(self):
        local = make_record(
            "test-a", "local", content_hash="first", hash_algorithm="sha256"
        )
        server = make_record(
            "test-b", "server", content_hash="second", hash_algorithm="sha256"
        )
        hashing = frozenset({ProviderCapability.HASHING})

        result = compare_folders(
            {"report.dat": local},
            {"report.dat": server},
            hashing,
            hashing,
        )[0]

        self.assertEqual(result.status, CompareStatus.NEEDS_REVIEW)
        self.assertEqual(result.decision.confidence, ConfidenceLevel.LOW)
        self.assertIn("hashes differ", result.decision.reason)

    def test_hashes_with_different_algorithms_are_not_compared(self):
        local = make_record(
            "test-a", "local", content_hash="same-text", hash_algorithm="sha256"
        )
        server = make_record(
            "test-b", "server", content_hash="same-text", hash_algorithm="md5"
        )
        hashing = frozenset({ProviderCapability.HASHING})

        result = compare_folders(
            {"report.dat": local},
            {"report.dat": server},
            hashing,
            hashing,
        )[0]

        self.assertEqual(result.status, CompareStatus.NEEDS_REVIEW)

    def test_timestamp_metadata_is_not_used_without_timestamp_capability(self):
        local = make_record(
            "test-a",
            "local",
            modified_time=200,
            timestamp_reliable=True,
        )
        server = make_record(
            "test-b",
            "server",
            modified_time=100,
            timestamp_reliable=True,
        )

        result = compare_folders(
            {"report.dat": local},
            {"report.dat": server},
            frozenset(),
            frozenset(),
        )[0]

        self.assertEqual(result.status, CompareStatus.NEEDS_REVIEW)
        self.assertEqual(result.decision.confidence, ConfidenceLevel.LOW)

    def test_reliable_timestamp_capability_preserves_directional_comparison(self):
        local = make_record(
            "test-a",
            "local",
            modified_time=200,
            timestamp_reliable=True,
        )
        server = make_record(
            "test-b",
            "server",
            modified_time=100,
            timestamp_reliable=True,
        )
        timestamps = frozenset({ProviderCapability.TIMESTAMPS})

        result = compare_folders(
            {"report.dat": local},
            {"report.dat": server},
            timestamps,
            timestamps,
        )[0]

        self.assertEqual(result.status, CompareStatus.LOCAL_NEWER)

    def test_version_id_is_used_for_same_provider_snapshot_validation(self):
        capabilities = frozenset({ProviderCapability.VERSION_HISTORY})
        expected = ComparisonMetadata(version_id="v1")
        unchanged = ComparisonMetadata(version_id="v1")
        changed = ComparisonMetadata(version_id="v2")

        self.assertEqual(
            compare_snapshot(unchanged, expected, capabilities),
            EvidenceMatch.MATCH,
        )
        self.assertEqual(
            compare_snapshot(changed, expected, capabilities),
            EvidenceMatch.CHANGED,
        )

    def test_size_without_change_evidence_is_insufficient(self):
        expected = ComparisonMetadata(size=10)
        current = ComparisonMetadata(size=10)

        self.assertEqual(
            compare_snapshot(current, expected, frozenset()),
            EvidenceMatch.INSUFFICIENT,
        )


if __name__ == "__main__":
    unittest.main()
