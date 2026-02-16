import json
import sys
from unittest.mock import MagicMock, patch, PropertyMock

import mcp_tools


class TestToolDefinitions:
    def test_all_tools_have_description(self):
        for name, tool in mcp_tools.TOOL_DEFINITIONS.items():
            assert "description" in tool, f"{name} missing description"
            assert isinstance(tool["description"], str)
            assert len(tool["description"]) > 0

    def test_all_tools_have_input_schema(self):
        for name, tool in mcp_tools.TOOL_DEFINITIONS.items():
            schema = tool["inputSchema"]
            assert schema["type"] == "object", f"{name} schema type is not object"
            assert "properties" in schema, f"{name} missing properties"

    def test_required_fields_exist_in_properties(self):
        for name, tool in mcp_tools.TOOL_DEFINITIONS.items():
            schema = tool["inputSchema"]
            required = schema.get("required", [])
            props = schema["properties"]
            for field in required:
                assert field in props, (
                    f"{name}: required field '{field}' not in properties"
                )

    def test_expected_tool_count(self):
        assert len(mcp_tools.TOOL_DEFINITIONS) == 15


class TestBuildSetqflistItems:
    def test_basic_entry(self):
        entries = [{"filename": "foo.py", "line": 10, "text": "error here"}]
        items = mcp_tools._build_setqflist_items(entries)
        assert items == [{"filename": "foo.py", "lnum": 10, "text": "error here"}]

    def test_with_optional_fields(self):
        entries = [{
            "filename": "bar.py",
            "line": 5,
            "text": "warning",
            "column": 3,
            "type": "W",
        }]
        items = mcp_tools._build_setqflist_items(entries)
        assert items == [{
            "filename": "bar.py",
            "lnum": 5,
            "text": "warning",
            "col": 3,
            "type": "W",
        }]

    def test_multiple_entries(self):
        entries = [
            {"filename": "a.py", "line": 1, "text": "one"},
            {"filename": "b.py", "line": 2, "text": "two"},
        ]
        items = mcp_tools._build_setqflist_items(entries)
        assert len(items) == 2
        assert items[0]["filename"] == "a.py"
        assert items[1]["filename"] == "b.py"

    def test_empty_entries(self):
        assert mcp_tools._build_setqflist_items([]) == []


def _make_buffer(number, name, lines):
    buf = MagicMock()
    buf.number = number
    buf.name = name
    buf.__len__ = lambda self: len(lines)
    buf.__getitem__ = lambda self, key: lines[key]
    return buf


def _make_vim(buffers, current_buf_number=None):
    vim = MagicMock()
    buf_dict = {b.number: b for b in buffers}

    if current_buf_number is None:
        current_buf_number = buffers[0].number if buffers else 1

    vim.current.buffer = buf_dict[current_buf_number]
    vim.current.buffer.number = current_buf_number

    vim.buffers = MagicMock()
    vim.buffers.__iter__ = lambda self: iter(buffers)
    vim.buffers.__getitem__ = lambda self, key: buf_dict[key]

    return vim


class TestResolveBuffer:
    def test_by_buffer_id(self):
        buf = _make_buffer(3, "/tmp/test.py", ["line1"])
        vim = _make_vim([buf])
        result = mcp_tools._resolve_buffer(vim, buffer_id=3)
        assert result is buf

    def test_by_buffer_id_not_found(self):
        buf = _make_buffer(1, "/tmp/test.py", ["line1"])
        vim = _make_vim([buf])
        vim.buffers.__getitem__ = MagicMock(side_effect=KeyError(99))
        result = mcp_tools._resolve_buffer(vim, buffer_id=99)
        assert result is None

    def test_by_buffer_path_exact_match(self):
        buf = _make_buffer(1, "/tmp/test.py", ["line1"])
        vim = _make_vim([buf])
        result = mcp_tools._resolve_buffer(vim, buffer_path="/tmp/test.py")
        assert result is buf

    def test_by_buffer_path_endswith_match(self):
        buf = _make_buffer(1, "/home/user/project/src/main.py", ["line1"])
        vim = _make_vim([buf])
        result = mcp_tools._resolve_buffer(vim, buffer_path="src/main.py")
        assert result is buf

    def test_by_buffer_path_backslash_normalization(self):
        buf = _make_buffer(1, "C:\\Users\\test\\file.py", ["line1"])
        vim = _make_vim([buf])
        result = mcp_tools._resolve_buffer(vim, buffer_path="test/file.py")
        assert result is buf

    def test_by_buffer_path_not_found(self):
        buf = _make_buffer(1, "/tmp/test.py", [])
        vim = _make_vim([buf])
        result = mcp_tools._resolve_buffer(vim, buffer_path="nonexistent.py")
        assert result is None

    def test_default_returns_current_buffer(self):
        buf = _make_buffer(1, "/tmp/test.py", [])
        vim = _make_vim([buf])
        result = mcp_tools._resolve_buffer(vim)
        assert result is vim.current.buffer


class TestCallToolUnknown:
    def test_unknown_tool_returns_error(self):
        result = mcp_tools.call_tool("nonexistent_tool", {})
        assert result == {"error": "Unknown tool: nonexistent_tool"}


class TestExecuteOnMainThread:
    def test_unknown_func_name(self):
        vim = MagicMock()
        result = mcp_tools.execute_on_main_thread(vim, "bogus_tool", {})
        assert result == {"error": "Unknown tool: bogus_tool"}

    def test_dispatches_get_cursor(self):
        vim = MagicMock()
        vim.current.buffer.number = 1
        vim.current.buffer.name = "test.py"
        vim.current.window.cursor = (5, 2)
        result = mcp_tools.execute_on_main_thread(vim, "get_cursor", {})
        data = json.loads(result)
        assert data["line"] == 5
        assert data["column"] == 3
        assert data["buffer"] == 1


class TestExecListBuffers:
    def test_lists_buffers(self):
        buf1 = _make_buffer(1, "/tmp/a.py", ["line1", "line2"])
        buf2 = _make_buffer(2, "/tmp/b.py", ["line1"])
        vim = _make_vim([buf1, buf2], current_buf_number=1)
        vim.eval = lambda expr: {
            "buflisted(1)": "1",
            "buflisted(2)": "1",
            "getbufvar(1, '&modified')": "0",
            "getbufvar(2, '&modified')": "1",
        }.get(expr, "0")
        result = mcp_tools._exec_list_buffers(vim)
        data = json.loads(result)
        assert len(data) == 2
        assert data[0]["number"] == 1
        assert data[0]["active"] is True
        assert data[0]["modified"] is False
        assert data[0]["line_count"] == 2
        assert data[1]["number"] == 2
        assert data[1]["active"] is False
        assert data[1]["modified"] is True

    def test_skips_unlisted_buffers(self):
        buf1 = _make_buffer(1, "/tmp/a.py", [])
        buf2 = _make_buffer(2, "/tmp/b.py", [])
        vim = _make_vim([buf1, buf2], current_buf_number=1)
        vim.eval = lambda expr: {
            "buflisted(1)": "1",
            "buflisted(2)": "0",
            "getbufvar(1, '&modified')": "0",
        }.get(expr, "0")
        result = mcp_tools._exec_list_buffers(vim)
        data = json.loads(result)
        assert len(data) == 1
        assert data[0]["number"] == 1


class TestExecGetBuffer:
    def test_full_buffer(self):
        buf = _make_buffer(1, "/tmp/test.py", ["aaa", "bbb", "ccc"])
        vim = _make_vim([buf])
        result = mcp_tools._exec_get_buffer(vim, {})
        assert "1: aaa" in result
        assert "2: bbb" in result
        assert "3: ccc" in result
        assert "3 lines" in result

    def test_line_range(self):
        buf = _make_buffer(1, "/tmp/test.py", ["aaa", "bbb", "ccc", "ddd"])
        vim = _make_vim([buf])
        result = mcp_tools._exec_get_buffer(vim, {"start_line": 2, "end_line": 3})
        assert "2: bbb" in result
        assert "3: ccc" in result
        assert "1: aaa" not in result
        assert "4: ddd" not in result

    def test_buffer_not_found(self):
        buf = _make_buffer(1, "/tmp/test.py", [])
        vim = _make_vim([buf])
        vim.buffers.__getitem__ = MagicMock(side_effect=KeyError(99))
        result = mcp_tools._exec_get_buffer(vim, {"buffer_id": 99})
        assert result == {"error": "Buffer not found"}


class TestExecGetCursor:
    def test_returns_cursor_position(self):
        buf = _make_buffer(1, "/tmp/test.py", [])
        vim = _make_vim([buf])
        vim.current.window.cursor = (10, 4)
        result = mcp_tools._exec_get_cursor(vim)
        data = json.loads(result)
        assert data["line"] == 10
        assert data["column"] == 5
        assert data["buffer"] == 1
        assert data["name"] == "/tmp/test.py"


class TestExecSetCursor:
    def test_sets_cursor(self):
        vim = MagicMock()
        result = mcp_tools._exec_set_cursor(vim, {"line": 5, "column": 3})
        assert vim.current.window.cursor == (5, 2)
        assert "line 5" in result
        assert "column 3" in result

    def test_default_column(self):
        vim = MagicMock()
        result = mcp_tools._exec_set_cursor(vim, {"line": 1})
        assert vim.current.window.cursor == (1, 0)


class TestExecEditBuffer:
    def test_replace(self):
        lines = ["aaa", "bbb", "ccc"]
        buf = _make_buffer(1, "/tmp/test.py", lines)
        vim = _make_vim([buf])
        result = mcp_tools._exec_edit_buffer(vim, {
            "action": "replace",
            "start_line": 1,
            "end_line": 2,
            "new_lines": ["xxx", "yyy", "zzz"],
        })
        assert "Replaced" in result

    def test_replace_missing_new_lines(self):
        buf = _make_buffer(1, "/tmp/test.py", ["aaa"])
        vim = _make_vim([buf])
        result = mcp_tools._exec_edit_buffer(vim, {
            "action": "replace",
            "start_line": 1,
            "end_line": 1,
        })
        assert result == {"error": "new_lines is required for replace"}

    def test_replace_missing_end_line(self):
        buf = _make_buffer(1, "/tmp/test.py", ["aaa"])
        vim = _make_vim([buf])
        result = mcp_tools._exec_edit_buffer(vim, {
            "action": "replace",
            "start_line": 1,
            "new_lines": ["xxx"],
        })
        assert result == {"error": "end_line is required for replace"}

    def test_insert(self):
        lines = ["aaa", "bbb"]
        buf = _make_buffer(1, "/tmp/test.py", lines)
        vim = _make_vim([buf])
        result = mcp_tools._exec_edit_buffer(vim, {
            "action": "insert",
            "start_line": 1,
            "new_lines": ["xxx"],
        })
        assert "Inserted" in result

    def test_delete(self):
        lines = ["aaa", "bbb", "ccc"]
        buf = _make_buffer(1, "/tmp/test.py", lines)
        vim = _make_vim([buf])
        result = mcp_tools._exec_edit_buffer(vim, {
            "action": "delete",
            "start_line": 1,
            "end_line": 2,
        })
        assert "Deleted" in result

    def test_delete_missing_end_line(self):
        buf = _make_buffer(1, "/tmp/test.py", ["aaa"])
        vim = _make_vim([buf])
        result = mcp_tools._exec_edit_buffer(vim, {
            "action": "delete",
            "start_line": 1,
        })
        assert result == {"error": "end_line is required for delete"}

    def test_unknown_action(self):
        buf = _make_buffer(1, "/tmp/test.py", ["aaa"])
        vim = _make_vim([buf])
        result = mcp_tools._exec_edit_buffer(vim, {
            "action": "frobnicate",
            "start_line": 1,
        })
        assert result == {"error": "Unknown action: frobnicate"}

    def test_buffer_not_found(self):
        buf = _make_buffer(1, "/tmp/test.py", [])
        vim = _make_vim([buf])
        vim.buffers.__getitem__ = MagicMock(side_effect=KeyError(99))
        result = mcp_tools._exec_edit_buffer(vim, {
            "buffer_id": 99,
            "action": "delete",
            "start_line": 1,
            "end_line": 1,
        })
        assert result == {"error": "Buffer not found"}


class TestExecExecuteCommand:
    def test_disabled_by_default(self):
        vim = MagicMock()
        vim.eval = lambda expr: "0"
        result = mcp_tools._exec_execute_command(vim, {"command": "echo 'hi'"})
        assert result["error"].startswith("execute_command is disabled")

    def test_enabled(self):
        vim = MagicMock()
        vim.eval = lambda expr: "1"
        result = mcp_tools._exec_execute_command(vim, {"command": "%s/foo/bar/g"})
        assert "Executed" in result
        vim.command.assert_called_once_with("%s/foo/bar/g")
