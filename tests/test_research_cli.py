import json
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ResearchCliTests(unittest.TestCase):
    def test_synthetic_replays(self):
        for name in ('research-f14.json', 'research-nuri.json'):
            result = subprocess.run([sys.executable, '-B', str(ROOT / 'tools/research_continuity.py'),
                                     'demo', '--fixture', str(ROOT / 'fixtures' / name)],
                                    capture_output=True, text=True, check=True)
            output = json.loads(result.stdout)
            self.assertEqual(output['actions'], ['send', 'reconcile', 'reconcile', 'skip', 'skip', 'send'])
            self.assertTrue(output['last_valid_retained'])
            for field in ('notification_sent', 'external_verification', 'accepted', 'project_truth'):
                self.assertIs(output[field], False)
            self.assertEqual(result.stderr, '')

    def test_invalid_input_does_not_emit_task(self):
        result = subprocess.run([sys.executable, '-B', str(ROOT / 'tools/research_continuity.py'),
                                 'adapt', '--mission', 'synthetic'], input='{}',
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, '')
        self.assertIn('failed', result.stderr)
