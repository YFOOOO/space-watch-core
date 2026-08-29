# Grok Bot App capability preflight and accepted disposition

Status: `C0_PARTIAL_ACCEPTED_COMPLETE / no D0 or later effect authority`

## Purpose

Observe whether the Grok Bot App can use this public repository as an exact, read-only source
and perform a disposable synthetic-only build and test run. This preflight does not acquire
live sources, enable a schedule, create project truth, or accept outputs.

## Frozen public input

- Repository URL: `https://github.com/YFOOOO/space-watch-core`
- Observed C0 subject ref: `1e4dddbb928d290b458feeee7c5f6399428a76ec`
- Required ref policy: exact commit SHA; floating `main` is insufficient
- Expected repository visibility: public
- Expected runtime: CPython 3.11 or newer
- Runtime package dependencies: none
- Test dependency: `jsonschema>=4,<5`, only if already available or separately approved

The observed C0 subject ref above is immutable execution evidence. A later phase must bind
its own already observed exact ref; floating `main` remains insufficient.

## Observed C0 disposition

Human accepted C0 as `PARTIAL` and complete for capability observation. Anonymous exact-ref
access, persistent workspace observation, the standard-library deterministic release build,
the synthetic-only runner, and artifact attachment passed. The Grok carrier could not bind
creation of an isolated environment or installation of the test-only `jsonschema`
dependency, so the complete cloud unittest suite remained unavailable.

This disposition is not a repository failure and does not authorize dependency fallback,
D0, live sources, schedules, routines, notifications, or project effects.

## Frozen requested observations

1. Read the public repository without credentials and prove the exact checked-out commit.
2. Create or identify one disposable cloud workspace.
3. Report the workspace root, persistence behavior, runtime version, available tools, and
   whether dependency installation would be required.
4. Run, without source acquisition:

   ```text
   PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
   python3 tools/build_release.py --output-dir <new-disposable-build-directory>
   ```

5. Read back the test count/result, release manifest, package SHA-256, file count, and exact
   repository commit used.
6. Observe whether artifact export and schedule/routine capabilities exist. Do not export to
   an external project, enable a schedule, create a routine, or send a notification.
7. Return an execution/effect receipt. Runner-unobservable cloud effects must remain
   explicitly `unavailable` unless observed by the Grok carrier.

## Fields requiring Human binding at dispatch

- Exact post-integration commit SHA
- Attempt budget
- Grok Bot App tool or interaction surface
- Disposable cloud root or its carrier-selected rule
- Dependency-install permission and exact command, if required
- Artifact export destination, if any
- Maximum runtime and output budget

No field above may be guessed. If a required capability or binding is absent, use
`CAPABILITY_UNAVAILABLE_SAFE_STOP`.

## Verdict matrix

| Verdict | Meaning |
| --- | --- |
| PASS | Exact ref, disposable execution, tests, build, hashes, and effect receipt are observed |
| PARTIAL | Some observations succeed; no claim is made for unavailable capabilities |
| FAIL | An observed result violates the repository, schema, hash, or effect contract |
| CAPABILITY_UNAVAILABLE_SAFE_STOP | The carrier cannot expose or enforce a required capability safely |

The terminal state is `human_capability_review`. PASS does not authorize D0, D1, O1, or O2.
