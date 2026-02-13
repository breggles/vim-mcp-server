import queue
import threading


_request_queue = queue.Queue()
_result_slots = {}
_result_lock = threading.Lock()
_result_events = {}


def submit_request(request_id, func_name, args):
    event = threading.Event()
    with _result_lock:
        _result_events[request_id] = event
    _request_queue.put((request_id, func_name, args))
    event.wait(timeout=30)
    with _result_lock:
        _result_events.pop(request_id, None)
        result = _result_slots.pop(request_id, None)
    if result is None:
        return {"error": "Timeout waiting for Vim to process request"}
    return result


def post_result(request_id, result):
    with _result_lock:
        _result_slots[request_id] = result
        event = _result_events.get(request_id)
        if event:
            event.set()


def drain_requests():
    requests = []
    while True:
        try:
            req = _request_queue.get_nowait()
            requests.append(req)
        except queue.Empty:
            break
    return requests
