"""
ignore_loader.py

Collects ignore rules from all supported rule sources.

Current sources:
- Built-in rules
- Project-level .tracesyncignore

Future sources (v0.4.x+):
- User-defined rules
- Workspace rules
"""

from __future__ import annotations

from pathlib import Path

from .ignore_rule import IgnoreRule
from .ignore_rule_engine import IgnoreRuleEngine
from .project_ignore_loader import ProjectIgnoreLoader
from .rule_source import RuleSource


class IgnoreLoader:
    """Loads and combines ignore rules from all configured sources."""

    def __init__(self) -> None:
        self._project_loader = ProjectIgnoreLoader()

    @staticmethod
    def _normalize_patterns(raw_patterns) -> list[str]:
        patterns: list[str] = []
        if raw_patterns is None:
            return patterns
        if isinstance(raw_patterns, str):
            raw_patterns = raw_patterns.splitlines()
        elif not isinstance(raw_patterns, (list, tuple, set)):
            return patterns

        for pattern in raw_patterns:
            if not isinstance(pattern, str):
                continue

            normalized_pattern = pattern.strip()
            if not normalized_pattern or normalized_pattern.startswith("#"):
                continue

            patterns.append(normalized_pattern)

        return patterns

    def load(self, project_root: str | Path, user_ignore_patterns=None) -> list[IgnoreRule]:
        """
        Load all ignore rules applicable to the given project.
        """
        rules = IgnoreRuleEngine.default_rules()
        rules.extend(self._project_loader.load(project_root))
        rules.extend(
            IgnoreRule(pattern=pattern, source=RuleSource.USER)
            for pattern in self._normalize_patterns(user_ignore_patterns)
        )
        return rules
