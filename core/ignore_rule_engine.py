"""
TraceSync
Ignore Rule Engine

Centralized ignore rule evaluation.
"""

from __future__ import annotations

from fnmatch import fnmatch
from pathlib import PurePosixPath

from models.ignore_rule import IgnoreRule
from models.rule_source import RuleSource


class IgnoreRuleEngine:
    """
    Evaluates whether files should be ignored.

    Supports built-in rules now, with future support for:

    - .tracesyncignore
    - User-defined rules
    - Include/override rules
    """

    BUILTIN_PATTERNS = (
        ".git/",
        ".hg/",
        ".svn/",
        "__pycache__/",
        ".pytest_cache/",
        ".vscode/",
        ".idea/",
        "Thumbs.db",
        "Desktop.ini",
        ".DS_Store",
        "~$*",
        "*.tmp",
        "*.temp",
    )

    def __init__(self) -> None:
        self._rules: list[IgnoreRule] = []

        self.load_builtin_rules()

    @property
    def rules(self) -> tuple[IgnoreRule, ...]:
        """Returns the loaded rules."""

        return tuple(self._rules)

    def load_builtin_rules(self) -> None:
        """Loads TraceSync's built-in ignore rules."""

        self._rules.extend(
            IgnoreRule(pattern=p, source=RuleSource.BUILTIN)
            for p in self.BUILTIN_PATTERNS
        )

    def add_rule(self, rule: IgnoreRule) -> None:
        """Adds a rule to the engine."""

        self._rules.append(rule)

    def is_ignored(self, relative_path: str) -> bool:
        """
        Determines whether a relative path should be ignored.
        """

        path = PurePosixPath(relative_path)

        for rule in self._rules:
            if self._matches(path, rule.pattern):
                return True

        return False

    @staticmethod
    def _matches(path: PurePosixPath, pattern: str) -> bool:
        """
        Matches a path against an ignore pattern.
        """

        normalized = path.as_posix()

        # Directory rule
        if pattern.endswith("/"):
            directory = pattern.rstrip("/")
            return (
                normalized == directory
                or normalized.startswith(directory + "/")
            )

        return fnmatch(path.name, pattern) or fnmatch(normalized, pattern)