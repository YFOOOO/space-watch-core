# Grok Bot App capability preflight candidate

Status: `candidate / no Grok or cloud effect authority`

## Purpose

Observe whether the Grok Bot App at grok.com can use this public repository as an exact,
read-only source and perform a disposable synthetic-only build and test run. This preflight
does not acquire live sources, enable a schedule, create project truth, or accept outputs.

## Frozen public input

- Repository URL: `https://github.com/YFOOOO/space-watch-core`
- Required ref: `unavailable_until_cold_start_integration_commit_read_back`
- Required ref policy: exact commit SHA; floating `main` is insufficient
- Expected repository visibility: public
- Expected runtime: CPython 3.11 or newer
- Runtime package dependencies: none
- Test dependency: `jsonschema>=4,<5`, only if already available or separately approved

The R0 commit is provenance, not the C0 execution ref. The Human must insert the observed
post-integration commit SHA into the dispatched request without editing this file to claim a
self-referential binding.

## Requested observations

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
