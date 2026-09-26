"""Typed models for the Codestra Document Intelligence v1 API."""

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
    status: Literal["ok"]


class ImageLimits(RedactedModel):
    max_bytes: int
    min_dimension: int
    max_dimension: int
    max_pixels: int
    media_types: list[str]


class Capabilities(RedactedModel):
    document_types: list[str]
    image_limits: ImageLimits | None = None
    authenticity_verification: bool | None = None


class ClientIntake(RedactedModel):
    scan_id: str
    fields: dict[str, JsonValue]


class ReviewedClientIntake(RedactedModel):
    """Explicit caller attestation that these fields were reviewed by a human."""

    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True, strict=True)
    scan_id: str = Field(min_length=1)
    reviewed_fields: dict[str, str | None]


class ScanResult(RedactedModel):
    scan_id: str = Field(min_length=1)
    status: Literal["pending_review", "confirmed", "failed"]
    document_type: str | None = None
    country: str | None = None
    fields: dict[str, JsonValue] = Field(default_factory=dict)
    corrected_fields: list[str] = Field(default_factory=list)

    def to_client_intake(self) -> ClientIntake:
        """Return fields only after the service reports successful confirmation."""
        if self.status != "confirmed":
            raise DocumentError("Scan is not confirmed for client intake")
        return ClientIntake(scan_id=self.scan_id, fields=self.fields.copy())


class ScanSummary(RedactedModel):
    scan_id: str
    document_type: str
    country: str
    status: Literal["pending_review", "confirmed", "failed"]
    created_at: str
    updated_at: str
    confirmed_at: str | None = None


class ScanList(RedactedModel):
    items: list[ScanSummary]
    next_cursor: str | None = None


class FaceIdHandoff(RedactedModel):
    schema_ref: str
    scan_id: str
    tenant_id: str
    ready: bool
    status: Literal["pending_review", "confirmed", "failed"]
    document: dict[str, JsonValue]
    subject: dict[str, JsonValue]
    portrait_detected: bool
    portrait_side: str | None = None
    front_image_sha256: str | None = None
    back_image_sha256: str | None = None
