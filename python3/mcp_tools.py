import json
import os
import posixpath
import re
import subprocess
import uuid

import mcp_vim_bridge


_MAX_GIT_OUTPUT_BYTES = 5 * 1024 * 1024


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
                    "description": "Absolute file path to open.",
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
            "Get the current visual selection in Vim. If Vim is currently in "
            "visual mode, returns the selected text, the selection type (v for "
            "characterwise, V for linewise, ctrl-v for blockwise), and the "
            "start/end positions. If there is no active visual selection, "
            "returns {\"active\": false}."
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
                                "description": "Absolute file path.",
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
                                "description": "Absolute file path.",
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
            "Open a side-by-side diff view in Vim. "
            "Supports two modes: content mode and file mode. "
            "STRONGLY prefer content mode (content_a/content_b) over "
            "file mode. Content mode avoids extra disk reads and works "
            "with text you already have (e.g. git diff output, code "
            "you've just read, or generated content). Only use file "
            "mode (file_a/file_b) when you need to compare two files "
            "whose contents you have NOT already read. "
            "In content mode, use label_a and label_b to give the "
            "buffers meaningful names (e.g. the file paths or "
            "descriptions like 'before'/'after'), and filetype_a / "
            "filetype_b to set the Vim filetype for syntax highlighting "
            "(e.g. 'python', 'diff', 'markdown'). "
            "Always opens in a new tab. "
            "Call multiple times for multiple diffs."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "content_a": {
                    "type": "string",
                    "description": "Text content for the left side. Preferred over file_a.",
                },
                "content_b": {
                    "type": "string",
                    "description": "Text content for the right side. Preferred over file_b.",
                },
                "label_a": {
                    "type": "string",
                    "description": "Display name for the left buffer (content mode only). Defaults to 'a'.",
                },
                "label_b": {
                    "type": "string",
                    "description": "Display name for the right buffer (content mode only). Defaults to 'b'.",
                },
                "filetype_a": {
                    "type": "string",
                    "description": "Vim filetype for the left buffer (content mode only). Used for syntax highlighting (e.g. 'python', 'diff'). If omitted, no filetype is set.",
                },
                "filetype_b": {
                    "type": "string",
                    "description": "Vim filetype for the right buffer (content mode only). Used for syntax highlighting (e.g. 'python', 'diff'). If omitted, no filetype is set.",
                },
                "file_a": {
                    "type": "string",
                    "description": "Absolute path to the first file (left side). Only use when content is not already available.",
                },
                "file_b": {
                    "type": "string",
                    "description": "Absolute path to the second file (right side). Only use when content is not already available.",
                },
            },
            "additionalProperties": False,
        },
    },
    "show_git_diff": {
        "description": (
            "Open a side-by-side diff view in Vim for git-tracked changes. "
            "Lets git compute the diff inputs directly inside Vim, avoiding "
            "the need to pre-fetch file contents. STRONGLY prefer this over "
            "show_diff whenever comparing git refs or staged/working-tree "
            "changes. Auto-discovers the repo root from path; filetype is "
            "detected by Vim from each side's filename. "
            "Rename detection is enabled, so a renamed file is followed "
            "across the two sides. If a side does not contain the file "
            "(e.g. an added or deleted file), that buffer is shown empty. "
            "Always opens in a new tab. Call multiple times for multiple "
            "diffs."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Absolute path to the file inside a git repository. May refer to either the pre- or post-rename name; rename detection resolves the other side.",
                },
                "ref_a": {
                    "type": "string",
                    "description": "Left-side revision. Empty string means working tree on disk. Defaults to 'HEAD'.",
                },
                "ref_b": {
                    "type": "string",
                    "description": "Right-side revision. Empty string means working tree on disk. Defaults to '' (working tree).",
                },
                "staged": {
                    "type": "boolean",
                    "description": "Convenience for diffing HEAD against the index. Mutually exclusive with explicit ref_a or ref_b. Defaults to false.",
                },
            },
            "required": ["path"],
            "additionalProperties": False,
        },
    },
}


def _require_absolute_path(path, param_name):
    if not os.path.isabs(path) and not path.startswith("/"):
        return {"error": f"{param_name} must be an absolute path, got relative path: {path}"}

    return None


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
    if func_name == "show_git_diff":
        return _exec_show_git_diff(vim, args)
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

    error = _require_absolute_path(path, "path")
    if error:
        return error

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
        return json.dumps({"active": False})
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


def _validate_list_entries(entries):
    for i, e in enumerate(entries):
        error = _require_absolute_path(e["filename"], f"entries[{i}].filename")
        if error:
            return error

    return None


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

    error = _validate_list_entries(entries)
    if error:
        return error

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

    error = _validate_list_entries(entries)
    if error:
        return error

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


_DIFFOPT_PATCH_CACHE = {}


def _reset_diffopt_patch_cache():
    _DIFFOPT_PATCH_CACHE.clear()


def _has_patch(vim, patch_id):
    if patch_id not in _DIFFOPT_PATCH_CACHE:
        _DIFFOPT_PATCH_CACHE[patch_id] = vim.eval("has('" + patch_id + "')") == "1"

    return _DIFFOPT_PATCH_CACHE[patch_id]


def _enhance_diffopt(vim):
    current = vim.eval("&diffopt")

    additions = []

    if "linematch" not in current:
        if _has_patch(vim, "patch-9.1.1009"):
            additions.append("linematch:60")

    if "algorithm:" not in current:
        if _has_patch(vim, "patch-8.1.0360"):
            additions.append("algorithm:histogram")

    for item in additions:
        vim.command("set diffopt+=" + item)


_FILETYPE_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+$")


def _is_valid_filetype(ft):
    return isinstance(ft, str) and bool(_FILETYPE_PATTERN.match(ft))


def _setup_scratch_buffer(vim, content, label, filetype=None):
    vim.command("enew")
    vim.command("setlocal buftype=nofile bufhidden=wipe noswapfile")
    escaped_label = vim.eval("fnameescape('" + label.replace("'", "''") + "')")
    vim.command("file " + escaped_label)
    if filetype is not None and _is_valid_filetype(filetype):
        vim.command("setlocal filetype=" + filetype)
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

    if has_files:
        for name, value in [("file_a", file_a), ("file_b", file_b)]:
            error = _require_absolute_path(value, name)
            if error:
                return error

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
    filetype_a = args.get("filetype_a")
    filetype_b = args.get("filetype_b")

    _setup_scratch_buffer(vim, content_a, label_a, filetype_a)
    vim.command("setlocal nomodifiable")
    vim.command("diffthis")

    vim.command("vnew")
    _setup_scratch_buffer(vim, content_b, label_b, filetype_b)
    vim.command("setlocal nomodifiable")
    vim.command("diffthis")

    return f"Showing diff in new tab: {label_a} vs {label_b}"


def _run_git(repo_root, args):
    return subprocess.run(
        ["git"] + list(args),
        cwd=repo_root,
        capture_output=True,
        check=False,
    )


def _git_repo_root(path):
    start_dir = path if os.path.isdir(path) else os.path.dirname(path)
    if not start_dir:
        return None
    try:
        result = subprocess.run(
            ["git", "-C", start_dir, "rev-parse", "--show-toplevel"],
            capture_output=True,
            check=False,
        )
    except FileNotFoundError:
        return None
    if result.returncode != 0:
        return None
    root = result.stdout.decode("utf-8", errors="replace").strip()
    if not root:
        return None
    return root


_FILENAME_ESCAPE_CHARS = set(" \t\n\r%#|\\\"'<>$&*?[]{}();`!")


def _vim_escape_filename(label):
    escaped = []
    for ch in label:
        if ch in _FILENAME_ESCAPE_CHARS or ord(ch) < 0x20:
            escaped.append("\\" + ch)
        else:
            escaped.append(ch)
    return "".join(escaped)


def _is_ref_safe(ref):
    return isinstance(ref, str) and not ref.startswith("-")


def _read_worktree(repo_root, rel_path):
    full = os.path.join(repo_root, rel_path)
    if not os.path.isfile(full):
        return "", True
    try:
        size = os.path.getsize(full)
    except OSError:
        return "", True
    if size > _MAX_GIT_OUTPUT_BYTES:
        return None, False
    try:
        with open(full, "rb") as f:
            data = f.read()
    except OSError:
        return "", True
    return data.decode("utf-8", errors="replace"), False


def _git_show(repo_root, ref, rel_path):
    if ref == "":
        return _read_worktree(repo_root, rel_path)

    if ref == ":0:":
        spec = ":" + rel_path
    else:
        spec = ref + ":" + rel_path

    result = _run_git(repo_root, ["show", spec])
    if result.returncode != 0:
        stderr = result.stderr.decode("utf-8", errors="replace")
        if (
            "does not exist" in stderr
            or "exists on disk, but not in" in stderr
            or "Path '" in stderr
            or "bad object" in stderr
        ):
            return "", True
        return None, False

    if len(result.stdout) > _MAX_GIT_OUTPUT_BYTES:
        return None, False

    return result.stdout.decode("utf-8", errors="replace"), False


def _resolve_path_at_ref(repo_root, ref, rel_path):
    if ref == "":
        full = os.path.join(repo_root, rel_path)
        return rel_path if os.path.isfile(full) else None

    if ref == ":0:":
        spec = ":" + rel_path
    else:
        spec = ref + ":" + rel_path

    exists = _run_git(repo_root, ["cat-file", "-e", spec])
    if exists.returncode == 0:
        return rel_path

    if ref == ":0:":
        diff_args = ["diff", "-M", "--name-status", "--cached", "--", rel_path]
    else:
        diff_args = ["diff", "-M", "--name-status", ref, "--", rel_path]

    result = _run_git(repo_root, diff_args)
    if result.returncode != 0:
        return None

    text = result.stdout.decode("utf-8", errors="replace")
    for line in text.splitlines():
        parts = line.split("\t")
        if not parts:
            continue
        status = parts[0]
        if status.startswith("R") and len(parts) >= 3:
            old_name, new_name = parts[1], parts[2]
            if new_name == rel_path:
                return old_name
            if old_name == rel_path:
                return new_name

    return None


def _ref_label(ref):
    if ref == "":
        return "working tree"
    if ref == ":0:":
        return "index"
    return ref


def _build_side_label(rel_path_input, resolved_path, ref):
    name = resolved_path if resolved_path is not None else rel_path_input
    missing_marker = "" if resolved_path is not None else " (missing)"
    return f"{name}@{_ref_label(ref)}{missing_marker}"


def _setup_git_diff_buffer(vim, lines, label, bare_name):
    escaped_label = _vim_escape_filename(label)
    escaped_bare = _vim_escape_filename(bare_name)

    vim.command(
        "enew | "
        "setlocal buftype=nofile bufhidden=wipe noswapfile | "
        "file " + escaped_bare + " | "
        "filetype detect | "
        "file " + escaped_label
    )
    vim.current.buffer[:] = lines
    vim.command("setlocal nomodifiable | diffthis")


def _exec_show_git_diff(vim, args):
    path = args.get("path")
    if not isinstance(path, str) or not path:
        return {"error": "path is required"}

    error = _require_absolute_path(path, "path")
    if error:
        return error

    staged = bool(args.get("staged", False))
    ref_a_arg = args.get("ref_a")
    ref_b_arg = args.get("ref_b")

    if staged and (ref_a_arg is not None or ref_b_arg is not None):
        return {"error": "staged cannot be combined with explicit ref_a or ref_b"}

    if staged:
        ref_a = "HEAD"
        ref_b = ":0:"
    else:
        ref_a = ref_a_arg if ref_a_arg is not None else "HEAD"
        ref_b = ref_b_arg if ref_b_arg is not None else ""

    if not _is_ref_safe(ref_a):
        return {"error": f"ref_a is not a valid revision: {ref_a}"}

    if not _is_ref_safe(ref_b):
        return {"error": f"ref_b is not a valid revision: {ref_b}"}

    repo_root = _git_repo_root(path)
    if repo_root is None:
        return {"error": f"{path} is not inside a git repository"}

    rel_native = os.path.relpath(path, repo_root)
    rel_path_input = rel_native.replace("\\", "/")
    if rel_path_input.startswith("../"):
        return {"error": f"{path} is not inside repo {repo_root}"}

    path_a = _resolve_path_at_ref(repo_root, ref_a, rel_path_input)
    path_b = _resolve_path_at_ref(repo_root, ref_b, rel_path_input)

    if path_a is None:
        text_a, _ = "", True
    else:
        text_a, missing_a = _git_show(repo_root, ref_a, path_a)
        if text_a is None:
            return {"error": f"git output for ref_a too large or git failed for {path_a}@{_ref_label(ref_a)}"}
        if missing_a:
            path_a = None

    if path_b is None:
        text_b, _ = "", True
    else:
        text_b, missing_b = _git_show(repo_root, ref_b, path_b)
        if text_b is None:
            return {"error": f"git output for ref_b too large or git failed for {path_b}@{_ref_label(ref_b)}"}
        if missing_b:
            path_b = None

    label_a = _build_side_label(rel_path_input, path_a, ref_a)
    label_b = _build_side_label(rel_path_input, path_b, ref_b)

    bare_a = posixpath.basename(path_a if path_a is not None else rel_path_input)
    bare_b = posixpath.basename(path_b if path_b is not None else rel_path_input)

    prev_lazyredraw = vim.eval("&lazyredraw")
    vim.command("set lazyredraw")

    try:
        vim.command("tabnew")
        _enhance_diffopt(vim)

        lines_a = text_a.split("\n") if text_a else [""]
        if text_a.endswith("\n") and len(lines_a) > 1:
            lines_a = lines_a[:-1]
        _setup_git_diff_buffer(vim, lines_a, label_a, bare_a)

        vim.command("vnew")

        lines_b = text_b.split("\n") if text_b else [""]
        if text_b.endswith("\n") and len(lines_b) > 1:
            lines_b = lines_b[:-1]
        _setup_git_diff_buffer(vim, lines_b, label_b, bare_b)
    finally:
        if prev_lazyredraw == "0":
            vim.command("set nolazyredraw")
        else:
            vim.command("set lazyredraw")

    return f"Showing git diff in new tab: {label_a} vs {label_b}"


def call_tool(name, arguments):
    if name not in TOOL_DEFINITIONS:
        return {"error": f"Unknown tool: {name}"}
    request_id = str(uuid.uuid4())
    result = mcp_vim_bridge.submit_request(request_id, name, arguments)
    return result
