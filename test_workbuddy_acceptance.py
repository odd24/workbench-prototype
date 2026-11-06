"""Security and outcome evidence for the optional real-client relay."""

import copy
import json
import unittest

from workbuddy_agent_acceptance import protocol_metadata


class WorkBuddyMetadataTests(unittest.TestCase):
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
