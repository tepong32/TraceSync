"""
project_ignore_loader.py

Loads project-specific ignore rules from a .tracesyncignore file.

Responsibilities:
- Discover the project ignore file.
- Parse ignore patterns.
- Return IgnoreRule objects.

This module does NOT perform any pattern matching.
Pattern evaluation belongs exclusively to IgnoreRuleEngine.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from .ignore_rule import IgnoreRule
from .rule_source import RuleSource


class ProjectIgnoreLoader:
    """Loads ignore rules from a project's .tracesyncignore file."""

    IGNORE_FILENAME = ".tracesyncignore"

    def load(self, project_root: str | Path) -> list[IgnoreRule]:
        """
        Load project-specific ignore rules.

        Parameters
        ----------
        project_root : str | Path
            Root directory of the project.

        Returns
        -------
        list[IgnoreRule]
            Parsed ignore rules.
        """
        ignore_file = self.get_ignore_file(project_root)

        if not ignore_file.is_file():
            return []

        try:
            lines = ignore_file.read_text(
                encoding="utf-8"
            ).splitlines()
        except OSError:
            # Fail gracefully if the ignore file cannot be read.
            return []

        return self._parse_lines(lines)

    def get_ignore_file(self, project_root: str | Path) -> Path:
        """
        Return the expected project ignore file path.
        """
        return Path(project_root) / self.IGNORE_FILENAME

    def _parse_lines(self, lines: Iterable[str]) -> list[IgnoreRule]:
        """
        Parse .tracesyncignore lines into IgnoreRule objects.

        Supported syntax:
            - Blank lines are ignored.
            - Lines beginning with '#' are comments.
            - Every other line becomes a project ignore rule.
        """
        rules: list[IgnoreRule] = []

        for line in lines:
            pattern = line.strip()

            if not pattern:
                continue

            if pattern.startswith("#"):
                continue

            rules.append(
                IgnoreRule(
                    pattern=pattern,
                    source=RuleSource.PROJECT,
                )
            )

        return rules