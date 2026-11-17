#!/bin/bash
# 服务器端电视中继转发模板 —— 只含占位符，没有真实值
# 前提：手机反向隧道已建好，手机上的 tv-relay.sh 已在跑
# 做法：经反向隧道，把手机本机中继端口转发到服务器本机（只绑本机），并实际建立转发
# 然后服务器上 TV_HOST=127.0.0.1 TV_PORT=<本机端口> 跑 CleanYourTV 的 tv.py
# 电视 IP 变了（重启、换网）要先在手机上改 tv-relay.sh 再重起中继
set -u

TUNNEL_PORT="YOUR_SERVER_TUNNEL_PORT"
PHONE_USER="YOUR_PHONE_TERMUX_USER"
PHONE_KEY="/root/.ssh/YOUR_SERVER_TO_PHONE_KEY"
PHONE_RELAY_PORT="15555"        # 手机上 relay.py 的 --port（默认 15555）
SERVER_LOCAL_PORT="15555"       # 服务器本机用来连电视的端口

echo "1) 检查反向隧道监听（服务器本机）"
if ! ss -tln | grep -q "127.0.0.1:${TUNNEL_PORT}"; then
  echo "隧道未监听：先在手机起反向隧道，再重试"
  exit 1
fi

echo "2) 经隧道把手机中继端口转发到服务器本机（只绑本机）"
if ss -tln | grep -q "127.0.0.1:${SERVER_LOCAL_PORT}"; then
  echo "转发已在监听：127.0.0.1:${SERVER_LOCAL_PORT}，跳过新建"
else
  ssh -f -N -L "127.0.0.1:${SERVER_LOCAL_PORT}:127.0.0.1:${PHONE_RELAY_PORT}" \
    -p "${TUNNEL_PORT}" -i "${PHONE_KEY}" "${PHONE_USER}@127.0.0.1" || {
    echo "转发建立失败：检查隧道、密钥与手机中继是否在跑"
    exit 1
  }
  sleep 1
  ss -tln | grep -q "127.0.0.1:${SERVER_LOCAL_PORT}" || {
    echo "转发未监听：检查手机中继是否在跑（tv-relay.sh）"
    exit 1
  }
  echo "转发已建立：127.0.0.1:${SERVER_LOCAL_PORT} -> 手机中继 -> 电视"
fi

echo ""
echo "3) 探电视（在服务器上跑，CleanYourTV 的 tv.py）"
echo "   TV_HOST=127.0.0.1 TV_PORT=${SERVER_LOCAL_PORT} tools/tv.py --probe"
echo "   TV_HOST=127.0.0.1 TV_PORT=${SERVER_LOCAL_PORT} tools/tv.py 'pm list packages'"
echo ""
echo "注意：转发是手动进程，隧道断了、服务器重启了，转发就没了，要重做。"
