let s:timer_id = -1
let s:plugin_root = expand('<sfile>:p:h:h')
let s:python_dir = s:plugin_root . '/python3'
let s:python_loaded = 0

function! s:ensure_python() abort
  if s:python_loaded
    return 1
  endif
  if !has('python3')
    echoerr 'vim-mcp-server requires Vim compiled with +python3'
    return 0
  endif
  execute 'py3 import sys; sys.path.insert(0, r"' . s:python_dir . '")'
  py3 import mcp_vim_bridge
  py3 import mcp_tools
  py3 import mcp_server
  let s:python_loaded = 1
  return 1
endfunction

function! mcp_server#start(...) abort
  if !s:ensure_python()
    return
  endif
  let l:port = get(a:, 1, get(g:, 'mcp_server_port', 8765))
  execute 'py3 _mcp_result = mcp_server.start(' . l:port . ')'
  let l:msg = py3eval('_mcp_result')
  echo l:msg
  if s:timer_id == -1
    let s:timer_id = timer_start(50, function('s:poll_requests'), {'repeat': -1})
  endif
endfunction

function! mcp_server#stop() abort
  if !s:python_loaded
    echo 'MCP server is not running'
    return
  endif
  if s:timer_id != -1
    call timer_stop(s:timer_id)
    let s:timer_id = -1
  endif
  py3 _mcp_result = mcp_server.stop()
  echo py3eval('_mcp_result')
endfunction

function! mcp_server#status() abort
  if !s:python_loaded
    echo 'MCP server: not loaded'
    return
  endif
  let l:running = py3eval('mcp_server.is_running()')
  if l:running
    let l:port = get(g:, 'mcp_server_port', 8765)
    echo 'MCP server: running on http://127.0.0.1:' . l:port . '/mcp'
  else
    echo 'MCP server: stopped'
  endif
endfunction

function! s:poll_requests(timer) abort
  py3 << EOF
import vim as _vim
import mcp_vim_bridge as _bridge
import mcp_tools as _tools

for _req_id, _func_name, _args in _bridge.drain_requests():
    try:
        _result = _tools.execute_on_main_thread(_vim, _func_name, _args)
    except Exception as _e:
        _result = {"error": str(_e)}
    _bridge.post_result(_req_id, _result)
EOF
endfunction
