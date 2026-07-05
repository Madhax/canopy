"""Authoritative validation for Canopy organization documents (docs/org-chart-editor.md §4)."""

from .codes import CODE_MESSAGES, Severity, ValidationIssue
from .rules import validate_organization

__all__ = ["CODE_MESSAGES", "Severity", "ValidationIssue", "validate_organization"]
