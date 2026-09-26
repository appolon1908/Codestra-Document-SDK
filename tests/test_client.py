import base64
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from codestra_document import (
    Client,
    DocumentError,
    ReviewedClientIntake,
    Routes,
    ScanResult,
)


@pytest.fixture
def server():
    requests = []
    replies = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            self.respond()

        def do_POST(self):
            self.respond()

        def respond(self):
            body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
            requests.append((self.command, self.path, dict(self.headers), body))
            status, data, delay = replies.pop(0)
            time.sleep(delay)
            self.send_response(status)
            self.end_headers()
            try:
                self.wfile.write(json.dumps(data).encode())
            except BrokenPipeError:
                pass

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_port}", requests, replies
    httpd.shutdown()
    httpd.server_close()
    thread.join()


def client(server, **kwargs):
    return Client(
        server[0],
        token=lambda: "private-token",
        allow_insecure_http=True,
        retry_backoff=0,
        **kwargs,
    )


def scan_payload(status="pending_review", scan_id="dscan_test12345"):
    return {
        "scan_id": scan_id,
        "tenant_id": "tenant-a",
        "document_type": "driver_license",
        "country": "DO",
        "status": status,
        "created_at": "2026-09-25T12:00:00Z",
        "updated_at": "2026-09-25T12:00:00Z",
        "confirmed_at": "2026-09-25T12:05:00Z" if status == "confirmed" else None,
        "images": [],
        "fields": {"full_name": {"value": "Ada Example", "confidence": 0.9}},
        "corrected_fields": [],
        "quality": {"overall_confidence": 0.9, "warnings": []},
        "document": {
            "number_last4": "8901",
            "number_masked": "****8901",
            "document_hash": "hmac-sha256:" + "a" * 64,
        },
        "portrait_detected": True,
        "qr_present": False,
        "worker": {"name": "codestra-ocr-workers", "version": "1.0.0"},
        "verification": {
            "authenticity_verified": False,
            "method": "ocr_intake_aid",
            "disclaimer": "OCR intake aid",
        },
        "source_lookup": None,
    }


def handoff_payload(scan_id="dscan_test12345"):
    return {
        "schema_ref": "codestra.document.face-id-handoff/v1",
        "scan_id": scan_id,
        "tenant_id": "tenant-a",
        "ready": True,
        "status": "confirmed",
        "confirmed_at": "2026-09-25T12:05:00Z",
        "document": {
            "document_type": "driver_license",
            "country": "DO",
            "number_last4": "8901",
            "document_hash": "hmac-sha256:" + "a" * 64,
        },
        "subject": {"full_name": "Ada Example"},
        "portrait_detected": True,
        "portrait_side": "front",
        "front_image_sha256": "b" * 64,
        "back_image_sha256": None,
        "verification": {
            "authenticity_verified": False,
            "method": "ocr_intake_aid",
            "disclaimer": "OCR intake aid",
        },
    }


def test_workflow_uses_real_v1_routes_and_json_scan_body(server):
    _url, requests, replies = server
    replies.extend(
        [
            (200, {"status": "ok"}, 0),
            (
                200,
                {
                    "service": "codestra-document-intelligence",
                    "api_version": "v1",
                    "document_types": ["driver_license"],
                    "raw_image_persistence": False,
                    "sensitive_number_storage": "keyed_hash_and_last4",
                    "authenticity_verification": False,
                },
                0,
            ),
            (201, scan_payload(), 0),
            (200, scan_payload(), 0),
            (200, scan_payload("confirmed"), 0),
            (200, handoff_payload(), 0),
            (
                200,
                {
                    "items": [
                        {
                            "scan_id": "dscan_test12345",
                            "document_type": "driver_license",
                            "country": "DO",
                            "status": "confirmed",
                            "created_at": "2026-09-25T12:00:00Z",
                            "updated_at": "2026-09-25T12:05:00Z",
                            "confirmed_at": "2026-09-25T12:05:00Z",
                        }
                    ],
                    "next_cursor": None,
                },
                0,
            ),
        ]
    )

    c = client(server)
    assert c.health().status == "ok"
    assert c.capabilities().document_types == ["driver_license"]

    result = c.scan_document(b"front-image", b"back-image", "driver_license", "DO")
    assert result.scan_id == "dscan_test12345"
    body = json.loads(requests[2][3])
    assert requests[2][1] == "/v1/documents/scan"
    assert body == {
        "document_type": "driver_license",
        "country": "DO",
        "front_image_base64": base64.b64encode(b"front-image").decode(),
        "back_image_base64": base64.b64encode(b"back-image").decode(),
    }

    assert c.get_scan(result.scan_id).status == "pending_review"
    reviewed = ReviewedClientIntake(
        scan_id=result.scan_id,
        reviewed_fields={"full_name": "Ada Corrected"},
    )
    confirmed = c.confirm_scan(result.scan_id, reviewed)
    assert confirmed.status == "confirmed"
    assert json.loads(requests[4][3]) == {
        "corrections": {"full_name": "Ada Corrected"}
    }
    assert c.get_face_id_handoff(result.scan_id).ready is True
    assert c.list_recent().items[0].scan_id == result.scan_id
    assert all(r[2]["Authorization"] == "Bearer private-token" for r in requests)


@pytest.mark.parametrize("status", [429, 502, 503, 504])
def test_get_retries(server, status):
    server[2].extend([(status, {"secret": "private"}, 0), (200, {"status": "ok"}, 0)])
    assert client(server).health().status == "ok"
    assert len(server[1]) == 2


@pytest.mark.parametrize("operation", ["scan", "confirm"])
def test_post_never_retried(server, operation):
    server[2].append((503, {"secret": "private"}, 0))
    with pytest.raises(DocumentError) as caught:
        if operation == "scan":
            client(server).scan_document(b"private-image", None, "driver_license", "DO")
        else:
            client(server).confirm_scan(
                "dscan_private",
                ReviewedClientIntake(scan_id="dscan_private", reviewed_fields={}),
            )
    assert caught.value.status_code == 503
    assert "private" not in str(caught.value)
    assert len(server[1]) == 1


def test_timeout_redacted(server):
    server[2].append((200, {"status": "ok"}, 0.1))
    with pytest.raises(DocumentError, match="transport"):
        client(server, timeout=0.01, get_retries=0).health()


def test_invalid_response_redacted(server):
    server[2].append((200, {"scan_id": {"private": "data"}}, 0))
    with pytest.raises(DocumentError) as caught:
        client(server).get_scan("dscan_private")
    assert "private" not in str(caught.value)


def test_review_gate():
    with pytest.raises(DocumentError):
        ScanResult(scan_id="dscan_x", status="pending_review").to_client_intake()


def test_token_failure_redacted(server):
    def provider():
        raise ValueError("private-token")

    c = Client(server[0], token=provider, allow_insecure_http=True)
    with pytest.raises(DocumentError) as caught:
        c.health()
    assert "private" not in str(caught.value)


def test_https_required():
    with pytest.raises(DocumentError):
        Client("http://example.com", token="secret")


def test_retry_exhaustion_and_refresh(server):
    tokens = iter(["first", "second", "third"])
    server[2].extend([(503, {}, 0)] * 3)
    c = Client(server[0], token=lambda: next(tokens), allow_insecure_http=True, retry_backoff=0)
    with pytest.raises(DocumentError):
        c.health()
    assert [r[2]["Authorization"] for r in server[1]] == [
        "Bearer first",
        "Bearer second",
        "Bearer third",
    ]


@pytest.mark.parametrize("status", [301, 401, 403, 404, 500])
def test_nonretryable_status(server, status):
    server[2].append((status, {"private": "body"}, 0))
    with pytest.raises(DocumentError):
        client(server).health()
    assert len(server[1]) == 1


def test_size_limit(server):
    server[2].append((200, {"status": "x" * 100}, 0))
    with pytest.raises(DocumentError, match="size limit"):
        client(server, max_response_bytes=10).health()


def test_identifier_encoded(server):
    payload = scan_payload(scan_id="a/b?secret")
    server[2].append((200, payload, 0))
    client(server).get_scan("a/b?secret")
    assert server[1][0][1] == "/v1/documents/a%2Fb%3Fsecret"


def test_no_back_and_custom_routes(server):
    server[2].append((201, scan_payload(scan_id="dscan_s"), 0))
    custom = Routes(submit="/scans")
    client(server, routes=custom).scan_document(b"front", None, "driver_license", "DO")
    assert server[1][0][1] == "/scans"
    payload = json.loads(server[1][0][3])
    assert payload["back_image_base64"] is None


def test_confirmation_mismatch(server):
    with pytest.raises(DocumentError, match="does not match"):
        client(server).confirm_scan(
            "dscan_a",
            ReviewedClientIntake(scan_id="dscan_b", reviewed_fields={}),
        )
    assert not server[1]


def test_nonfinite_review_fields_rejected():
    with pytest.raises(Exception):
        ReviewedClientIntake(
            scan_id="dscan_s",
            reviewed_fields={"secret": float("nan")},
        )


def test_invalid_upload_text_redacted(server):
    with pytest.raises(DocumentError):
        client(server).scan_document(b"front", None, "\ud800secret", "DO")


@pytest.mark.parametrize("method", ["get", "confirm", "handoff"])
def test_response_scan_must_match_request(server, method):
    wrong = scan_payload("confirmed", scan_id="dscan_wrong")
    if method == "handoff":
        wrong = handoff_payload(scan_id="dscan_wrong")
    server[2].append((200, wrong, 0))
    with pytest.raises(DocumentError, match="does not match"):
        c = client(server)
        if method == "get":
            c.get_scan("dscan_expected")
        elif method == "confirm":
            c.confirm_scan(
                "dscan_expected",
                ReviewedClientIntake(scan_id="dscan_expected", reviewed_fields={}),
            )
        else:
            c.get_face_id_handoff("dscan_expected")


def test_list_recent_cursor_is_encoded(server):
    server[2].append((200, {"items": [], "next_cursor": None}, 0))
    client(server).list_recent(limit=25, cursor="dscan_cursor")
    assert server[1][0][1] == "/v1/documents?limit=25&cursor=dscan_cursor"


def test_invalid_list_limit_rejected(server):
    with pytest.raises(DocumentError):
        client(server).list_recent(limit=0)
    assert not server[1]


@pytest.mark.parametrize(
    "url",
    ["https://private host", "https://secret\nexample.com", "https://example.com/private path"],
)
def test_invalid_url_redacted(url):
    with pytest.raises(DocumentError) as caught:
        Client(url, token="secret")
    assert "secret" not in str(caught.value) and "private" not in str(caught.value)
