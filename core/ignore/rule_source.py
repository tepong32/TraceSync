"""
TraceSync
Rule Source Enumeration

Defines where an ignore rule originated.
"""

from enum import Enum


class RuleSource(str, Enum):
    """Represents the origin of an ignore rule."""

    BUILTIN = "builtin"
    PROJECT = "project"
    USER = "user"