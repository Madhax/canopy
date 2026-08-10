"""Authoritative validation for Canopy team documents (docs/org-chart-editor.md §4)."""

from .codes import CODE_MESSAGES, Severity, ValidationIssue
from .rules import validate_team

__all__ = ["CODE_MESSAGES", "Severity", "ValidationIssue", "validate_team"]
