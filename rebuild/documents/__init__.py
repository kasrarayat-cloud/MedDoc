"""Bounded document processing. Public operations always run in a sandbox."""

from .service import DocumentError, check_original, fill_template, inspect_template, resolve_template

__all__ = ["DocumentError", "inspect_template", "check_original", "fill_template", "resolve_template"]
