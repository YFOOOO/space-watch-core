# Space Watch Core v0.2 contract

This repository contains the accepted synthetic comparison core and a D1 candidate for one
supervised Flight 14 public-source observation. D1 binds an exact repository basis, three
exact public carriers, a Human-exported non-authoritative baseline, explicit attempt/runtime
budgets, a disposable output path, and a Human Observation Review stop.

The D1 CLI uses the repository-owned standard-library HTTP adapter. The orchestrator calls
that boundary exactly once per frozen source. The adapter performs one exact-URI GET, follows
no redirects, sends no credentials, exposes no search or alternate carrier, and reads at most
1 MiB. Failure, redirect, overflow, or insufficient typed content becomes `unavailable`.
No D1 run is authorized by repository bytes. It cannot accept observations, create project
truth, notify, schedule, persist cloud state, or write another repository. All candidates
remain `accepted=false` and `project_truth=false`.

The caller/executor is responsible for choosing an approved disposable root and placing the
requested output directory within it. The runner is not a filesystem sandbox: it guarantees
only that the exact target directory does not already exist and that its generated files are
written beneath that target. Runner-unobservable
attachment, cloud-root, and cloud-command effects are reported as
`unavailable/not_observed_by_runner`; an external interaction receipt owns those facts and a
future closeout owns reconciliation.

The baseline cannot designate itself: the runner verifies the baseline file SHA-256 against
the separately supplied designation and fails closed on mismatch.

`release-files.json` is the exact publication allowlist. Files outside it are governance or
local-freeze artifacts and are not part of the standalone release.
