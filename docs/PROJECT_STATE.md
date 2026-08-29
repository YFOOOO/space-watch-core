# Space Watch Core project state

Status: `R0_REPOSITORY_FOUNDATION_PASS / C0_PARTIAL_ACCEPTED / D0_PARTIAL_ACCEPTED / D1_PENDING`

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

The public cold-start integration was remotely observed at commit
`1e4dddbb928d290b458feeee7c5f6399428a76ec` and tree
`69960ea6a0481ed4716038fd13f883b059190b55`. That exact ref became the C0 execution basis.
A file cannot safely bind the SHA of the commit that contains its own later update; each new
commit or remote effect still requires post-effect read-back and its own authority.

## Phase model

| Phase | Meaning | State |
| --- | --- | --- |
| R0 | Public repository foundation | PASS |
| C0 | Grok Bot App capability preflight | PARTIAL_ACCEPTED_COMPLETE |
| D0 | Supervised synthetic cloud demo | PARTIAL_ACCEPTED_COMPLETE |
| D1 | Supervised live-source demo | LOCAL_IMPLEMENTATION_CANDIDATE |
| O1 | Supervised schedule/routine | PENDING |
| O2 | Formal operation | PENDING |

R0 alone did not prove Grok repository access, cloud execution, artifact export,
persistence, source acquisition, scheduling, or notification capability. The accepted C0
outcome below records only the capabilities actually observed later.

## Stable phase and live authority

- Stable public phase: `R0_REPOSITORY_FOUNDATION_PASS / C0_PARTIAL_ACCEPTED / D0_PARTIAL_ACCEPTED / D1_PENDING`
- Live Gate, next actor, and current effect authorization: owned by the local private authority carrier
- Repository text alone authorizes no external effect
- Grok/cloud execution: not authorized
- Real source access: not authorized
- Schedule, routine, notification, or project write: not authorized
- Commit, push, tag, Release, or repository setting change: not authorized by this file

## C0 accepted outcome

Human accepted a bounded `PARTIAL` C0 observation against exact public commit
`1e4dddbb928d290b458feeee7c5f6399428a76ec` and tree
`69960ea6a0481ed4716038fd13f883b059190b55`.

- anonymous exact-ref access, cold start, and persistent workspace observation passed;
- the standard-library release build passed with 29 files, release file-set SHA-256
  `bd456b82dd2b326e673e3d8971431d86318ee1990062a8b4525cc4e40dc0fec3`, and package
  SHA-256 `4b8668900d071acc2222b2763e4114c3c6017c82aca7149b8c9943af9a22b7b5`;
- the synthetic-only runner passed and stopped at Human Review without source, project,
  routine, or notification effects;
- isolated installation of the test-only `jsonschema` dependency was unavailable, so the
  complete cloud unittest suite did not run;
- accepted `PARTIAL` completes C0 capability observation only. It grants no D0 or later
  effect authority.

## D0 accepted outcome

Human accepted a bounded `PARTIAL` D0 observation against exact public commit
`7805554a4f9ae549ae3271f39d14564906af8e00` and tree
`ff32fac5103eb375b66439a3727461d4d8475921`.

- exact-ref recovery, the standard-library synthetic runner, six-artifact generation, three
  chat attachments, carrier-effect reporting, and the Human Review stop were observed;
- the runner emitted two candidates (`alpha:changed`, `beta:unavailable`) with
  `accepted=false`, `project_truth=false`, `source_acquisition_effect=false`, and no project,
  repository, routine, or notification effect;
- independent attachment byte read-back remained unavailable;
- after an initial clone did not materialize, the Bot performed a second repository
  acquisition attempt despite a zero-retry packet. Human accepted this as a retained D0
  limitation: the runner passed, but prompt-level retry constraints were not runtime-enforced;
- accepted `PARTIAL` completes D0 observation only. It grants no live-source, D1 execution,
  schedule, routine, notification, or project-write authority.

## Next bounded transition

Human accepted the first D1 design scope of exactly three Flight 14 carriers and authorized
local implementation and validation. The current candidate adds repository-enforced exact
basis/hash/path/budget preflight and a single injected acquisition boundary that rejects
redirects, login, search, alternate carriers, and retries. After the first Grok capability
probe reported that its public-web tool could not bind to the injected interface, the local
candidate added a repository-owned standard-library exact-URI HTTP adapter and D1 CLI. This
is Evaluation evidence only; no real carrier was accessed during local validation.
D1 execution, commit, push, live-source access, Grok interaction, schedule, routine,
notification, and project write remain unauthorized.
