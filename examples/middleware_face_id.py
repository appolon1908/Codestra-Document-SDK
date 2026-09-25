"""Reference integration boundary; no direct FACE-ID dependency or automatic review.

Application UI obtains explicit human approval first. Middleware implements the
adapter protocol below and owns any downstream FACE-ID mapping and credentials.
No network submission occurs merely by importing this example.
"""

from typing import Protocol

from codestra_document import Client, ClientIntake, ReviewedClientIntake


class MiddlewareAdapter(Protocol):
    def create_client_from_reviewed_intake(self, intake: ClientIntake) -> str:
        """Return a client reference after applying application policy."""
        ...


def complete_reviewed_intake(
    documents: Client,
    reviewed: ReviewedClientIntake,
    middleware: MiddlewareAdapter,
) -> str:
    """Call only after review; reconcile failures before retrying either mutation."""
    confirmed = documents.confirm_scan(reviewed.scan_id, reviewed)
    return middleware.create_client_from_reviewed_intake(confirmed.to_client_intake())
