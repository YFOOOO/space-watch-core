# Space Watch Core v0.2 contract

This repository candidate is a generic, offline, synthetic-only comparison core. It accepts
frozen JSON input, a synthetic comparison baseline, and an independent hash-bound baseline
designation, emits review candidates and an execution receipt, and stops at Human Review.

It does not fetch sources, contain mission-specific URLs, accept observations, create project
truth, access a network, notify, schedule, persist cloud state, or write another repository.
All candidates remain `accepted=false` and `project_truth=false`.

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
