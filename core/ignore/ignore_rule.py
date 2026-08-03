"""
TraceSync
Ignore Rule Model
"""

from dataclasses import dataclass

from .rule_source import RuleSource


@dataclass(frozen=True, slots=True)
class IgnoreRule:
    """
    Represents a single ignore rule.

    Attributes
    ----------
    pattern:
        The pattern to match.

    source:
        Where the rule originated.
    """

    pattern: str
    source: RuleSource