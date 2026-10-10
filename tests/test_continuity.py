"""Synthetic continuity and crash/recovery contracts; no sources or transport."""
import copy
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from jsonschema import Draft202012Validator
from space_watch_cloud import continuity as c

ROOT = Path(__file__).resolve().parents[1]


def observation(mission='F14', source='official', facts=None, **extra):
    return {'mission_id': mission, 'source_id': source, 'observed_at': '2026-10-10T00:00:00Z',
            'status': 'available', 'raw_sha256': 'a' * 64, 'limitations': [],
            'facts': ({'status': 'scheduled'} if extra.get('status', 'available') == 'available' else None) if facts is None else facts, **extra}


class ContinuityTests(unittest.TestCase):
    def ready(self, mission='F14'):
        state = c.initial_state(mission, ['official'])
        return c.apply_observation(state, observation(mission), expected_version=0)

    def test_mission_destination_and_metadata_identity(self):
        f14, candidate = self.ready()
        nuri, other = self.ready('Nuri')
        self.assertNotEqual(candidate['candidate_id'], other['candidate_id'])
        changed, unchanged = c.apply_observation(f14, observation(observed_at='2026-10-11T00:00:00Z',
            raw_sha256='b' * 64, limitations=['synthetic limitation']), expected_version=1)
        self.assertEqual(candidate, unchanged)
        self.assertNotEqual(f14['sources']['official']['last_valid']['raw_sha256'],
                            changed['sources']['official']['last_valid']['raw_sha256'])
        self.assertNotEqual(c.delivery_key(candidate, 'AI'), c.delivery_key(candidate, 'Space'))
        self.assertFalse(candidate['accepted'])
        self.assertFalse(nuri['project_truth'])

    def test_failures_keep_valid_and_recovery_reuses_identity(self):
        state, candidate = self.ready()
        failed, missing = c.apply_observation(state, observation(status='unavailable', facts=None,
            raw_sha256=None, limitations=['HTTP 403']), expected_version=1)
        self.assertIsNone(missing)
        self.assertEqual(state['sources']['official']['last_valid'], failed['sources']['official']['last_valid'])
        self.assertEqual(failed['sources']['official']['last_attempt']['status'], 'unavailable')
        recovered, current = c.apply_observation(failed, observation(), expected_version=2)
        self.assertEqual(candidate, current)
        self.assertEqual(state['version'], 1)  # input remains immutable
        self.assertEqual(recovered['version'], 3)

    def test_incomplete_snapshot_and_stale_basis(self):
        state = c.initial_state('Nuri', ['official', 'catalog'])
        state, candidate = c.apply_observation(state, observation('Nuri'), expected_version=0)
        self.assertIsNone(candidate)
        state, candidate = c.apply_observation(state, observation('Nuri', 'catalog'), expected_version=1)
        self.assertIsNotNone(candidate)
        changed, new = c.apply_observation(state, observation('Nuri', facts={'status': 'launched'}), expected_version=2)
        self.assertNotEqual(candidate['candidate_id'], new['candidate_id'])
        with self.assertRaisesRegex(ValueError, 'stale'):
            c.prepare_delivery(changed, candidate, 'Space', expected_version=3)

    def test_pending_unknown_reconcile_ack_duplicate(self):
        state, candidate = self.ready()
        state, key, action = c.prepare_delivery(state, candidate, 'Space', expected_version=1)
        self.assertEqual(action, 'send')
        attempt = state['deliveries'][key]['attempt_id']
        state, _, action = c.prepare_delivery(state, candidate, 'Space', expected_version=2)
        self.assertEqual(action, 'reconcile')
        state, action = c.reconcile_delivery(state, key, 'unknown', expected_version=3, attempt_id=attempt)
        self.assertEqual(action, 'reconcile')
        state, _, action = c.prepare_delivery(state, candidate, 'Space', expected_version=4)
        self.assertEqual(action, 'reconcile')
        state = c.ack_delivery(state, key, 'synthetic-message-1', expected_version=5, attempt_id=attempt)
        state, _, action = c.prepare_delivery(state, candidate, 'Space', expected_version=6)
        self.assertEqual(action, 'skip')
        with self.assertRaisesRegex(ValueError, 'immutable'):
            c.reconcile_delivery(state, key, 'not_found', expected_version=7, attempt_id=attempt)

    def test_verified_absence_rotates_attempt_and_stale_ack_rejected(self):
        state, candidate = self.ready()
        state, key, _ = c.prepare_delivery(state, candidate, 'Space', expected_version=1)
        original = state['deliveries'][key]['attempt_id']
        state, action = c.reconcile_delivery(state, key, 'not_found', expected_version=2, attempt_id=original)
        self.assertEqual(action, 'send')
        self.assertNotEqual(original, state['deliveries'][key]['attempt_id'])
        with self.assertRaisesRegex(ValueError, 'attempt mismatch'):
            c.ack_delivery(state, key, 'late-receipt', expected_version=3, attempt_id=original)
        changed, _ = c.apply_observation(state, observation(facts={'status': 'launched'}), expected_version=3)
        changed, action = c.reconcile_delivery(changed, key, 'not_found', expected_version=4,
            attempt_id=changed['deliveries'][key]['attempt_id'])
        self.assertEqual(action, 'reconcile')  # old candidate may not be resent

    def test_failed_source_blocks_mixed_snapshot_and_time_reversal(self):
        state = c.initial_state('Nuri', ['official', 'catalog'])
        state, _ = c.apply_observation(state, observation('Nuri'), expected_version=0)
        state, _ = c.apply_observation(state, observation('Nuri', 'catalog'), expected_version=1)
        state, _ = c.apply_observation(state, observation('Nuri', 'catalog', status='unavailable',
            raw_sha256=None), expected_version=2)
        state, mixed = c.apply_observation(state, observation('Nuri'), expected_version=3)
        self.assertIsNone(mixed)
        with self.assertRaisesRegex(ValueError, 'backwards'):
            c.apply_observation(state, observation('Nuri', observed_at='2026-10-09T23:59:59Z'), expected_version=4)
        with self.assertRaisesRegex(ValueError, 'timestamp'):
            c.apply_observation(state, observation('Nuri', observed_at='2026-02-30T00:00:00Z'), expected_version=4)

    def test_cas_and_corrupt_state_fail_closed(self):
        state, candidate = self.ready()
        with self.assertRaisesRegex(ValueError, 'version conflict'):
            c.prepare_delivery(state, candidate, 'Space', expected_version=0)
        corrupted = copy.deepcopy(state)
        corrupted['sources']['official']['last_valid']['facts']['status'] = 'launched'
        with self.assertRaisesRegex(ValueError, 'digest'):
            c.validate_state(corrupted)
        for invalid in [dict(state, accepted=True), dict(state, version=True), dict(state, unexpected=1)]:
            with self.assertRaises(ValueError):
                c.validate_state(invalid)
        with self.assertRaises(ValueError):
            c.apply_observation(state, observation(facts={'observed_at': 'clock'}), expected_version=1)

    def test_schema_runtime_shape_parity(self):
        state, candidate = self.ready()
        state, key, _ = c.prepare_delivery(state, candidate, 'Space', expected_version=1)
        values = {'observation': (c.OBSERVATION_SCHEMA, observation()),
                  'candidate': (c.CANDIDATE_SCHEMA, candidate), 'state': (c.STATE_SCHEMA, state)}
        for name, (runtime_schema, valid) in values.items():
            schema = json.loads((ROOT / f'schemas/continuity-{name}.schema.json').read_text())
            self.assertEqual({k: v for k, v in schema.items() if k != '$schema'}, runtime_schema)
            Draft202012Validator.check_schema(schema)
            validator = Draft202012Validator(schema, format_checker=Draft202012Validator.FORMAT_CHECKER)
            malformed = [dict(valid, unexpected=True), {k: v for k, v in valid.items() if k != next(iter(valid))}]
            if name == 'observation':
                malformed.extend([dict(valid, facts=None), dict(valid, raw_sha256=None),
                                  dict(valid, facts={'limitations': 'bad'}), dict(valid, status='unavailable'),
                                  dict(valid, observed_at='2026-02-30T00:00:00Z')])
            for value in [valid, *malformed]:
                runtime_accepts = True
                try:
                    c._check(value, runtime_schema)
                except ValueError:
                    runtime_accepts = False
                self.assertEqual(runtime_accepts, validator.is_valid(value), (name, value))
        bad = copy.deepcopy(state)
        bad['deliveries'][key]['status'] = 'acked'
        self.assertFalse(Draft202012Validator(c.STATE_SCHEMA).is_valid(bad))
        with self.assertRaises(ValueError):
            c.validate_state(bad)


if __name__ == '__main__':
    unittest.main()
