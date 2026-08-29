# Dependency and offline execution binding

- Runtime: CPython `>=3.11`; runtime package dependencies: none.
- Tests: `jsonschema>=4,<5`; locally observed version for this freeze: `4.25.0`.
- Build: Python standard library only (`json`, `hashlib`, `zipfile`, `pathlib`).
- Build backend metadata: `setuptools>=68`; packaging through that backend is not part of the
  frozen offline build command and may require a separately provisioned environment.

The frozen test and build commands assume required tools are already present. They do not
authorize dependency installation, package-index access, or any network request. The D1 CLI
uses only `urllib` from the standard library, but an exact Human effect packet is still
required before its three network requests. A cloud preflight must bind the exact runtime
image and explicit no-install condition separately.

The deterministic ZIP claim is bounded to two builds from identical bytes in the observed
local runtime. Cross-Python or cross-zlib byte identity is unavailable until independently
tested.
