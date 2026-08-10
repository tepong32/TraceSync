import unittest

from core.comparison_confidence import build_decision, TIMESTAMP_UNCERTAINTY_SECONDS
from models.comparison_decision import ConfidenceLevel
from models.comparison_result import ComparisonResult
from models.compare_status import CompareStatus
from models.file_record import FileRecord


def _record(path, modified_time, size):
    return FileRecord(
        absolute_path=path,
        relative_path=path,
        modified_time=modified_time,
        size=size,
    )


class ComparisonConfidenceTests(unittest.TestCase):
    def test_local_only_is_high_confidence_copy_suggestion(self):
        result = ComparisonResult(
            relative_path="notes/todo.txt",
            status=CompareStatus.LOCAL_ONLY,
            local_record=_record("notes/todo.txt", 1000, 10),
            server_record=None,
        )

        decision = build_decision(result)
        self.assertEqual(decision.confidence, ConfidenceLevel.HIGH)
        self.assertIn("Local", decision.recommendation)

    def test_server_only_is_high_confidence_copy_suggestion(self):
        result = ComparisonResult(
            relative_path="notes/todo.txt",
            status=CompareStatus.SERVER_ONLY,
            local_record=None,
            server_record=_record("notes/todo.txt", 1000, 10),
        )

        decision = build_decision(result)
        self.assertEqual(decision.confidence, ConfidenceLevel.HIGH)
        self.assertIn("Server", decision.recommendation)

    def test_same_timestamp_same_size_is_high_confidence_no_action(self):
        result = ComparisonResult(
            relative_path="notes/todo.txt",
            status=CompareStatus.SAME,
            local_record=_record("notes/todo.txt", 1000, 10),
            server_record=_record("notes/todo.txt", 1000, 10),
        )

        decision = build_decision(result)
        self.assertEqual(decision.confidence, ConfidenceLevel.HIGH)
        self.assertIn("No action", decision.recommendation)

    def test_equal_timestamp_size_mismatch_becomes_low_confidence(self):
        result = ComparisonResult(
            relative_path="notes/todo.txt",
            status=CompareStatus.SAME,
            local_record=_record("notes/todo.txt", 1000, 10),
            server_record=_record("notes/todo.txt", 1000, 11),
        )

        decision = build_decision(result)
        self.assertEqual(decision.confidence, ConfidenceLevel.LOW)
        self.assertIn("Review", decision.recommendation)

    def test_close_timestamps_with_size_change_is_low_confidence(self):
        result = ComparisonResult(
            relative_path="notes/todo.txt",
            status=CompareStatus.LOCAL_NEWER,
            local_record=_record("notes/todo.txt", 1000.1, 10),
            server_record=_record("notes/todo.txt", 1000.0, 12),
        )

        decision = build_decision(result)
        self.assertEqual(decision.confidence, ConfidenceLevel.LOW)
        self.assertIn("within a few seconds", decision.reason)
        self.assertIn("within", decision.reason)

    def test_large_time_gap_treats_as_high_confidence(self):
        result = ComparisonResult(
            relative_path="notes/todo.txt",
            status=CompareStatus.SERVER_NEWER,
            local_record=_record("notes/todo.txt", 2000, 10),
            server_record=_record("notes/todo.txt", 2000 + 2 * TIMESTAMP_UNCERTAINTY_SECONDS + 1, 20),
        )

        decision = build_decision(result)
        self.assertEqual(decision.confidence, ConfidenceLevel.HIGH)
        self.assertIn("likely correct", decision.recommendation)
