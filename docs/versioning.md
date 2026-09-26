# Versioning

Current version: **0.2.0**.

The SDK follows semantic versioning. Wire compatibility is tied to the standalone
Document Intelligence v1 API and versioned Document Schemas contracts.

| SDK version | Document Intelligence | Document Schemas | Status |
| --- | --- | --- | --- |
| 0.2.0 | v1 integration branch | v1 / 1.0.0 contracts | aligned |
| 0.1.0a1 | provisional pre-contract surface | unavailable at original foundation | superseded |

Breaking route, request, status, or response-model changes require a new SDK minor
or major version depending on compatibility impact. New optional response fields
are accepted because SDK models ignore unknown fields for forward compatibility.
