# Space Watch Core project state

Status: `R0_REPOSITORY_FOUNDATION_PASS / C0_GROK_CAPABILITY_PREFLIGHT_PENDING`

This is the public cold-start entry point. It records no secret, credential, private path,
conversation content, or live operational state.

## Accepted and observed foundation

- Repository: `YFOOOO/space-watch-core`
- Provider and visibility: GitHub, public
- Default branch: `main`
- R0 accepted root commit: `8c87a2f99b8555e3ba4fffa31b6c84a360e0d837`
- R0 accepted tree: `6eea00b15ec95fa7c9c08ac38147e130382af9d0`
- R0 release file-set SHA-256: `0535fe7364db8ab0c93d5c6579853fc560f77aa819996eddedc5226f713ec0eb`
- R0 package SHA-256: `bc65bef98b5cfd1d9073404a7e794d2fee6d4d3715bc98fe83f315238adf598d`
- Independent Evaluation accepted by Human: `FINAL_PUBLICATION_REAUDIT_PASS`

The cold-start integration containing this file has been accepted by Human for a local
commit. Its commit and tree identities remain `observable_only_after_commit`. Remote push
and remote acceptance remain separately gated. A file cannot safely bind the SHA of the
commit that contains itself; the C0 dispatch must bind the observed post-integration commit
SHA from the local and remote read-back.

## Phase model

| Phase | Meaning | State |
| --- | --- | --- |
| R0 | Public repository foundation | PASS |
| C0 | Grok Bot App capability preflight | PENDING |
| D0 | Supervised synthetic cloud demo | PENDING |
| D1 | Supervised live-source demo | PENDING |
| O1 | Supervised schedule/routine | PENDING |
| O2 | Formal operation | PENDING |

R0 does not prove Grok repository access, cloud execution, artifact export, persistence,
source acquisition, scheduling, or notification capability.

## Current Gate and authority

- Current Gate: `cold_start_integration_remote_push_human_authorization`
- Next actor: Human
- Current authorized effects: one local cold-start integration commit and effect-free validation
- Grok/cloud execution: not authorized
- Real source access: not authorized
- Schedule, routine, notification, or project write: not authorized
- Remote push, tag, Release, or repository setting change: not authorized

## Next bounded transition

Create and read back the authorized standalone commit, then stop for separate remote-push
authorization. After remote read-back, the Human may bind that exact commit as the immutable
repository input to C0. C0 must use `docs/GROK_CAPABILITY_PREFLIGHT.md`, stop at Human
Capability Review, and must not enable live-source or routine effects.
