#!/bin/bash
# 服务器端 adb 转发模板 —— 只含占位符，没有真实值
# 前提：手机反向隧道已建好，服务器本机已有反向隧道端口监听
# 做法：经反向隧道，把手机无线调试的配对端口和连接端口转发到服务器本机（只绑本机）
# 端口每次配对都可能变，重启、换网后可能要重新配对；配对码只用一次，用完即废
set -u

TUNNEL_PORT="YOUR_SERVER_TUNNEL_PORT"
PHONE_USER="YOUR_PHONE_TERMUX_USER"
PHONE_KEY="/root/.ssh/YOUR_SERVER_TO_PHONE_KEY"

echo "1) 检查反向隧道监听（服务器本机）"
ss -tln | grep "127.0.0.1:${TUNNEL_PORT}" || echo "隧道未监听：先在手机起反向隧道，再重试"

echo "2) 经隧道转发手机无线调试端口到服务器本机"
echo "   示例（把端口换成你当时在手机无线调试里看到的实际端口）："
echo "   ssh -N -L 127.0.0.1:YOUR_PAIR_PORT:localhost:YOUR_PHONE_PAIR_PORT \\"
echo "          -L 127.0.0.1:YOUR_CONNECT_PORT:localhost:YOUR_PHONE_CONNECT_PORT \\"
echo "          -p ${TUNNEL_PORT} -i ${PHONE_KEY} ${PHONE_USER}@127.0.0.1"
echo ""
echo "3) 配对与连接（在服务器上跑，配对码只用一次）"
echo "   adb pair 127.0.0.1:YOUR_PAIR_PORT"
echo "   adb connect 127.0.0.1:YOUR_CONNECT_PORT"
echo "   adb devices   # 应为 device（已授权）状态"
echo ""
echo "注意：转发是手动进程，隧道断了、服务器重启了，转发就没了，要重做。"
