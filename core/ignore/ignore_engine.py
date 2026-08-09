"""
ignore_engine.py

Convenience factory for constructing a configured IgnoreRuleEngine.
"""

from __future__ import annotations

from pathlib import Path

from .ignore_loader import IgnoreLoader
from .ignore_rule_engine import IgnoreRuleEngine


def create_ignore_engine(
    project_root: str | Path,
    user_ignore_patterns=None,
) -> IgnoreRuleEngine:
    """
    Build and return a configured IgnoreRuleEngine.

    Parameters
    ----------
    project_root:
        Root directory of the project.

    Returns
    -------
    IgnoreRuleEngine
        Ready-to-use ignore rule engine.
    """
    loader = IgnoreLoader()
    rules = loader.load(project_root, user_ignore_patterns=user_ignore_patterns)
    return IgnoreRuleEngine(rules)
