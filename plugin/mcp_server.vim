if exists('g:loaded_mcp_server')
  finish
endif
let g:loaded_mcp_server = 1

command! -nargs=? McpServerStart call mcp_server#start(<f-args>)
command! -nargs=0 McpServerStop  call mcp_server#stop()
command! -nargs=0 McpServerStatus call mcp_server#status()

augroup vim_mcp_server
  autocmd!
  autocmd VimLeavePre * call mcp_server#stop()
augroup END

if get(g:, 'mcp_server_autostart', 0)
  autocmd VimEnter * call mcp_server#start()
endif
