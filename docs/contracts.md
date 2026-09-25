# Contract status

The remote `ingtrader21-spec/Codestra-Document-Schemas` repository at commit
`57d5a999b006f819da0dc7d1743cf325b3345fc1` contained only README.md on all
branches, including `mission/document-intelligence-foundation-20260925`, when
inspected on 2026-09-25. No authoritative request/response schemas or OpenAPI
contract were available. The following is an explicit provisional integration
surface, not a claim of alignment with unpublished schemas.

| Method | Default route | Body / response |
| --- | --- | --- |
| health | GET /health | `{status: string}` |
| capabilities | GET /v1/capabilities | `{document_types: string[], countries: string[]}` |
| scan_document | POST /v1/scans | multipart front, optional back, document_type, country → ScanResult |
| get_scan | GET /v1/scans/{scan_id} | ScanResult |
| confirm_scan | POST /v1/scans/{scan_id}/confirm | ReviewedClientIntake → ScanResult |

ScanResult has `scan_id`, `status` (pending, processing, needs_review, confirmed,
failed), and `fields` (JSON object, default empty). ReviewedClientIntake has
`scan_id` and `reviewed_fields` (JSON object). Images are uploaded as opaque bytes
with generic front.bin/back.bin filenames and application/octet-stream media type.
A caller can customize routes with `Routes`; base URL path prefixes are preserved.
Routing customization does not adapt incompatible payload schemas.

Before a stable release, pin the published schema commit/version, replace these
assumptions with canonical models, add canonical valid/invalid fixtures and
contract tests, verify routes/content types/statuses against Middleware, and
record compatibility in the versioning matrix. Human review is caller-attested;
the server must enforce authorization and review policy. Extracted fields alone
never constitute reviewed intake.
