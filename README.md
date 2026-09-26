# Codestra Document SDK

Python 3.11+ client for Codestra Document Intelligence. Distribution:
`codestra-document`; import: `codestra_document`.

The SDK is aligned with the standalone Document Intelligence v1 API and the
versioned Codestra Document Schemas foundation on the integration branch.

```sh
pip install .
```

```python
from codestra_document import Client, ReviewedClientIntake

# Supply a workload/bearer token from your application's identity system.
client = Client("https://documents.example.com", token=get_workload_token)
health = client.health()
capabilities = client.capabilities()
scan = client.scan_document(front_bytes, back_bytes, document_type="driver_license", country="DO")
scan = client.get_scan(scan.scan_id)

# Show the fields in your review UI. Only after a human explicitly approves:
reviewed = ReviewedClientIntake(scan_id=scan.scan_id, reviewed_fields=approved_fields)
confirmed = client.confirm_scan(scan.scan_id, reviewed)
intake = confirmed.to_client_intake()  # rejects anything except status='confirmed'
```

`front` is nonempty bytes; `back` is nonempty bytes or `None`. Read files in the
caller so this library never stores paths or uploaded documents on disk. The
client is synchronous and holds no persistent connections. No context manager or
close call is needed. Responses are validated typed models; `py.typed` is shipped.
Unknown response properties are ignored for forward compatibility.

Authentication accepts either a token string or a zero-argument callable returning
a token, invoked on every attempt. Only the supplied bearer token/provider is held
in memory. No provider secret configuration, environment discovery, credential
persistence, FACE-ID SDK, or OCR provider dependency is included.

Defaults: 30-second socket-operation timeout, two GET retries with exponential
backoff starting at 0.25 seconds, 8 MiB response limit. Retries cover transport
failures and HTTP 429/502/503/504. Other statuses, including authentication failures,
are not retried. POST scan and confirmation are **never automatically retried**.
After a submission timeout the outcome is unknown: reconcile through your service
before submitting again. No idempotency contract has been verified, so no
idempotency-key promise is made. Redirects are never followed. TLS certificates
are verified; HTTP is available only for explicitly enabled loopback development.

`DocumentError` contains a fixed safe message and optional `status_code`, never
response bodies, URLs, credentials, images or upstream exception chains. Client
and model string/repr output is redacted. The SDK emits no logs. Model fields and
explicit `model_dump()`/`model_dump_json()` results contain sensitive data by design;
do not log them. Debuggers and traceback tools that capture locals can expose
in-memory secrets and documents; disable local capture in production. Pydantic
validation errors hide input in their displayed text, but structured `.errors()`
may contain input: do not log those either.

See the [Middleware/FACE-ID reference workflow](examples/middleware_face_id.py)
and [versioning policy](docs/versioning.md).

## Development

```sh
python -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/python -m pytest
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/mypy src examples
.venv/bin/python -m build
```

Tests use a real loopback HTTP mock server, synthetic documents and synthetic
tokens. No external service or provider credential is required.
