import uuid


PROTOCOL_VERSION = "2025-06-18"

SERVER_INFO = {
    "name": "vim-mcp-server",
    "version": "0.1.0",
}

SERVER_CAPABILITIES = {
    "tools": {"listChanged": False},
}


def make_response(req_id, result):
    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "result": result,
    }


def make_error(req_id, code, message):
    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "error": {"code": code, "message": message},
    }


def handle_initialize(req_id, params):
    session_id = str(uuid.uuid4())
    result = {
        "protocolVersion": PROTOCOL_VERSION,
        "capabilities": SERVER_CAPABILITIES,
        "serverInfo": SERVER_INFO,
    }
    return make_response(req_id, result), session_id


def handle_tools_list(req_id, tools):
    tool_list = []
    for name, tool in tools.items():
        tool_list.append({
            "name": name,
            "description": tool["description"],
            "inputSchema": tool["inputSchema"],
        })
    return make_response(req_id, {"tools": tool_list})


def handle_tools_call(req_id, params, tool_executor):
    name = params.get("name", "")
    arguments = params.get("arguments", {})
    try:
        result = tool_executor(name, arguments)
    except Exception as e:
        return make_response(req_id, {
            "content": [{"type": "text", "text": str(e)}],
            "isError": True,
        })
    if isinstance(result, dict) and "error" in result:
        return make_response(req_id, {
            "content": [{"type": "text", "text": result["error"]}],
            "isError": True,
        })
    if isinstance(result, str):
        content = [{"type": "text", "text": result}]
    elif isinstance(result, list):
        content = result
    else:
        content = [{"type": "text", "text": str(result)}]
    return make_response(req_id, {"content": content})


def route_request(method, req_id, params, tools, tool_executor):
    if method == "initialize":
        return handle_initialize(req_id, params)
    if method == "notifications/initialized":
        return None, None
    if method == "tools/list":
        return handle_tools_list(req_id, tools), None
    if method == "tools/call":
        return handle_tools_call(req_id, params, tool_executor), None
    if method == "ping":
        return make_response(req_id, {}), None
    return make_error(req_id, -32601, f"Method not found: {method}"), None
