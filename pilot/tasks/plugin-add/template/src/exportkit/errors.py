class ExportError(Exception):
    """Raised for every user-facing export failure: unknown format,
    empty input, malformed records."""
