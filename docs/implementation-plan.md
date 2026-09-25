# Implementation status

The SDK is now aligned to the standalone Codestra Document Intelligence v1 API.

## Transport
- HTTPS by default; loopback HTTP only when explicitly enabled for development.
- Caller supplies a bearer/workload token.
- GET operations may retry selected transient failures.
- POST scan/confirm operations are never blindly retried.
- Responses are size bounded and validated through typed Pydantic models.
- No request or response logging is emitted by the SDK.

## Current v1 operations
1. health
2. capabilities
3. submit document scan using JSON base64 images
4. list tenant-scoped recent scans
5. get scan
6. confirm reviewed corrections
7. retrieve FACE-ID handoff reference

## Product boundaries
- No local persistence.
- No OCR implementation.
- No FACE-ID implementation.
- No Keycloak/OpenBao logic.
- No raw provider credentials.
- Middleware V3 remains the cross-system integration authority.

## Next SDK work
- expose optional Idempotency-Key support without enabling blind retry
- generated models from pinned OpenAPI/schema artifacts
- asynchronous client variant
- TypeScript SDK parity
- package publication/version provenance
