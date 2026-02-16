import uuid
from unittest.mock import patch

import mcp_protocol


class TestMakeResponse:
    def test_structure(self):
        resp = mcp_protocol.make_response(1, {"key": "value"})
        assert resp == {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {"key": "value"},
        }

    def test_string_id(self):
        resp = mcp_protocol.make_response("abc", "ok")
        assert resp["id"] == "abc"
        assert resp["result"] == "ok"

    def test_none_id(self):
        resp = mcp_protocol.make_response(None, {})
        assert resp["id"] is None


class TestMakeError:
    def test_structure(self):
        resp = mcp_protocol.make_error(1, -32600, "Invalid Request")
        assert resp == {
            "jsonrpc": "2.0",
            "id": 1,
            "error": {"code": -32600, "message": "Invalid Request"},
        }

    def test_none_id(self):
        resp = mcp_protocol.make_error(None, -32700, "Parse error")
        assert resp["id"] is None
        assert resp["error"]["code"] == -32700


class TestHandleInitialize:
    def test_returns_response_and_session_id(self):
        response, session_id = mcp_protocol.handle_initialize(1, {})
        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 1
        result = response["result"]
        assert result["protocolVersion"] == mcp_protocol.PROTOCOL_VERSION
        assert result["capabilities"] == mcp_protocol.SERVER_CAPABILITIES
        assert result["serverInfo"] == mcp_protocol.SERVER_INFO
        uuid.UUID(session_id)

    def test_session_ids_are_unique(self):
        _, id1 = mcp_protocol.handle_initialize(1, {})
        _, id2 = mcp_protocol.handle_initialize(2, {})
        assert id1 != id2


class TestHandleToolsList:
    def test_transforms_tools_dict(self):
        tools = {
            "tool_a": {
                "description": "Does A",
                "inputSchema": {"type": "object", "properties": {}},
            },
            "tool_b": {
                "description": "Does B",
                "inputSchema": {"type": "object", "properties": {"x": {"type": "integer"}}},
            },
        }
        resp = mcp_protocol.handle_tools_list(1, tools)
        tool_list = resp["result"]["tools"]
        assert len(tool_list) == 2
        names = {t["name"] for t in tool_list}
        assert names == {"tool_a", "tool_b"}
        for t in tool_list:
            assert "description" in t
            assert "inputSchema" in t

    def test_empty_tools(self):
        resp = mcp_protocol.handle_tools_list(1, {})
        assert resp["result"]["tools"] == []


class TestHandleToolsCall:
    def test_string_result(self):
        executor = lambda name, args: "hello"
        resp = mcp_protocol.handle_tools_call(1, {"name": "t", "arguments": {}}, executor)
        result = resp["result"]
        assert result["content"] == [{"type": "text", "text": "hello"}]
        assert "isError" not in result

    def test_list_result(self):
        content = [{"type": "text", "text": "a"}, {"type": "text", "text": "b"}]
        executor = lambda name, args: content
        resp = mcp_protocol.handle_tools_call(1, {"name": "t"}, executor)
        assert resp["result"]["content"] == content

    def test_error_dict_result(self):
        executor = lambda name, args: {"error": "something broke"}
        resp = mcp_protocol.handle_tools_call(1, {"name": "t"}, executor)
        result = resp["result"]
        assert result["isError"] is True
        assert result["content"][0]["text"] == "something broke"

    def test_executor_exception(self):
        def executor(name, args):
            raise RuntimeError("boom")
        resp = mcp_protocol.handle_tools_call(1, {"name": "t"}, executor)
        result = resp["result"]
        assert result["isError"] is True
        assert "boom" in result["content"][0]["text"]

    def test_other_type_result(self):
        executor = lambda name, args: 42
        resp = mcp_protocol.handle_tools_call(1, {"name": "t"}, executor)
        assert resp["result"]["content"] == [{"type": "text", "text": "42"}]

    def test_missing_name_defaults_to_empty(self):
        calls = []
        def executor(name, args):
            calls.append(name)
            return "ok"
        mcp_protocol.handle_tools_call(1, {}, executor)
        assert calls == [""]


class TestRouteRequest:
    def test_initialize(self):
        resp, session_id = mcp_protocol.route_request(
            "initialize", 1, {}, {}, None,
        )
        assert resp["result"]["protocolVersion"] == mcp_protocol.PROTOCOL_VERSION
        assert session_id is not None

    def test_notifications_initialized(self):
        resp, session_id = mcp_protocol.route_request(
            "notifications/initialized", None, {}, {}, None,
        )
        assert resp is None
        assert session_id is None

    def test_tools_list(self):
        tools = {
            "my_tool": {
                "description": "A tool",
                "inputSchema": {"type": "object", "properties": {}},
            },
        }
        resp, session_id = mcp_protocol.route_request(
            "tools/list", 1, {}, tools, None,
        )
        assert len(resp["result"]["tools"]) == 1
        assert session_id is None

    def test_tools_call(self):
        executor = lambda name, args: "result"
        resp, session_id = mcp_protocol.route_request(
            "tools/call", 1, {"name": "t"}, {}, executor,
        )
        assert resp["result"]["content"][0]["text"] == "result"
        assert session_id is None

    def test_ping(self):
        resp, session_id = mcp_protocol.route_request(
            "ping", 1, {}, {}, None,
        )
        assert resp["result"] == {}
        assert session_id is None

    def test_unknown_method(self):
        resp, session_id = mcp_protocol.route_request(
            "nonexistent/method", 1, {}, {}, None,
        )
        assert resp["error"]["code"] == -32601
        assert "nonexistent/method" in resp["error"]["message"]
        assert session_id is None
