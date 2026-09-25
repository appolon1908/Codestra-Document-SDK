import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from codestra_document import Client, DocumentError, ReviewedClientIntake, ScanResult


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


def test_workflow(server):
    _url, requests, replies = server
    scan = {"scan_id": "scan-1", "status": "needs_review", "fields": {"name": "private-name"}}
    replies.extend(
        [
            (200, {"status": "ok"}, 0),
            (200, {"document_types": ["id"], "countries": ["DO"]}, 0),
            (202, scan, 0),
            (200, scan, 0),
            (200, {**scan, "status": "confirmed"}, 0),
        ]
    )
    c = client(server)
    assert c.health().status == "ok"
    assert c.capabilities().countries == ["DO"]
    result = c.scan_document(b"front-image", b"back-image", "id", "DO")
    assert result.scan_id == "scan-1"
    assert c.get_scan("scan-1").fields == {"name": "private-name"}
    reviewed = ReviewedClientIntake(scan_id="scan-1", reviewed_fields={"name": "corrected"})
    confirmed = c.confirm_scan("scan-1", reviewed)
    assert confirmed.to_client_intake().fields == {"name": "private-name"}
    assert all(r[2]["Authorization"] == "Bearer private-token" for r in requests)
    assert requests[2][1] == "/v1/scans"
    assert b"front-image" in requests[2][3] and b"back-image" in requests[2][3]
    assert b'name="document_type"' in requests[2][3]
    assert json.loads(requests[4][3]) == {
        "scan_id": "scan-1",
        "reviewed_fields": {"name": "corrected"},
    }
    for obj in (c, result, reviewed, confirmed.to_client_intake()):
        assert "private" not in repr(obj) and "corrected" not in str(obj)


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
            client(server).scan_document(b"private-image", None, "id", "DO")
        else:
            client(server).confirm_scan(
                "private-id", ReviewedClientIntake(scan_id="private-id", reviewed_fields={})
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
        client(server).get_scan("private-id")
    assert "private" not in str(caught.value)
    assert caught.value.__context__ is None


def test_review_gate():
    with pytest.raises(DocumentError):
        ScanResult(scan_id="s", status="needs_review").to_client_intake()


def test_token_failure_redacted(server):
    def provider():
        raise ValueError("private-token")

    c = Client(server[0], token=provider, allow_insecure_http=True)
    with pytest.raises(DocumentError) as caught:
        c.health()
    assert "private" not in str(caught.value)
    assert caught.value.__context__ is None


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
    server[2].append((200, {"scan_id": "a/b?secret", "status": "pending"}, 0))
    client(server).get_scan("a/b?secret")
    assert server[1][0][1] == "/v1/scans/a%2Fb%3Fsecret"


def test_no_back_and_custom_routes(server):
    from codestra_document import Routes

    server[2].append((202, {"scan_id": "s", "status": "pending"}, 0))
    client(server, routes=Routes(scans="/scans")).scan_document(b"front", None, "id", "DO")
    assert server[1][0][1] == "/scans"
    assert b'name="back"' not in server[1][0][3]


def test_confirmation_mismatch(server):
    with pytest.raises(DocumentError, match="does not match"):
        client(server).confirm_scan("a", ReviewedClientIntake(scan_id="b", reviewed_fields={}))
    assert not server[1]


def test_nonfinite_review_fields_redacted(server):
    with pytest.raises(DocumentError):
        client(server).confirm_scan(
            "s", ReviewedClientIntake(scan_id="s", reviewed_fields={"secret": float("nan")})
        )


def test_invalid_upload_text_redacted(server):
    with pytest.raises(DocumentError):
        client(server).scan_document(b"front", None, "\ud800secret", "DO")


@pytest.mark.parametrize("method", ["get", "confirm"])
def test_response_scan_must_match_request(server, method):
    server[2].append((200, {"scan_id": "wrong", "status": "confirmed"}, 0))
    with pytest.raises(DocumentError, match="does not match"):
        c = client(server)
        if method == "get":
            c.get_scan("expected")
        else:
            c.confirm_scan("expected", ReviewedClientIntake(scan_id="expected", reviewed_fields={}))


def test_middleware_example(server):
    from middleware_face_id import complete_reviewed_intake

    class Adapter:
        def create_client_from_reviewed_intake(self, intake):
            assert intake.fields == {"name": "reviewed"}
            return "client-ref"

    server[2].append(
        (200, {"scan_id": "s", "status": "confirmed", "fields": {"name": "reviewed"}}, 0)
    )
    reviewed = ReviewedClientIntake(scan_id="s", reviewed_fields={"name": "reviewed"})
    assert complete_reviewed_intake(client(server), reviewed, Adapter()) == "client-ref"


@pytest.mark.parametrize(
    "url",
    ["https://private host", "https://secret\nexample.com", "https://example.com/private path"],
)
def test_invalid_url_redacted(url):
    with pytest.raises(DocumentError) as caught:
        Client(url, token="secret")
    assert "secret" not in str(caught.value) and "private" not in str(caught.value)
