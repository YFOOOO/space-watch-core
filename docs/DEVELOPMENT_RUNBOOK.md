# Development and release runbook

## Local setup

Use CPython 3.11 or newer. Runtime code has no package dependencies. Tests require an
already-available `jsonschema>=4,<5`; do not install or upgrade dependencies unless the
current task explicitly authorizes that effect.

Run from the repository root:

```text
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
python3 tools/run_shadow.py --input fixtures/synthetic-source-input.json --baseline fixtures/synthetic-baseline.json --baseline-designation fixtures/synthetic-baseline-designation.json --output-dir <new-output-dir> --attempt-id <id> --executed-at <RFC3339-time>
python3 tools/build_release.py --output-dir <new-build-dir>
```

Both output directories must be new and disposable. The runner is not a filesystem sandbox;
the caller owns containment. Do not retain generated output in the release allowlist.

## Change workflow

1. Read `AGENTS.md` and `docs/PROJECT_STATE.md`.
2. Record the exact starting commit, tree, worktree state, current Gate, and authorization.
3. Change only the bounded source, schema, test, tool, or public documentation scope.
4. Keep JSON Schemas and runtime validation fail-closed and behaviorally aligned.
5. Run the complete tests and deterministic twin-build read-back.
6. Confirm `release-files.json` is sorted, unique, self-contained, and free of private or
   historical carriers.
7. Present the candidate, exact changed paths, hashes, and unavailable fields to Human Review.
8. Do not commit or push unless that exact effect is separately authorized.

## D1 local validation

`src/space_watch_cloud/d1.py` owns the D1 preflight and one-shot acquisition state machine;
`src/space_watch_cloud/http_adapter.py` owns the concrete standard-library request and typed
projection boundary. Tests inject fake responses and must not access the three configured
URLs. The exact post-commit ref, packet hashes, disposable root, and budgets are bound only in
a later Human-authorized dispatch. Run only `tools/run_d1.py` for a conforming live attempt.
A caller that bypasses this entrypoint cannot claim a conforming D1 receipt.

## Release contract

`release-files.json` is the only source inclusion authority. A release build adds only
`release-manifest.json` to those files. Exclude governance receipts, local freeze artifacts,
cloud state, source observations, credentials, caches, bytecode, private paths, and history.

A valid deterministic twin build has identical package and manifest hashes, includes LICENSE,
contains no unexpected paths, and binds every payload byte in its manifest. Tests and build
PASS are Evaluation evidence only; Human retains acceptance and effect authority.

## State updates

Keep `docs/PROJECT_STATE.md` concise and public-safe. It may record an already observed prior
commit, but must not guess the SHA of the commit containing its own update. Bind a new exact
ref in the post-commit read-back or dispatch carrier. Never restore a superseded decision from
chat history or an older governance artifact.
