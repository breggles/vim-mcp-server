import json
import uuid

import mcp_vim_bridge


TOOL_DEFINITIONS = {
    "list_buffers": {
        "description": (
            "List all open buffers in Vim. Returns buffer number, file path, "
            "whether the buffer is modified, whether the buffer is the "
            "active buffer, and line count for each buffer."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
    },
    "get_buffer": {
        "description": (
            "Read the contents of a buffer. Specify the buffer by number or "
            "file path. Optionally restrict to a line range (1-based, inclusive)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "buffer_id": {
                    "type": "integer",
                    "description": "Buffer number. Omit to use the current buffer.",
                },
                "buffer_path": {
                    "type": "string",
                    "description": "File path of the buffer. Omit to use the current buffer.",
                },
                "start_line": {
                    "type": "integer",
                    "description": "First line to read (1-based, inclusive). Omit to start from line 1.",
                },
                "end_line": {
                    "type": "integer",
                    "description": "Last line to read (1-based, inclusive). Omit to read to end of buffer.",
                },
            },
            "additionalProperties": False,
        },
    },
    "edit_buffer": {
        "description": (
            "Modify lines in a buffer. Supports replacing a range of lines, "
            "inserting lines at a position, or deleting lines. Line numbers are "
            "1-based and inclusive. Must be explicitly enabled via "
            "g:mcp_server_allow_edit (disabled by default)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "buffer_id": {
                    "type": "integer",
                    "description": "Buffer number. Omit to use the current buffer.",
                },
                "buffer_path": {
                    "type": "string",
                    "description": "File path of the buffer. Omit to use the current buffer.",
                },
                "action": {
                    "type": "string",
                    "enum": ["replace", "insert", "delete"],
                    "description": (
                        "'replace': replace lines start_line..end_line with new_lines. "
                        "'insert': insert new_lines after the given start_line (0 to insert at top). "
                        "'delete': delete lines start_line..end_line."
                    ),
                },
                "start_line": {
                    "type": "integer",
                    "description": "First line of the range (1-based). For insert, the line after which to insert (0 = top).",
                },
                "end_line": {
                    "type": "integer",
                    "description": "Last line of the range (1-based, inclusive). Required for replace and delete.",
                },
                "new_lines": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Lines to insert or replace with. Required for replace and insert.",
                },
            },
            "required": ["action", "start_line"],
            "additionalProperties": False,
        },
    },
    "open_file": {
        "description": (
            "Open a file in Vim using :edit. If the file is already open, "
            "switches to that buffer. After opening, use set_cursor to move "
            "to the line most relevant to the current task, so the user sees "
            "it immediately. "
            "Only use this to show a single file. When presenting multiple "
            "file locations to the user, use set_quickfix_list instead so "
            "the user can navigate them with :cnext/:cprev."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Absolute or relative file path to open.",
                },
            },
            "required": ["path"],
            "additionalProperties": False,
        },
    },
    "save_buffer": {
        "description": (
            "Save a buffer to disk using :write. "
            "Must be explicitly enabled via g:mcp_server_allow_save (disabled by default)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "buffer_id": {
                    "type": "integer",
                    "description": "Buffer number. Omit to use the current buffer.",
                },
                "buffer_path": {
                    "type": "string",
                    "description": "File path of the buffer. Omit to use the current buffer.",
                },
            },
            "additionalProperties": False,
        },
    },
    "close_buffer": {
        "description": "Close a buffer using :bdelete. If the buffer has unsaved changes, use force=true to discard them.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "buffer_id": {
                    "type": "integer",
                    "description": "Buffer number. Omit to use the current buffer.",
                },
                "buffer_path": {
                    "type": "string",
                    "description": "File path of the buffer. Omit to use the current buffer.",
                },
                "force": {
                    "type": "boolean",
                    "description": "Force close even if buffer has unsaved changes. Default false.",
                },
            },
            "additionalProperties": False,
        },
    },
    "get_cursor": {
        "description": "Get the current cursor position: buffer number, line (1-based), and column (1-based).",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
    },
    "set_cursor": {
        "description": "Move the cursor to a specific line and column in the current buffer.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "line": {
                    "type": "integer",
                    "description": "Line number (1-based).",
                },
                "column": {
                    "type": "integer",
                    "description": "Column number (1-based). Defaults to 1.",
                },
            },
            "required": ["line"],
            "additionalProperties": False,
        },
    },
    "get_visual_selection": {
        "description": (
            "Get the current or last visual selection in Vim. Returns the "
            "selected text, the selection type (v for characterwise, V for "
            "linewise, ctrl-v for blockwise), and the start/end positions. "
            "If Vim is currently in visual mode, returns the active selection. "
            "Otherwise, returns the last visual selection."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
    },
    "execute_command": {
        "description": (
            "Execute an arbitrary Vim Ex command. This is a powerful escape hatch. "
            "Must be explicitly enabled via g:mcp_server_allow_execute (disabled by default)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The Vim Ex command to execute (e.g. '%s/foo/bar/g').",
                },
            },
            "required": ["command"],
            "additionalProperties": False,
        },
    },
    "get_quickfix_list": {
        "description": "Get the current quickfix list entries.",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
    },
    "set_quickfix_list": {
        "description": (
            "Set the quickfix list. Replaces the current quickfix list with "
            "the given entries. Each entry has a filename, line number, and "
            "description text. Optionally opens the quickfix window. "
            "Prefer this over multiple open_file calls when presenting two "
            "or more file locations to the user. "
            "For a single location, prefer open_file and set_cursor instead."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "entries": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "filename": {
                                "type": "string",
                                "description": "File path.",
                            },
                            "line": {
                                "type": "integer",
                                "description": "Line number (1-based).",
                            },
                            "column": {
                                "type": "integer",
                                "description": "Column number (1-based).",
                            },
                            "text": {
                                "type": "string",
                                "description": "Description text for the entry.",
                            },
                            "type": {
                                "type": "string",
                                "description": "Single-letter type: E(rror), W(arning), I(nfo), N(ote), or H(int).",
                            },
                        },
                        "required": ["filename", "line", "text"],
                        "additionalProperties": False,
                    },
                    "description": "List of quickfix entries.",
                },
                "title": {
                    "type": "string",
                    "description": "Title for the quickfix list.",
                },
                "open": {
                    "type": "boolean",
                    "description": "Open the quickfix window after setting the list. Default false.",
                },
            },
            "required": ["entries"],
            "additionalProperties": False,
        },
    },
    "get_location_list": {
        "description": "Get the location list entries for the current window.",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
    },
    "set_location_list": {
        "description": (
            "Set the location list for the current window. Replaces the "
            "current location list with the given entries. Each entry has a "
            "filename, line number, and description text. Optionally opens "
            "the location window. "
            "Prefer this over multiple open_file calls when presenting two "
            "or more file locations to the user. "
            "For a single location, prefer open_file and set_cursor instead."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "entries": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "filename": {
                                "type": "string",
                                "description": "File path.",
                            },
                            "line": {
                                "type": "integer",
                                "description": "Line number (1-based).",
                            },
                            "column": {
                                "type": "integer",
                                "description": "Column number (1-based).",
                            },
                            "text": {
                                "type": "string",
                                "description": "Description text for the entry.",
                            },
                            "type": {
                                "type": "string",
                                "description": "Single-letter type: E(rror), W(arning), I(nfo), N(ote), or H(int).",
                            },
                        },
                        "required": ["filename", "line", "text"],
                        "additionalProperties": False,
                    },
                    "description": "List of location list entries.",
                },
                "title": {
                    "type": "string",
                    "description": "Title for the location list.",
                },
                "open": {
                    "type": "boolean",
                    "description": "Open the location window after setting the list. Default false.",
                },
            },
            "required": ["entries"],
            "additionalProperties": False,
        },
    },
    "get_messages": {
        "description": (
            "Get Vim's message history. Returns the messages that Vim has "
            "displayed, including errors, warnings, and informational "
            "messages. This is the output of the :messages command."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
    },
    "show_diff": {
        "description": (
            "Open a side-by-side diff view in Vim. Supports two modes: "
            "content mode (provide content_a and content_b strings "
            "to diff arbitrary text, e.g. from git or GitHub)"
            "and file mode (provide file_a and file_b paths to diff files on disk)."
            "Prefer content mode where possible."
            "In content mode, optional label_a and label_b set the buffer "
            "names. Always opens a vertical split in a new tab page. "
            "Call multiple times to load several diffs."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "file_a": {
                    "type": "string",
                    "description": "Path to the first file (left side).",
                },
                "file_b": {
                    "type": "string",
                    "description": "Path to the second file (right side).",
                },
                "content_a": {
                    "type": "string",
                    "description": "Text content for the left side.",
                },
                "content_b": {
                    "type": "string",
                    "description": "Text content for the right side.",
                },
                "label_a": {
                    "type": "string",
                    "description": "Display name for the left buffer (content mode only). Defaults to 'a'.",
                },
                "label_b": {
                    "type": "string",
                    "description": "Display name for the right buffer (content mode only). Defaults to 'b'.",
                },
            },
            "additionalProperties": False,
        },
    },
}


def _resolve_buffer(vim, buffer_id=None, buffer_path=None):
    if buffer_id is not None:
        try:
            return vim.buffers[buffer_id]
        except KeyError:
            return None
    if buffer_path is not None:
        for b in vim.buffers:
            if b.name == buffer_path or b.name.replace("\\", "/").endswith(
                buffer_path.replace("\\", "/")
            ):
                return b
        return None
    return vim.current.buffer


def execute_on_main_thread(vim, func_name, args):
    if func_name == "list_buffers":
        return _exec_list_buffers(vim)
    if func_name == "get_buffer":
        return _exec_get_buffer(vim, args)
    if func_name == "edit_buffer":
        return _exec_edit_buffer(vim, args)
    if func_name == "open_file":
        return _exec_open_file(vim, args)
    if func_name == "save_buffer":
        return _exec_save_buffer(vim, args)
    if func_name == "close_buffer":
        return _exec_close_buffer(vim, args)
    if func_name == "get_cursor":
        return _exec_get_cursor(vim)
    if func_name == "set_cursor":
        return _exec_set_cursor(vim, args)
    if func_name == "get_visual_selection":
        return _exec_get_visual_selection(vim)
    if func_name == "execute_command":
        return _exec_execute_command(vim, args)
    if func_name == "get_quickfix_list":
        return _exec_get_quickfix_list(vim)
    if func_name == "set_quickfix_list":
        return _exec_set_quickfix_list(vim, args)
    if func_name == "get_location_list":
        return _exec_get_location_list(vim)
    if func_name == "set_location_list":
        return _exec_set_location_list(vim, args)
    if func_name == "get_messages":
        return _exec_get_messages(vim)
    if func_name == "show_diff":
        return _exec_show_diff(vim, args)
    return {"error": f"Unknown tool: {func_name}"}


def _exec_list_buffers(vim):
    buffers = []
    current_number = vim.current.buffer.number
    for b in vim.buffers:
        if not int(vim.eval(f"buflisted({b.number})")):
            continue
        buffers.append({
            "number": b.number,
            "name": b.name or "[No Name]",
            "modified": bool(int(vim.eval(f"getbufvar({b.number}, '&modified')"))),
            "active": b.number == current_number,
            "line_count": len(b),
        })
    return json.dumps(buffers, indent=2)


def _exec_get_buffer(vim, args):
    buf = _resolve_buffer(vim, args.get("buffer_id"), args.get("buffer_path"))
    if buf is None:
        return {"error": "Buffer not found"}
    start = args.get("start_line")
    end = args.get("end_line")
    if start is None:
        start = 1
    if end is None:
        end = len(buf)
    start = max(1, start)
    end = min(len(buf), end)
    lines = buf[start - 1:end]
    numbered = []
    for i, line in enumerate(lines, start=start):
        numbered.append(f"{i}: {line}")
    header = f"Buffer {buf.number}: {buf.name or '[No Name]'} ({len(buf)} lines)"
    return header + "\n" + "\n".join(numbered)


def _exec_edit_buffer(vim, args):
    allow = int(vim.eval("get(g:, 'mcp_server_allow_edit', 0)"))
    if not allow:
        return {"error": "edit_buffer is disabled. Set g:mcp_server_allow_edit = 1 to enable."}
    buf = _resolve_buffer(vim, args.get("buffer_id"), args.get("buffer_path"))
    if buf is None:
        return {"error": "Buffer not found"}
    action = args.get("action")
    start = args.get("start_line")
    end = args.get("end_line")
    new_lines = args.get("new_lines")
    if action == "replace":
        if new_lines is None:
            return {"error": "new_lines is required for replace"}
        if end is None:
            return {"error": "end_line is required for replace"}
        buf[start - 1:end] = new_lines
        return f"Replaced lines {start}-{end} with {len(new_lines)} lines"
    if action == "insert":
        if new_lines is None:
            return {"error": "new_lines is required for insert"}
        buf[start:start] = new_lines
        return f"Inserted {len(new_lines)} lines after line {start}"
    if action == "delete":
        if end is None:
            return {"error": "end_line is required for delete"}
        del buf[start - 1:end]
        return f"Deleted lines {start}-{end}"
    return {"error": f"Unknown action: {action}"}


def _exec_open_file(vim, args):
    path = args.get("path", "")
    vim.command("edit " + vim.eval("fnameescape('" + path.replace("'", "''") + "')"))
    return f"Opened {path}"


def _exec_save_buffer(vim, args):
    allow = int(vim.eval("get(g:, 'mcp_server_allow_save', 0)"))
    if not allow:
        return {"error": "save_buffer is disabled. Set g:mcp_server_allow_save = 1 to enable."}
    buf = _resolve_buffer(vim, args.get("buffer_id"), args.get("buffer_path"))
    if buf is None:
        return {"error": "Buffer not found"}
    prev = vim.current.buffer.number
    vim.command(f"buffer {buf.number}")
    vim.command("write")
    if prev != buf.number:
        vim.command(f"buffer {prev}")
    return f"Saved buffer {buf.number}: {buf.name}"


def _exec_close_buffer(vim, args):
    buf = _resolve_buffer(vim, args.get("buffer_id"), args.get("buffer_path"))
    if buf is None:
        return {"error": "Buffer not found"}
    force = args.get("force", False)
    bang = "!" if force else ""
    vim.command(f"bdelete{bang} {buf.number}")
    return f"Closed buffer {buf.number}"


def _exec_get_cursor(vim):
    buf = vim.current.buffer
    row, col = vim.current.window.cursor
    return json.dumps({
        "buffer": buf.number,
        "name": buf.name or "[No Name]",
        "line": row,
        "column": col + 1,
    })


def _exec_set_cursor(vim, args):
    line = args.get("line", 1)
    col = args.get("column", 1)
    vim.current.window.cursor = (line, col - 1)
    return f"Cursor moved to line {line}, column {col}"


_VISUAL_MODES = {"v", "V", "\x16", "vs", "Vs", "\x16s"}

_VISUAL_TYPE_NAMES = {
    "v": "characterwise",
    "V": "linewise",
    "\x16": "blockwise",
}


def _exec_get_visual_selection(vim):
    mode = vim.eval("mode()")
    if mode in _VISUAL_MODES:
        start = vim.eval("getpos('v')")
        end = vim.eval("getpos('.')")
        lines = vim.eval(f"getregion(getpos('v'), getpos('.'), #{{ type: mode() }})")
        sel_type = mode.rstrip("s")
    else:
        sel_type = vim.eval("visualmode()")
        if not sel_type:
            return json.dumps({"error": "No visual selection available"})
        start = vim.eval("getpos(\"'<\")")
        end = vim.eval("getpos(\"'>\")")
        if start[1] == "0" and end[1] == "0":
            return json.dumps({"error": "No visual selection marks set"})
        lines = vim.eval(
            "getregion(getpos(\"'<\"), getpos(\"'>\"), #{ type: visualmode() })"
        )
    start_line = int(start[1])
    start_col = int(start[2])
    end_line = int(end[1])
    end_col = int(end[2])
    if start_line > end_line or (start_line == end_line and start_col > end_col):
        start_line, start_col, end_line, end_col = end_line, end_col, start_line, start_col
    return json.dumps({
        "type": _VISUAL_TYPE_NAMES.get(sel_type, sel_type),
        "text": "\n".join(lines),
        "start": {"line": start_line, "column": start_col},
        "end": {"line": end_line, "column": end_col},
    })


def _exec_execute_command(vim, args):
    allow = int(vim.eval("get(g:, 'mcp_server_allow_execute', 0)"))
    if not allow:
        return {"error": "execute_command is disabled. Set g:mcp_server_allow_execute = 1 to enable."}
    cmd = args.get("command", "")
    vim.command(cmd)
    return f"Executed: {cmd}"


def _format_list_entries(vim, raw_entries):
    entries = []
    for e in raw_entries:
        bufnr = int(e.get("bufnr", 0))
        filename = e.get("filename", "")
        if not filename and bufnr > 0:
            filename = vim.eval(f"bufname({bufnr})")
        entries.append({
            "filename": filename,
            "line": int(e.get("lnum", 0)),
            "column": int(e.get("col", 0)),
            "text": e.get("text", ""),
            "type": e.get("type", ""),
        })
    return entries


def _build_setqflist_items(entries):
    items = []
    for e in entries:
        item = {
            "filename": e["filename"],
            "lnum": e["line"],
            "text": e["text"],
        }
        if "column" in e:
            item["col"] = e["column"]
        if "type" in e:
            item["type"] = e["type"]
        items.append(item)
    return items


def _exec_get_quickfix_list(vim):
    raw = vim.eval("getqflist()")
    title = vim.eval("getqflist({'title': 1})").get("title", "")
    return json.dumps({"title": title, "entries": _format_list_entries(vim, raw)})


def _exec_set_quickfix_list(vim, args):
    entries = args.get("entries", [])
    title = args.get("title", "")
    items = _build_setqflist_items(entries)
    vim.eval(f"setqflist({json.dumps(items)}, 'r')")
    if title:
        vim.eval(f"setqflist([], 'a', {json.dumps({'title': title})})")
    if args.get("open", False):
        vim.command("copen")
    return f"Set {len(entries)} quickfix entries"


def _exec_get_location_list(vim):
    raw = vim.eval("getloclist(0)")
    title = vim.eval("getloclist(0, {'title': 1})").get("title", "")
    return json.dumps({"title": title, "entries": _format_list_entries(vim, raw)})


def _exec_set_location_list(vim, args):
    entries = args.get("entries", [])
    title = args.get("title", "")
    items = _build_setqflist_items(entries)
    vim.eval(f"setloclist(0, {json.dumps(items)}, 'r')")
    if title:
        vim.eval(f"setloclist(0, [], 'a', {json.dumps({'title': title})})")
    if args.get("open", False):
        vim.command("lopen")
    return f"Set {len(entries)} location list entries"


def _exec_get_messages(vim):
    return vim.eval("execute('messages')")


def _enhance_diffopt(vim):
    current = vim.eval("&diffopt")

    additions = []

    if "linematch" not in current:
        if vim.eval("has('patch-9.1.1009')") == "1":
            additions.append("linematch:60")

    if "algorithm:" not in current:
        if vim.eval("has('patch-8.1.0360')") == "1":
            additions.append("algorithm:histogram")

    for item in additions:
        vim.command("set diffopt+=" + item)


def _setup_scratch_buffer(vim, content, label):
    vim.command("enew")
    vim.command("setlocal buftype=nofile bufhidden=wipe noswapfile")
    escaped_label = vim.eval("fnameescape('" + label.replace("'", "''") + "')")
    vim.command("file " + escaped_label)
    lines = content.split("\n")
    vim.current.buffer[:] = lines


def _exec_show_diff(vim, args):
    file_a = args.get("file_a")
    file_b = args.get("file_b")
    content_a = args.get("content_a")
    content_b = args.get("content_b")

    has_files = file_a is not None and file_b is not None
    has_content = content_a is not None and content_b is not None

    if not has_files and not has_content:
        return {
            "error": (
                "Provide either file_a and file_b (file mode) "
                "or content_a and content_b (content mode)."
            )
        }

    vim.command("tabnew")
    _enhance_diffopt(vim)

    if has_files:
        escaped_a = vim.eval("fnameescape('" + file_a.replace("'", "''") + "')")
        escaped_b = vim.eval("fnameescape('" + file_b.replace("'", "''") + "')")
        vim.command("edit " + escaped_a)
        vim.command("setlocal nomodifiable")
        vim.command("diffthis")
        vim.command("vert diffsplit " + escaped_b)
        vim.command("setlocal nomodifiable")
        return f"Showing diff in new tab: {file_a} vs {file_b}"

    label_a = args.get("label_a", "a")
    label_b = args.get("label_b", "b")

    _setup_scratch_buffer(vim, content_a, label_a)
    vim.command("setlocal nomodifiable")
    vim.command("diffthis")

    vim.command("vnew")
    _setup_scratch_buffer(vim, content_b, label_b)
    vim.command("setlocal nomodifiable")
    vim.command("diffthis")

    return f"Showing diff in new tab: {label_a} vs {label_b}"


def call_tool(name, arguments):
    if name not in TOOL_DEFINITIONS:
        return {"error": f"Unknown tool: {name}"}
    request_id = str(uuid.uuid4())
    result = mcp_vim_bridge.submit_request(request_id, name, arguments)
    return result
