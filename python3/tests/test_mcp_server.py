import http.client
import json
import socket

import mcp_server


class TestConcurrentConnections:
    def setup_method(self):
        mcp_server.start(0)

        self.port = mcp_server._server.server_address[1]

        self.idle = socket.create_connection(("127.0.0.1", self.port))

    def teardown_method(self):
        self.idle.close()

        mcp_server.stop()

    def test_serves_request_while_another_connection_is_idle(self):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=2)

        body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "ping"})

        conn.request("POST", "/mcp", body, {"Content-Type": "application/json"})

        response = conn.getresponse()

        conn.close()

        assert response.status == 200


class TestKeepAlive:
    def setup_method(self):
        mcp_server.start(0)

        self.port = mcp_server._server.server_address[1]

    def teardown_method(self):
        mcp_server.stop()

    def test_reuses_connection_for_second_request(self):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=2)

        conn.connect()

        sock = conn.sock

        body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "ping"})

        conn.request("POST", "/mcp", body, {"Content-Type": "application/json"})

        first = conn.getresponse()

        first.read()

        conn.request("POST", "/mcp", body, {"Content-Type": "application/json"})

        second = conn.getresponse()

        second.read()

        reused = conn.sock is sock

        conn.close()

        assert first.status == 200

        assert second.status == 200

        assert reused
