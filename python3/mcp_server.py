import json
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

import mcp_protocol
import mcp_tools


_server = None
_server_thread = None
_session_id = None


class McpRequestHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path != "/mcp":
            self.send_error(404)
            return
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)
        try:
            msg = json.loads(body)
        except json.JSONDecodeError:
            self._send_json(
                mcp_protocol.make_error(None, -32700, "Parse error"),
                200,
            )
            return
        method = msg.get("method", "")
        req_id = msg.get("id")
        params = msg.get("params", {})
        is_notification = req_id is None
        response, new_session_id = mcp_protocol.route_request(
            method, req_id, params,
            mcp_tools.TOOL_DEFINITIONS,
            mcp_tools.call_tool,
        )
        global _session_id
        if new_session_id is not None:
            _session_id = new_session_id
        if is_notification:
            self.send_response(202)
            self.send_header("Content-Length", "0")
            if _session_id:
                self.send_header("Mcp-Session-Id", _session_id)
            self.end_headers()
            return
        self._send_json(response, 200)

    def do_GET(self):
        if self.path != "/mcp":
            self.send_error(404)
            return
        self.send_response(405)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_DELETE(self):
        if self.path != "/mcp":
            self.send_error(404)
            return
        global _session_id
        _session_id = None
        self.send_response(200)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _send_json(self, data, status_code):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        if _session_id:
            self.send_header("Mcp-Session-Id", _session_id)
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass


def start(port=8765):
    global _server, _server_thread
    if _server is not None:
        return f"MCP server already running on port {port}"
    _server = HTTPServer(("127.0.0.1", port), McpRequestHandler)
    _server_thread = threading.Thread(target=_server.serve_forever, daemon=True)
    _server_thread.start()
    return f"MCP server started on http://127.0.0.1:{port}/mcp"


def stop():
    global _server, _server_thread, _session_id
    if _server is None:
        return "MCP server is not running"
    _server.shutdown()
    _server = None
    _server_thread = None
    _session_id = None
    return "MCP server stopped"


def is_running():
    return _server is not None
