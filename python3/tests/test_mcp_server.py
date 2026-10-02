import http.client
import json
import socket
import time

import pytest

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

        response.read()

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


class TestNotFound:
    def setup_method(self):
        mcp_server.start(0)

        self.port = mcp_server._server.server_address[1]

    def teardown_method(self):
        mcp_server.stop()

    def test_answers_post_with_large_body(self):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=2)

        large_body = "x" * 1_000_000

        conn.request("POST", "/other", large_body)

        time.sleep(0.2)

        response = conn.getresponse()

        response.read()

        conn.close()

        assert response.status == 404


class TestStop:
    def setup_method(self):
        mcp_server.start(0)

        self.port = mcp_server._server.server_address[1]

    def teardown_method(self):
        mcp_server.stop()

    def test_refuses_request_on_open_connection_after_stop(self):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=2)

        body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "ping"})

        conn.request("POST", "/mcp", body, {"Content-Type": "application/json"})

        first = conn.getresponse()

        first.read()

        mcp_server.stop()

        large_body = "x" * 1_000_000

        conn.request("POST", "/mcp", large_body)

        time.sleep(0.2)

        second = conn.getresponse()

        second.read()

        conn.close()

        assert first.status == 200

        assert second.status == 503


class TestStopReleasesPort:
    def setup_method(self):
        mcp_server.start(0)

        self.port = mcp_server._server.server_address[1]

        self.kept = http.client.HTTPConnection("127.0.0.1", self.port, timeout=2)

    def teardown_method(self):
        self.kept.close()

        mcp_server.stop()

    def test_refuses_new_connection_after_stop_while_connection_is_open(self):
        body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "ping"})

        self.kept.request("POST", "/mcp", body, {"Content-Type": "application/json"})

        self.kept.getresponse().read()

        mcp_server.stop()

        with pytest.raises(ConnectionRefusedError):
            socket.create_connection(("127.0.0.1", self.port), timeout=5)
