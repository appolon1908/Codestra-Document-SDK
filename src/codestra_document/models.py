"""Provisional wire models; see docs/contracts.md before production integration."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue

from .errors import DocumentError


class RedactedModel(BaseModel):
    model_config = ConfigDict(extra="ignore", hide_input_in_errors=True, strict=True)

    def __repr__(self) -> str:
        return f"{type(self).__name__}(<redacted>)"

    def __str__(self) -> str:
        return repr(self)


class Health(RedactedModel):
    status: str


class Capabilities(RedactedModel):
    document_types: list[str]
    countries: list[str]


class ClientIntake(RedactedModel):
    scan_id: str
    fields: dict[str, JsonValue]


class ReviewedClientIntake(RedactedModel):
    """Explicit caller attestation that these fields were reviewed by a human."""

    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True, strict=True)
    scan_id: str = Field(min_length=1)
    reviewed_fields: dict[str, JsonValue]


class ScanResult(RedactedModel):
    scan_id: str = Field(min_length=1)
    status: Literal["pending", "processing", "needs_review", "confirmed", "failed"]
    fields: dict[str, JsonValue] = Field(default_factory=dict)

    def to_client_intake(self) -> ClientIntake:
        """Return fields only after the service reports successful confirmation."""
        if self.status != "confirmed":
            raise DocumentError("Scan is not confirmed for client intake")
        return ClientIntake(scan_id=self.scan_id, fields=self.fields.copy())
