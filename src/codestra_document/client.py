"""Synchronous transport with no request logging and no mutation retries."""

import http.client
import json
import math
import ssl
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import TypeVar
from urllib.parse import quote, urlsplit

from .errors import DocumentError
from .models import Capabilities, Health, RedactedModel, ReviewedClientIntake, ScanResult

Model = TypeVar("Model", bound=RedactedModel)


@dataclass(frozen=True)
class Routes:
    """Paths relative to the base URL; scan routes contain {scan_id}."""

    health: str = "/health"
    capabilities: str = "/v1/capabilities"
    scans: str = "/v1/scans"
    scan: str = "/v1/scans/{scan_id}"
    confirm: str = "/v1/scans/{scan_id}/confirm"


class Client:
    """Caller-owned credentials; one connection per request, no persistent session.

    Timeout is a socket-operation timeout, not a total request deadline.
    Token providers run once per attempt and may refresh workload tokens.
    """

    def __init__(
        self,
        base_url: str,
        *,
        token: str | Callable[[], str],
        timeout: float = 30.0,
        get_retries: int = 2,
        retry_backoff: float = 0.25,
        allow_insecure_http: bool = False,
        routes: Routes | None = None,
        max_response_bytes: int = 8 * 1024 * 1024,
    ) -> None:
        routes = routes or Routes()
        valid = False
        try:
            parsed = urlsplit(base_url)
            port = parsed.port
            valid = bool(parsed.hostname) and parsed.scheme in ("http", "https")
            valid = valid and all(32 < ord(c) < 127 for c in base_url)
            valid = valid and not (
                parsed.username or parsed.password or parsed.query or parsed.fragment
            )
            valid = valid and (
                parsed.scheme == "https"
                or (allow_insecure_http and parsed.hostname in ("localhost", "127.0.0.1", "::1"))
            )
        except (ValueError, TypeError):
            pass
        if not valid:
            raise DocumentError("Invalid base URL; HTTPS required except explicit loopback HTTP")
        if not math.isfinite(timeout) or timeout <= 0:
            raise DocumentError("Timeout must be finite and positive")
        if not isinstance(get_retries, int) or not 0 <= get_retries <= 5:
            raise DocumentError("GET retries must be between zero and five")
        if not math.isfinite(retry_backoff) or not 0 <= retry_backoff <= 60:
            raise DocumentError("Retry backoff must be finite and between zero and 60 seconds")
        if max_response_bytes < 1:
            raise DocumentError("Response limit must be positive")
        for path in (routes.health, routes.capabilities, routes.scans, routes.scan, routes.confirm):
            if (
                not path.startswith("/")
                or "?" in path
                or "#" in path
                or any(not 32 < ord(c) < 127 for c in path)
            ):
                raise DocumentError("Invalid route configuration")
        self._host = parsed.hostname or ""
        self._port = port
        self._https = parsed.scheme == "https"
        self._prefix = parsed.path.rstrip("/")
        self._token = token
        self._timeout = timeout
        self._get_retries = get_retries
        self._backoff = retry_backoff
        self._routes = routes
        self._max_response_bytes = max_response_bytes

    def __repr__(self) -> str:
        return "Client(<redacted>)"

    def _bearer(self) -> str:
        result = None
        try:
            candidate = self._token() if callable(self._token) else self._token
            if (
                isinstance(candidate, str)
                and candidate
                and all(32 < ord(c) < 127 for c in candidate)
            ):
                result = candidate
        except Exception:  # noqa: BLE001, S110 - caller errors may contain credentials
            pass
        if result is None:
            raise DocumentError("Token provider failed or returned an invalid token")
        return result

    def _request(
        self,
        method: str,
        path: str,
        model: type[Model],
        body: bytes | None = None,
        content_type: str = "application/json",
    ) -> Model:
        attempts = 1 + (self._get_retries if method == "GET" else 0)
        for attempt in range(attempts):
            headers = {
                "Authorization": f"Bearer {self._bearer()}",
                "Accept": "application/json",
                "Content-Type": content_type,
            }
            connection: http.client.HTTPConnection
            if self._https:
                connection = http.client.HTTPSConnection(
                    self._host,
                    self._port,
                    timeout=self._timeout,
                    context=ssl.create_default_context(),
                )
            else:
                connection = http.client.HTTPConnection(
                    self._host, self._port, timeout=self._timeout
                )
            status = None
            data = b""
            failed = False
            try:
                connection.request(method, self._prefix + path, body, headers)
                response = connection.getresponse()
                status = response.status
                data = response.read(self._max_response_bytes + 1)
            except (OSError, http.client.HTTPException, ValueError, UnicodeError):
                failed = True
            finally:
                connection.close()
            retryable = failed or status in (429, 502, 503, 504)
            if retryable and attempt + 1 < attempts:
                time.sleep(self._backoff * (2**attempt))
                continue
            if failed:
                raise DocumentError("Document service transport failure")
            if status is None or not 200 <= status < 300:
                raise DocumentError("Document service request failed", status_code=status)
            if len(data) > self._max_response_bytes:
                raise DocumentError("Document service response exceeds size limit")
            result = None
            try:
                result = model.model_validate_json(data)
            except ValueError:
                pass
            if result is None:
                raise DocumentError("Invalid document service response")
            return result
        raise DocumentError("Document service request failed")

    def health(self) -> Health:
        return self._request("GET", self._routes.health, Health)

    def capabilities(self) -> Capabilities:
        return self._request("GET", self._routes.capabilities, Capabilities)

    def scan_document(
        self,
        front: bytes,
        back: bytes | None,
        document_type: str,
        country: str,
    ) -> ScanResult:
        """Submit images once. A timeout leaves the outcome unknown; do not blindly resubmit."""
        if (
            not isinstance(front, bytes)
            or not front
            or (back is not None and (not isinstance(back, bytes) or not back))
        ):
            raise DocumentError("Images must be nonempty bytes")
        if (
            not isinstance(document_type, str)
            or not document_type
            or not isinstance(country, str)
            or not country
        ):
            raise DocumentError("Document type and country are required")
        encoded_values = None
        try:
            encoded_values = (document_type.encode(), country.encode())
        except UnicodeError:
            pass
        if encoded_values is None:
            raise DocumentError("Invalid document metadata encoding")
        boundary = uuid.uuid4().hex
        parts = []
        for name, value in (("document_type", encoded_values[0]), ("country", encoded_values[1])):
            parts.append(
                f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n'.encode()
                + value
                + b"\r\n"
            )
        for name, image in (("front", front), ("back", back)):
            if image is not None:
                parts.append(
                    f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"; filename="{name}.bin"\r\nContent-Type: application/octet-stream\r\n\r\n'.encode()
                    + image
                    + b"\r\n"
                )
        body = b"".join(parts) + f"--{boundary}--\r\n".encode()
        return self._request(
            "POST",
            self._routes.scans,
            ScanResult,
            body,
            f"multipart/form-data; boundary={boundary}",
        )

    @staticmethod
    def _scan_path(template: str, scan_id: str) -> str:
        if not isinstance(scan_id, str) or not scan_id or scan_id in (".", ".."):
            raise DocumentError("Invalid scan identifier")
        encoded = None
        try:
            encoded = quote(scan_id, safe="")
        except UnicodeError:
            pass
        if encoded is None:
            raise DocumentError("Invalid scan identifier encoding")
        return template.replace("{scan_id}", encoded)

    def get_scan(self, scan_id: str) -> ScanResult:
        result = self._request("GET", self._scan_path(self._routes.scan, scan_id), ScanResult)
        if result.scan_id != scan_id:
            raise DocumentError("Response does not match requested scan")
        return result

    def confirm_scan(self, scan_id: str, reviewed: ReviewedClientIntake) -> ScanResult:
        """Confirm explicitly reviewed fields once; never infer human review from extraction."""
        if reviewed.scan_id != scan_id:
            raise DocumentError("Reviewed result does not match scan")
        body = None
        try:
            body = json.dumps(reviewed.model_dump(), allow_nan=False).encode()
        except (ValueError, TypeError):
            pass
        if body is None:
            raise DocumentError("Invalid reviewed fields")
        result = self._request(
            "POST", self._scan_path(self._routes.confirm, scan_id), ScanResult, body
        )
        if result.scan_id != scan_id:
            raise DocumentError("Response does not match requested scan")
        return result
