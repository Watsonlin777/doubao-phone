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
PHONE_RELAY_PORT="15555"        # 手机上 relay.py 的 --port（默认 15555；必须和手机 tv-relay.sh 的 RELAY_PORT 相同）
SERVER_LOCAL_PORT="15555"       # 服务器本机用来连电视的端口

# 占位符校验：没填真实值就退出
case "$TUNNEL_PORT/$PHONE_USER/$PHONE_KEY" in
  *YOUR_*) echo "先把 TUNNEL_PORT / PHONE_USER / PHONE_KEY 的 YOUR_… 换成真实值再跑"; exit 1 ;;
esac

echo "1) 检查反向隧道监听（服务器本机）"
if ! ss -tln | grep -q "127.0.0.1:${TUNNEL_PORT}"; then
  echo "隧道未监听：先在手机起反向隧道，再重试"
  exit 1
fi

echo "2) 经隧道把手机中继端口转发到服务器本机（只绑本机）"
# 已有我们这条转发在跑（带这条 -L 的 ssh 进程）就跳过；方括号写法避开 pgrep 自匹配
if pgrep -af "ssh.*-L 127[.]0[.]0[.]1:${SERVER_LOCAL_PORT}:" >/dev/null 2>&1; then
  echo "转发已在跑（ssh 带这条 -L）：127.0.0.1:${SERVER_LOCAL_PORT}，跳过新建"
elif ss -tln | grep -q "127.0.0.1:${SERVER_LOCAL_PORT}"; then
  echo "端口 ${SERVER_LOCAL_PORT} 已被别的进程占用（不是我们的 ssh 转发），先释放它再重试"
  exit 1
else
  ssh -f -N -o StrictHostKeyChecking=accept-new -o ExitOnForwardFailure=yes \
    -L "127.0.0.1:${SERVER_LOCAL_PORT}:127.0.0.1:${PHONE_RELAY_PORT}" \
    -p "${TUNNEL_PORT}" -i "${PHONE_KEY}" "${PHONE_USER}@127.0.0.1" || {
    echo "转发建立失败：检查隧道、密钥与手机中继是否在跑"
    exit 1
  }
  sleep 1
  pgrep -af "ssh.*-L 127[.]0[.]0[.]1:${SERVER_LOCAL_PORT}:" >/dev/null 2>&1 || {
    echo "转发未建立：检查手机中继是否在跑（tv-relay.sh）"
    exit 1
  }
  echo "本地转发已监听：127.0.0.1:${SERVER_LOCAL_PORT}（只说明本机端口起来了，不代表电视可达；跑下面的 probe 才是真验证）"
fi

echo ""
echo "3) 探电视（在服务器上跑，CleanYourTV 的 tv.py）"
echo "   TV_HOST=127.0.0.1 TV_PORT=${SERVER_LOCAL_PORT} tools/tv.py --probe"
echo "   TV_HOST=127.0.0.1 TV_PORT=${SERVER_LOCAL_PORT} tools/tv.py 'pm list packages'"
echo ""
echo "注意：转发是手动进程，隧道断了、服务器重启了，转发就没了，要重做。"
