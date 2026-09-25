# Python SDK foundation

Implement a synchronous Python 3.11+ client with validated Pydantic models,
caller-owned bearer token or refreshing callable, finite socket timeout, and
bounded retries for GET transport failures and 429/502/503/504 only. Never retry
POST, including confirmation. Use standard-library HTTP transport without request
logging; enforce HTTPS except explicit local development. Redact model repr and
sanitize validation, authentication, transport and server exceptions.

Contracts are provisional: Codestra-Document-Schemas remote branches contain only
README at commit 57d5a999b006f819da0dc7d1743cf325b3345fc1. Record this limitation;
do not claim upstream compatibility. Expose route configuration. Multipart image
uploads and JSON confirmation are provisional wire assumptions.

Tasks:
1. Test real loopback HTTP behavior: uploads, authentication, retrieval,
   confirmation, retries, timeout, error redaction and intake review gating.
2. Implement typed models, transport and intake helpers to satisfy tests.
3. Document API assumptions, versioning, security and Middleware integration.
4. Run full tests, lint, strict typing, package build and installed-wheel smoke.
5. Review diff, commit and push mission branch without merging.

Defer TypeScript until the canonical schema exists. No provider integrations or
provider credentials belong in this SDK.
