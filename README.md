# vim-mcp-server

An MCP (Model Context Protocol) server embedded in Vim. It exposes tools over
HTTP that let MCP-compatible clients — such as AI coding agents — read and
modify buffers, move the cursor, retrieve visual selections, manage quickfix
and location lists, read message history, and run Ex commands.

## Requirements

- Vim compiled with `+python3`

## Installation

Use your preferred plugin manager.

### vim-plug

```vim
Plug 'breggles/vim-mcp-server'
```

### Vundle

```vim
Plugin 'breggles/vim-mcp-server'
```

### Manual

Clone the repository into your Vim packages directory:

```sh
git clone https://github.com/breggles/vim-mcp-server.git \
    ~/.vim/pack/plugins/start/vim-mcp-server
```

## Usage

### Start the server

In Vim, run:

```vim
:McpServerStart
```

Auto-start the server on Vim launch by adding this to your `vimrc`:

```vim
let g:mcp_server_autostart = 1
```

### MCP Client Configuration

Point your MCP client at `http://127.0.0.1:8765/mcp` (or whichever port you
chose).

For example, for opencode add the server to your `opencode.jsonc`:

```jsonc
"mcp": {
  "vim": {
    "type": "remote",
    "url": "http://localhost:8765/mcp",
    "enabled": true
  }
}
```

## Commands

| Command                | Description                          |
| ---------------------- | ------------------------------------ |
| `:McpServerStart [port]` | Start the server (default port 8765) |
| `:McpServerStop`         | Stop the server                      |
| `:McpServerStatus`       | Print server status and URL          |

## Options

| Variable                       | Default | Description                                    |
| ------------------------------ | ------- | ---------------------------------------------- |
| `g:mcp_server_port`            | `8765`  | Port the server listens on                     |
| `g:mcp_server_autostart`       | `0`     | Start the server automatically on `VimEnter`   |
| `g:mcp_server_allow_execute`   | `0`     | Enable the `execute_command` tool               |
| `g:mcp_server_allow_save`     | `0`     | Enable the `save_buffer` tool                   |

## Tools

The server exposes the following tools to MCP clients:

| Tool                   | Description                                           |
| ---------------------- | ----------------------------------------------------- |
| `list_buffers`         | List all open buffers                                 |
| `get_buffer`           | Read buffer contents (optionally a line range)        |
| `edit_buffer`          | Replace, insert, or delete lines in a buffer          |
| `open_file`            | Open a file via `:edit`                               |
| `save_buffer`          | Save a buffer via `:write` (opt-in, see above)        |
| `close_buffer`         | Close a buffer via `:bdelete`                         |
| `get_cursor`           | Get current cursor position                           |
| `set_cursor`           | Move cursor to a line and column                      |
| `get_visual_selection` | Get the current or last visual selection               |
| `execute_command`      | Run an arbitrary Ex command (opt-in, see above)       |
| `get_quickfix_list`    | Get the current quickfix list entries                 |
| `set_quickfix_list`    | Set the quickfix list                                 |
| `get_location_list`    | Get the location list for the current window          |
| `set_location_list`    | Set the location list for the current window          |
| `get_messages`         | Get Vim's message history (`:messages` output)        |

When a tool accepts a buffer argument it can be specified by number
(`buffer_id`) or by file path (`buffer_path`). When both are omitted, the
current buffer is used.

## OpenCode Plan Mode

By default, OpenCode's plan mode disables all MCP tools. To allow read-only
vim tools in plan mode, add the following to your `opencode.jsonc`:

```jsonc
{
  "agent": {
    "plan": {
      "tools": {
        "vim_*": false,
        "vim_list_buffers": true,
        "vim_get_buffer": true,
        "vim_get_cursor": true,
        "vim_get_visual_selection": true,
        "vim_open_file": true,
        "vim_set_cursor": true,
        "vim_get_quickfix_list": true,
        "vim_set_quickfix_list": true,
        "vim_get_location_list": true,
        "vim_set_location_list": true,
        "vim_get_messages": true
      }
    }
  }
}
```

This disables all `vim_*` tools first, then re-enables specific ones. Adjust
the list to suit your workflow.

## Development

To work on the plugin without installing it, clone the repository and add it
to Vim's runtime path:

```vim
set rtp+=~/path/to/vim-mcp-server
```

Add this to your `vimrc` or run it manually. Changes take effect the next time
Vim is started.

Generate the help tags with:

```vim
:helptags ~/path/to/vim-mcp-server/doc
```

## License

MIT
