"""Synthetic adapter boundary and continuity mapping contracts."""
import copy
import json
from pathlib import Path
import sys
import unittest

import jsonschema

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from space_watch_cloud.research_adapter import adapt_research_readout, research_observation, validate_task


class ResearchAdapterTests(unittest.TestCase):
    def fixture(self, name="f14"):
        return json.loads((ROOT / f"fixtures/research-{name}.json").read_text())

    def adapt(self, snapshot):
        return adapt_research_readout(snapshot, mission_id=snapshot['mission']['id'])

    def test_two_versions_are_schema_valid_and_do_not_mutate_input(self):
        schema = json.loads((ROOT / 'schemas/research-task.schema.json').read_text())
        for name in ('f14', 'nuri'):
            snapshot = self.fixture(name)
            before = copy.deepcopy(snapshot)
            task = self.adapt(snapshot)
            jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker()).validate(task)
            self.assertEqual(snapshot, before)
            self.assertFalse(task['accepted'])
            self.assertFalse(task['snapshot']['external_verification'])
            self.assertNotIn('review', task['tracking'][0])
            self.assertEqual(task['claims'][0]['evidence_refs'], ['official'])
            observation = research_observation(task)
            self.assertEqual(observation['observed_at'], snapshot['as_of'])
            self.assertEqual(observation['facts']['status.name'], 'Synthetic pending')
            self.assertNotIn('headline', observation['facts'])

    def test_fail_closed(self):
        mutations = [lambda s: s.update(schema_version='future'),
                     lambda s: s['mission'].update(id='other'),
                     lambda s: s['sources'].append(copy.deepcopy(s['sources'][0])),
                     lambda s: s['claims'].append(copy.deepcopy(s['claims'][0])),
                     lambda s: s['claims'][0].update(evidence_refs=['missing']),
                     lambda s: s['basis'][0].update(kind='source'),
                     lambda s: s['mission']['aliases'].append(s['mission']['id']),
                     lambda s: s['attention']['items'][0].update(id='other')]
        for mutate in mutations:
            snapshot = self.fixture()
            mutate(snapshot)
            with self.assertRaises(ValueError):
                adapt_research_readout(snapshot, mission_id='synthetic-f14')

    def test_no_local_or_credential_urls(self):
        for url in ['file:///private/source', 'https://user:pass@example.test/source',
                    'http://127.0.0.1/a', 'http://localhost/a', 'https://example.test/a?token=secret']:
            snapshot = self.fixture()
            snapshot['sources'][0]['carrier_url'] = url
            with self.assertRaises(ValueError): self.adapt(snapshot)

    def test_paths_and_exploration_not_exported_as_sources(self):
        snapshot = self.fixture('nuri')
        snapshot['sources'][0]['path'] = '/private/research/file'
        snapshot['exploration'] = {'entry': {'path': '/private/atlas'}}
        task = self.adapt(snapshot)
        self.assertNotIn('/private/', json.dumps(task))

    def test_empty_facts_unavailable_and_unresolved_basis_preserved(self):
        snapshot = self.fixture()
        snapshot['facts'] = {}
        snapshot['basis'].append({'ref': 'unknown', 'kind': 'unresolved'})
        task = self.adapt(snapshot)
        observation = research_observation(task)
        self.assertEqual(observation['status'], 'unavailable')
        self.assertIsNone(observation['facts'])
        self.assertIsNone(observation['raw_sha256'])
        self.assertEqual(task['basis'][-1]['kind'], 'unresolved')

    def test_tampered_portable_task_rejected_before_observation(self):
        original = self.adapt(self.fixture())
        mutations = [lambda t: t.update(accepted=True),
                     lambda t: t.update(project_truth=True),
                     lambda t: t['snapshot'].update(external_verification=True),
                     lambda t: t['facts']['status'].update(private_path='/private/file'),
                     lambda t: t['reviews'][0].update(summary={'private_path': '/private/file'}),
                     lambda t: t['basis'].append({'ref': 'window-claim', 'kind': 'claim'}),
                     lambda t: t.update(extra='unsafe')]
        for mutate in mutations:
            task = copy.deepcopy(original); mutate(task)
            with self.assertRaises(ValueError): validate_task(task)
            with self.assertRaises(ValueError): research_observation(task)

    def test_claim_changes_do_not_change_fact_projection(self):
        snapshot = self.fixture()
        before = research_observation(self.adapt(snapshot))
        snapshot['claims'][0]['evaluation_state'] = 'confirmed'
        snapshot['attention']['items'][0]['headline'] = 'New review conclusion'
        after = research_observation(self.adapt(snapshot))
        self.assertEqual(before['facts'], after['facts'])
        self.assertNotEqual(before['raw_sha256'], after['raw_sha256'])

    def test_locator_and_time_parity(self):
        schema = json.loads((ROOT / 'schemas/research-task.schema.json').read_text())
        for timestamp in ['2026-10-10 00:00:00+00:00', '20261010T000000Z']:
            snapshot = self.fixture(); snapshot['as_of'] = timestamp
            with self.assertRaises(ValueError): self.adapt(snapshot)
        for url in ['https://example.localhost./a', 'https://example.test/a b']:
            snapshot = self.fixture(); snapshot['sources'][0]['carrier_url'] = url
            with self.assertRaises(ValueError): self.adapt(snapshot)
        snapshot = self.fixture(); snapshot['sources'][0]['carrier_url'] = 'http://EXAMPLE.test/a'
        task = self.adapt(snapshot)
        jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker()).validate(task)
