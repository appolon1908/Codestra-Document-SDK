"""Safe exception surface: never attach requests, responses or provider errors."""


class DocumentError(Exception):
    """Sanitized SDK failure with an optional HTTP status code."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
