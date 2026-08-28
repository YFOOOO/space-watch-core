# Dependency and offline execution binding

- Runtime: CPython `>=3.11`; runtime package dependencies: none.
- Tests: `jsonschema>=4,<5`; locally observed version for this freeze: `4.25.0`.
- Build: Python standard library only (`json`, `hashlib`, `zipfile`, `pathlib`).
- Build backend metadata: `setuptools>=68`; packaging through that backend is not part of the
  frozen offline build command and may require a separately provisioned environment.

The frozen test and build commands assume required tools are already present. They do not
authorize dependency installation, package-index access, or any network request. A future
cloud preflight must bind the exact runtime image, dependency-install command or explicit
no-install condition, and observed versions separately.

The deterministic ZIP claim is bounded to two builds from identical bytes in the observed
local runtime. Cross-Python or cross-zlib byte identity is unavailable until independently
tested.
