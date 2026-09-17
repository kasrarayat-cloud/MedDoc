"""Bounded document processing. Public operations always run in a sandbox."""

from .service import DocumentError, fill_template, inspect_template, resolve_template

__all__ = ["DocumentError", "inspect_template", "fill_template", "resolve_template"]
