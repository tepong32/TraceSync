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


class IgnoreLoader:
    """Loads and combines ignore rules from all configured sources."""

    def __init__(self) -> None:
        self._project_loader = ProjectIgnoreLoader()

    def load(self, project_root: str | Path) -> list[IgnoreRule]:
        """
        Load all ignore rules applicable to the given project.
        """
        rules = IgnoreRuleEngine.default_rules()
        rules.extend(self._project_loader.load(project_root))
        return rules