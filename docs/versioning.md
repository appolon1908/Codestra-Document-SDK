# Versioning

Current version: **0.1.0a1** (provisional contract, Python >=3.11).

| SDK | Canonical schema | Service compatibility |
| --- | --- | --- |
| 0.1.0a1 | unavailable at inspected commit 57d5a999b006f819da0dc7d1743cf325b3345fc1 | unverified |

Use PEP 440 versions and semantic versioning after 1.0. Pre-1.0 minor versions
may change public models or method signatures; patch versions fix compatible
behavior. Alpha releases may change wire assumptions and should be pinned exactly.
After 1.0, breaking SDK or required wire changes require a major version; additive
optional fields/methods use minor releases; compatible fixes use patches.

Each release must update pyproject.toml and codestra_document.__version__, record
schema and service compatibility, run tests/lint/type checks, build both wheel and
sdist, and smoke-test the installed wheel. Never publish credentials or document
fixtures from real clients. Publishing/tagging is a separate release action;
this foundation branch is not a package-registry release.
