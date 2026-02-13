# vim-mcp-server

An MCP (Model Context Protocol) server embedded in Vim. It exposes tools over
HTTP that let MCP-compatible clients — such as AI coding agents — read and
modify buffers, move the cursor, retrieve visual selections, and run Ex
commands.

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

Start the server:

```vim
:McpServerStart
```

Start on a specific port:

```vim
:McpServerStart 9000
```

Check status:

```vim
:McpServerStatus
```

Stop the server:

```vim
:McpServerStop
```

Point your MCP client at `http://127.0.0.1:8765/mcp` (or whichever port you
chose).

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

## Tools

The server exposes the following tools to MCP clients:

| Tool                   | Description                                           |
| ---------------------- | ----------------------------------------------------- |
| `list_buffers`         | List all open buffers                                 |
| `get_buffer`           | Read buffer contents (optionally a line range)        |
| `edit_buffer`          | Replace, insert, or delete lines in a buffer          |
| `open_file`            | Open a file via `:edit`                               |
| `save_buffer`          | Save a buffer via `:write`                            |
| `close_buffer`         | Close a buffer via `:bdelete`                         |
| `get_cursor`           | Get current cursor position                           |
| `set_cursor`           | Move cursor to a line and column                      |
| `get_visual_selection` | Get the current or last visual selection               |
| `execute_command`      | Run an arbitrary Ex command (opt-in, see above)       |

When a tool accepts a buffer argument it can be a buffer number or a file
path. When omitted, the current buffer is used.

## License

MIT
