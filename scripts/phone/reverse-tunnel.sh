#!/bin/bash
# 手机端反向隧道模板 —— 只含占位符，没有真实值
# 用法：把下面 YOUR_… 换成你自己的值，再在手机 Termux 里跑
# 原理：手机主动把本地 sshd 端口反向转发到服务器本机，服务器再经本机端口连回手机
# 注意：隧道断了，远程控机就断了；手机重启后要重起隧道
set -u

SERVER_HOST="YOUR_SERVER_HOST"
SERVER_USER="YOUR_SERVER_USER"
SERVER_SSH_KEY="$HOME/.ssh/YOUR_PHONE_TO_SERVER_KEY"
PHONE_SSHD_PORT="YOUR_PHONE_SSHD_PORT"
SERVER_TUNNEL_PORT="YOUR_SERVER_TUNNEL_PORT"

# 检查密钥存在（不要把密钥本身写进脚本、不要提交到仓库）
if [ ! -f "$SERVER_SSH_KEY" ]; then
  echo "KEY MISSING: 先生成手机到服务器的专用密钥，再跑本脚本"
  exit 1
fi

termux-wake-lock 2>/dev/null || true
sshd 2>/dev/null || true

exec autossh -M 0 -N \
  -o ServerAliveInterval=30 \
  -o ServerAliveCountMax=3 \
  -o ExitOnForwardFailure=yes \
  -o StrictHostKeyChecking=accept-new \
  -i "$SERVER_SSH_KEY" \
  -R "${SERVER_TUNNEL_PORT}:localhost:${PHONE_SSHD_PORT}" \
  "${SERVER_USER}@${SERVER_HOST}"
