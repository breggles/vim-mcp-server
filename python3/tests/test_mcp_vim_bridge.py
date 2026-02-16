import threading
import time

import mcp_vim_bridge


def _reset_bridge():
    while not mcp_vim_bridge._request_queue.empty():
        mcp_vim_bridge._request_queue.get_nowait()
    with mcp_vim_bridge._result_lock:
        mcp_vim_bridge._result_slots.clear()
        mcp_vim_bridge._result_events.clear()


class TestDrainRequests:
    def setup_method(self):
        _reset_bridge()

    def test_empty_queue(self):
        assert mcp_vim_bridge.drain_requests() == []

    def test_returns_queued_items(self):
        mcp_vim_bridge._request_queue.put(("id1", "func_a", {"x": 1}))
        mcp_vim_bridge._request_queue.put(("id2", "func_b", {}))
        requests = mcp_vim_bridge.drain_requests()
        assert len(requests) == 2
        assert requests[0] == ("id1", "func_a", {"x": 1})
        assert requests[1] == ("id2", "func_b", {})
        assert mcp_vim_bridge.drain_requests() == []


class TestSubmitAndPostResult:
    def setup_method(self):
        _reset_bridge()

    def test_round_trip(self):
        result_holder = {}

        def submitter():
            result_holder["result"] = mcp_vim_bridge.submit_request(
                "req-1", "get_cursor", {},
            )

        t = threading.Thread(target=submitter)
        t.start()

        time.sleep(0.05)

        requests = mcp_vim_bridge.drain_requests()
        assert len(requests) == 1
        req_id, func_name, args = requests[0]
        assert req_id == "req-1"
        assert func_name == "get_cursor"

        mcp_vim_bridge.post_result("req-1", {"line": 5, "column": 1})
        t.join(timeout=2)

        assert result_holder["result"] == {"line": 5, "column": 1}

    def test_multiple_concurrent_requests(self):
        results = {}

        def submitter(rid, expected):
            results[rid] = mcp_vim_bridge.submit_request(rid, "tool", {})

        threads = []
        for i in range(3):
            t = threading.Thread(target=submitter, args=(f"r-{i}", f"val-{i}"))
            t.start()
            threads.append(t)

        time.sleep(0.05)

        requests = mcp_vim_bridge.drain_requests()
        assert len(requests) == 3

        for req_id, _, _ in requests:
            mcp_vim_bridge.post_result(req_id, f"result-for-{req_id}")

        for t in threads:
            t.join(timeout=2)

        for i in range(3):
            assert results[f"r-{i}"] == f"result-for-r-{i}"


class TestSubmitTimeout:
    def setup_method(self):
        _reset_bridge()

    def test_returns_error_on_timeout(self, monkeypatch):
        monkeypatch.setattr(threading.Event, "wait", lambda self, timeout=None: None)
        result = mcp_vim_bridge.submit_request("timeout-req", "tool", {})
        assert result == {"error": "Timeout waiting for Vim to process request"}
