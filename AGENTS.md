# Space Watch Core agent instructions

## Cold start

Before changing or running this repository, read these files in order:

1. `docs/PROJECT_STATE.md`
2. `CONTRACT.md`
3. `docs/GROK_CAPABILITY_PREFLIGHT.md` when working on Grok execution
4. `docs/DEVELOPMENT_RUNBOOK.md` when changing source or release contents

Repository bytes, tests, and manifests are implementation evidence. They do not create
Human acceptance or external-effect authority. If the current exact ref, Gate, or effect
authorization is unavailable, stop and request a Human binding instead of inferring it from
an older commit, task, receipt, or conversation.

## Default boundary

Work is effect-free by default. Do not access real sources, Grok, cloud workspaces, private
services, credentials, schedules, routines, notifications, or another repository without an
explicit bounded authorization. Do not commit, push, publish, tag, or create a Release unless
the Human authorizes that exact effect surface.

Never read or publish `.env*`, credentials, tokens, cookies, private keys, browser profiles,
session state, private project data, or conversation transcripts. Keep generated output,
caches, receipts, and local freeze evidence outside `release-files.json`.

## Verification

Run commands from the repository root. Use the commands and lifecycle rules in
`docs/DEVELOPMENT_RUNBOOK.md`. Preserve fail-closed schemas, synthetic-only runner behavior,
deterministic release construction, and the distinction between Observation, Evaluation,
and Human Acceptance.
