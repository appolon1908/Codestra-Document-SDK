# Document Intelligence v1 contract

This SDK is aligned to the standalone Codestra Document Intelligence API.

Canonical cross-system path:

`Caddy -> Kong -> Middleware V3 :8095 -> Document Intelligence`

The SDK receives a workload bearer token from its caller. It does not mint tokens,
call Keycloak, call OCR providers, or call FACE-ID directly.

| SDK method | HTTP route | Body / response |
| --- | --- | --- |
| `health()` | `GET /healthz` | `{"status":"ok"}` |
| `capabilities()` | `GET /v1/capabilities` | typed service capabilities |
| `scan_document()` | `POST /v1/documents/scan` | JSON base64 front/back images + document type/country |
| `list_recent()` | `GET /v1/documents?limit=&cursor=` | tenant-scoped scan summaries |
| `get_scan()` | `GET /v1/documents/{scan_id}` | full tenant-scoped scan result |
| `confirm_scan()` | `POST /v1/documents/{scan_id}/confirm` | `{"corrections": {...}}` |
| `get_face_id_handoff()` | `GET /v1/documents/{scan_id}/face-id-handoff` | reviewed client-ready reference object |

## Status model

Document Intelligence exposes `pending_review`, `confirmed`, and `failed`.
Only `confirmed` results may be converted into a reviewed client-intake object.

## Privacy boundary

- Raw document images are held in request memory only by the SDK.
- The SDK sends JSON base64 because that is the current API contract; it writes no temporary image files.
- Clear document numbers may appear transiently in pending-review responses and therefore must never be logged.
- Confirmed service responses must use protected values/last-four references.
- `repr()` and `str()` for SDK models are redacted, but explicit model dumps contain real fields and remain sensitive.
- The SDK never treats OCR or QR extraction as government authenticity verification.

## FACE-ID boundary

`get_face_id_handoff()` returns the Document Intelligence handoff object. Middleware
V3 owns any downstream FACE-ID mapping, authorization, credentials, and effectful
client creation. The SDK has no FACE-ID dependency.
