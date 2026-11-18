"""Stage deadlines of the disposable graph confirmation pilot."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from concept_map_pilot import GraphAttestedCase
from recovery_pilot import RecoveryCase
from workbench.agent_security import read_json
from workbench.persistence import atomic_write_json


class GraphPilotWindowTests(unittest.TestCase):
    def test_recovery_transition_requires_durable_evidence_and_live_deadline(self):
        with tempfile.TemporaryDirectory() as folder:
            case = RecoveryCase.__new__(RecoveryCase)
            case.gate = Path(folder) / 'case.json'
            case.stop = Path(folder) / 'STOP'
            case.deadline = 15
            case.state = {'phase':'query', 'expires_at':105, 'commit':{'proposal_id':'fixed'}}
            original = ('receipt', 'graph', 'history')
            with patch('recovery_pilot.time.monotonic', return_value=12), patch('recovery_pilot.time.time', return_value=102):
                with patch.object(case, 'current_result', return_value=original):
                    case.advance_window(10, commit=case.state['commit'], result=original)
                self.assertEqual(read_json(case.gate)['expires_at'], 112)
                self.assertEqual(read_json(case.gate)['commit'], {'proposal_id':'fixed'})
                with patch.object(case, 'current_result', return_value=('changed',)):
                    with self.assertRaises(ValueError):
                        case.advance_window(10, commit=case.state['commit'], result=original)
            with patch('recovery_pilot.time.monotonic', side_effect=[20, 23]), patch('recovery_pilot.time.time', return_value=110):
                with patch.object(case, 'current_result', return_value=original):
                    with self.assertRaises(ValueError):
                        case.advance_window(10, commit=case.state['commit'], result=original)
            for clock, wall, stopped in ((22, 110, False), (20, 112, False), (20, 110, True)):
                if stopped:
                    case.stop.touch()
                with patch('recovery_pilot.time.monotonic', return_value=clock), patch('recovery_pilot.time.time', return_value=wall):
                    with self.assertRaises(ValueError):
                        case.advance_window(10, commit=case.state['commit'], result=original)
                self.assertEqual(read_json(case.gate)['expires_at'], 112)

    def test_transition_updates_relay_expiry_and_preserves_binding(self):
        with tempfile.TemporaryDirectory() as folder:
            case = GraphAttestedCase.__new__(GraphAttestedCase)
            case.case_path = Path(folder) / 'case.json'
            case.stop = Path(folder) / 'STOP'
            case.deadline = 15
            case.case = {'expires_at':105, 'request':{'request_id':'fixed'}}
            gate = Path(folder) / 'gate.json'
            binding = {'proposal_id':'fixed', 'version':1, 'preview_digest':'a' * 64}
            atomic_write_json(gate, binding)
            with patch('concept_map_pilot.time.monotonic', return_value=12), patch('concept_map_pilot.time.time', return_value=102):
                case.advance_window(10)
            self.assertEqual(case.deadline, 22)
            self.assertEqual(read_json(case.case_path), {'expires_at':112, 'request':{'request_id':'fixed'}})
            self.assertEqual(read_json(gate), binding)
            for clock, wall, stopped in ((22, 110, False), (20, 112, False), (20, 110, True)):
                if stopped:
                    case.stop.touch()
                with patch('concept_map_pilot.time.monotonic', return_value=clock), patch('concept_map_pilot.time.time', return_value=wall):
                    with self.assertRaises(ValueError):
                        case.advance_window(10)
                self.assertEqual(read_json(case.case_path)['expires_at'], 112)
