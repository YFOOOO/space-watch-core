# Space Watch Core v0.2

Status: `R0_REPOSITORY_FOUNDATION_PASS / C0_GROK_CAPABILITY_PREFLIGHT_PENDING`

This directory contains a self-contained, generic, synthetic-only repository candidate and
its local governance packet. It is not a nested Git repository, a public release, an effect
request approval, or a runnable cloud deployment.

The release allowlist contains an offline comparison runner, schemas, synthetic fixtures,
tests, and a deterministic build tool. Historical observations, receipts, packages, source
URLs, project-derived baselines, and machine-specific evidence are excluded.

From this standalone repository root, local verification uses only already-available
dependencies described in `DEPENDENCIES.md`:

```text
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
python3 tools/run_shadow.py --input fixtures/synthetic-source-input.json --baseline fixtures/synthetic-baseline.json --baseline-designation fixtures/synthetic-baseline-designation.json --output-dir <new-output-dir> --attempt-id <id> --executed-at <UTC-time>
python3 tools/build_release.py --output-dir <new-build-dir>
```

The caller must place `<new-output-dir>` inside an approved disposable root. The runner does
not enforce repository or sandbox containment; it rejects an existing target and writes its
fixed artifact set beneath the new target only. Baseline identity is bound to a normalized,
non-escaping path relative to this standalone repository root as well as to its SHA-256.

Standalone release layout:

- `AGENTS.md` and `docs/`: cold-start state, bounded Grok preflight, and development runbook;
- `src/space_watch_cloud/`: deterministic comparison core;
- `schemas/`: six fail-closed public JSON Schemas;
- `fixtures/`: synthetic input, baseline, and independent hash-bound designation;
- `tests/`: runner, schema, publication-boundary, and reproducibility checks;
- `tools/`: offline runner and deterministic release builder;
- `release-files.json`: exact standalone allowlist;
- `CONTRACT.md`, `DEPENDENCIES.md`, `LICENSE`, `pyproject.toml`, and `.gitignore`.

Project governance files and `local-freeze/` evidence remain outside the standalone release.

No command in this repository is authorized for cloud or network execution by repository
text alone. Read `docs/PROJECT_STATE.md` before continuing. Public files record stable phase;
the local private authority carrier owns the live Gate, next actor, and effect authorization.
