# Continuity and research adapter candidate

This additive candidate extracts portable observation and delivery behavior from a research
workflow. It does not replace the accepted O1/D1 pilot, import a project's database, or
authorize source acquisition, publication, scheduling, notifications, or acceptance.

## Boundaries

- The research adapter consumes a caller-provided, versioned single-mission readout. It
  preserves identity, source and claim references, facts, and limitations. Tracking and
  review receipts remain separate from evidence. A snapshot is not a fresh source check.
- Continuity keeps the last valid observation independently of the current failed or
  successful attempt. Acquisition metadata and presentation wording do not create a fact
  delta. Raw evidence bytes and projected facts have separate digests.
- A candidate binds to its observation basis. Candidate generation is neither acceptance
  nor delivery. Delivery preparation, unknown outcome, reconciliation, and acknowledgement
  are separate transitions; repeat suppression uses the destination as part of identity.
- State transitions are pure functions. A deployment must persist state under one writer
  or an actual atomic compare-and-swap boundary. An in-memory version check alone does not
  make concurrent processes or an external message send atomic.

## Integration

The upstream project's existing research readout is the input contract. The adapter does
not scan a filesystem or copy the upstream authority store. Synthetic fixtures exercise
distinct missions without importing private snapshots. Mission-specific interpretation,
source acquisition, authorization, and project writes remain adapters owned by the caller.

Use a pinned repository commit for cloud verification and a fresh disposable directory.
Do not reset an existing cloud checkout. Run the offline demo and tests without dependency
installation or live-source access. A successful synthetic replay establishes transition
behavior only; it does not establish cross-day scheduling or real notification recovery.

Before operational use, validate the same-source no-change path, unavailable-source
retention, changed-fact candidates, unknown delivery reconciliation, destination isolation,
and recovery after persisted-state reload. Human acceptance remains an independent action.

## Offline commands

Run `python3 tools/research_continuity.py demo --fixture fixtures/research-f14.json`
and repeat with `fixtures/research-nuri.json`. Each replay expects
`send, reconcile, reconcile, skip, skip, send`, retains the last valid facts after
a synthetic failure, and uses only an in-memory transport.

Use `python3 tools/research_continuity.py adapt --mission <canonical-id>` with one
readout JSON on stdin. The result is a portable candidate task; it does not write state.
`research_observation` hashes the adapted snapshot, not newly fetched source bytes.
A failed latest attempt on any required source blocks preparing a new send.
An acknowledged delivery remains bound to its destination and qualified receipt.
