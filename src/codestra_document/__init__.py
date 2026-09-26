"""Codestra Document Intelligence Python SDK."""

from .client import Client, Routes
from .errors import DocumentError
from .models import (
    Capabilities,
    ClientIntake,
    FaceIdHandoff,
    Health,
    ReviewedClientIntake,
    ScanList,
    ScanResult,
    ScanSummary,
)

__version__ = "0.2.0"
__all__ = [
    "Capabilities",
    "Client",
    "ClientIntake",
    "DocumentError",
    "FaceIdHandoff",
    "Health",
    "ReviewedClientIntake",
    "Routes",
    "ScanList",
    "ScanResult",
    "ScanSummary",
]
