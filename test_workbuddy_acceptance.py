"""Security and outcome evidence for the optional real-client relay."""

import copy
import json
import tempfile
import unittest
from pathlib import Path

from workbuddy_agent_acceptance import (READONLY_PILOT_TOOLS, ProtocolFaultProbe, installed_cli_bundle,
                                       protocol_metadata, restrict_pilot_catalog)


class WorkBuddyMetadataTests(unittest.TestCase):
    def test_pilot_catalog_filters_tools_and_rejects_missing_or_duplicate_entries(self):
        allowed = [{'name':name, 'inputSchema':{'type':'object'}} for name in READONLY_PILOT_TOOLS]
        reply = {'jsonrpc':'2.0', 'id':17,
                 'result':{'tools':allowed + [{'name':'workbench_prepare_proposal'}], 'nextCursor':'unexpected'}}
        original = copy.deepcopy(reply)
        self.assertEqual(restrict_pilot_catalog(reply), {'jsonrpc':'2.0', 'id':17, 'result':{'tools':allowed}})
        self.assertEqual(reply, original)
        for tools in (allowed[:-1], allowed + [allowed[0]], None):
            with self.subTest(tools=tools):
                reply['result']['tools'] = tools
                result = restrict_pilot_catalog(reply)
                self.assertEqual(result['id'], 17)
                self.assertEqual(result['error']['code'], -32603)
                self.assertNotIn('result', result)

    def test_original_launcher_selection_preserves_full_and_supports_lite_only(self):
        with tempfile.TemporaryDirectory() as directory:
            install = Path(directory)
            dist = install / "resources" / "app.asar.unpacked" / "cli" / "dist"
            dist.mkdir(parents=True)
            self.assertEqual(installed_cli_bundle(install), "default")
            (dist / "codebuddy-lite-wb.mjs").write_text("", encoding="utf-8")
            self.assertEqual(installed_cli_bundle(install), "lite-wb")
            (dist / "codebuddy.js").write_text("", encoding="utf-8")
            self.assertEqual(installed_cli_bundle(install), "default")

    def test_cancellation_correlates_without_hiding_late_outcome_or_secrets(self):
        pending = {}
        protocol_metadata({"id": "PRIVATE_ID", "method": "tools/call", "params": {
            "name": "workbench_commit_proposal", "arguments": {"body": "PRIVATE_BODY"}}}, pending)
        message = {"method": "notifications/cancelled", "params": {
            "requestId": "PRIVATE_ID", "reason": "PRIVATE_REASON"}}
        original = copy.deepcopy(message)
        event = protocol_metadata(message, pending)
        self.assertEqual(event, {"method": "notifications/cancelled", "cancelled_request_pending": True,
                                "cancelled_tool": "workbench_commit_proposal"})
        self.assertEqual(message, original)
        self.assertEqual(pending, {"PRIVATE_ID": "workbench_commit_proposal"})
        outcome = protocol_metadata({"id": "PRIVATE_ID", "result": {"isError": False}}, pending)
        self.assertEqual(outcome, {"tool": "workbench_commit_proposal", "tool_is_error": False})
        self.assertEqual(protocol_metadata(message, pending),
                         {"method": "notifications/cancelled", "cancelled_request_pending": False})
        self.assertNotIn("PRIVATE", json.dumps([event, outcome]))

    def test_unmatched_or_malformed_cancellation_does_not_consume_pending(self):
        for params in ({"requestId": "unknown"}, {"requestId": []}, {"requestId": True}, None):
            pending = {1: "workbench_search"}
            event = protocol_metadata({"method": "notifications/cancelled", "params": params}, pending)
            self.assertEqual(event, {"method": "notifications/cancelled", "cancelled_request_pending": False})
            self.assertEqual(pending, {1: "workbench_search"})

    def test_explicit_fault_probe_consumes_only_its_own_replies(self):
        self.assertEqual(ProtocolFaultProbe().requests(), [])
        probe = ProtocolFaultProbe(True)
        messages = probe.requests()
        self.assertEqual(probe.requests(), [])
        self.assertEqual([message["method"] for message in messages], ["ping", "workbench/probe_unknown_method"])
        normal = {"id": "normal-tool", "result": {"content": "PRIVATE"}}
        self.assertIsNone(probe.consume(normal))
        self.assertFalse(probe.completed.is_set())
        ping = probe.consume({"id": messages[0]["id"], "result": {}})
        unknown = probe.consume({"id": messages[1]["id"], "error": {"code": -32601, "data": "PRIVATE"}})
        self.assertEqual(ping, {"fixture_reply": "ping", "valid": True})
        self.assertEqual(unknown, {"fixture_reply": "unknown_method", "valid": True, "error_code": -32601})
        self.assertTrue(probe.completed.is_set())
        self.assertNotIn("PRIVATE", json.dumps([ping, unknown]))
        self.assertIsNone(probe.consume({"id": messages[0]["id"], "result": {}}))

    def test_fault_probe_does_not_treat_unexpected_responses_as_success(self):
        probe = ProtocolFaultProbe(True)
        messages = probe.requests()
        ping = probe.consume({"id": messages[0]["id"], "result": {"unexpected": True}})
        unknown = probe.consume({"id": messages[1]["id"], "error": "PRIVATE"})
        self.assertFalse(ping["valid"])
        self.assertFalse(unknown["valid"])
        another = ProtocolFaultProbe(True)
        invalid_code = another.requests()[1]["id"]
        self.assertFalse(another.consume({"id": invalid_code, "error": {"code": -32601.0}})["valid"])

    def test_interleaved_outcomes_exclude_secrets_and_business_content(self):
        pending = {}
        messages = [
            {"id": "private-request-A", "method": "tools/call", "params": {
                "name": "workbench_search", "arguments": {"query": "SECRET_ARGUMENT"}}},
            {"id": 2, "method": "tools/call", "params": {
                "name": "workbench_get_item", "arguments": {"token": "SECRET_TOKEN"}}},
            {"id": 2, "result": {"content": [{"text": "SECRET_BODY"}]}},
            {"id": "private-request-A", "result": {"isError": True,
                "content": [{"text": "SECRET_ERROR"}], "structuredContent": {"token": "SECRET_TOKEN"}}},
        ]
        original = copy.deepcopy(messages)
        events = [protocol_metadata(message, pending) for message in messages]
        self.assertEqual(events[2], {"tool": "workbench_get_item", "tool_is_error": False})
        self.assertEqual(events[3], {"tool": "workbench_search", "tool_is_error": True})
        self.assertEqual(pending, {})
        self.assertEqual(messages, original)
        serialized = json.dumps(events)
        for secret in ("SECRET_ARGUMENT", "SECRET_TOKEN", "SECRET_BODY", "SECRET_ERROR", "private-request-A"):
            self.assertNotIn(secret, serialized)

    def test_rpc_errors_and_malformed_error_flags_remain_distinct(self):
        pending = {1: "workbench_search", 2: "workbench_get_item"}
        rpc = protocol_metadata({"id": 1, "error": {"code": -32602, "message": "PRIVATE", "data": "PRIVATE"}}, pending)
        malformed = protocol_metadata({"id": 2, "result": {"isError": "PRIVATE"}}, pending)
        self.assertEqual(rpc, {"tool": "workbench_search", "error_code": -32602})
        self.assertEqual(malformed, {"tool": "workbench_get_item", "tool_result_malformed": True})
        self.assertNotIn("PRIVATE", json.dumps([rpc, malformed]))

    def test_abandoned_requests_have_bounded_metadata(self):
        pending = {}
        for request_id in range(300):
            protocol_metadata({"id": request_id, "method": "tools/call", "params": {
                "name": "workbench_search", "arguments": {"body": "PRIVATE"}}}, pending)
        self.assertEqual(len(pending), 256)
        self.assertNotIn(0, pending)
        self.assertEqual(protocol_metadata({"id": 0, "result": {"isError": True}}, pending), {})
        self.assertEqual(protocol_metadata({"id": 299, "result": {"isError": True}}, pending),
                         {"tool": "workbench_search", "tool_is_error": True})


if __name__ == "__main__":
    unittest.main()
