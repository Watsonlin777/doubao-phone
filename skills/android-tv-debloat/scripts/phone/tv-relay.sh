#!/bin/bash
# 手机端电视中继模板 —— 只含占位符，没有真实值
# 用法：把下面 YOUR_… 换成你自己的值，再在手机 Termux 里跑
# 原理：手机跑 CleanYourTV 的 relay.py，把本机一个端口转发到电视的 ADB 端口
#   （relay 只绑 127.0.0.1，绝不暴露到网络；手机就是电视的调试服务器）
# 服务器经反向隧道连到这个中继端口，再用 tv.py 对电视下命令
# 注意：中继断了，服务器就够不着电视了；手机重启、换网后要重起中继
set -u

TV_HOST="YOUR_TV_IP"            # 电视的 IP（只要 IP，不要加 http://，不要加路径）
TV_PORT="YOUR_TV_ADB_PORT"      # 电视的 ADB 端口，一般 5555；无线调试配对端口见电视屏幕
RELAY_PORT="15555"              # 手机本机中继端口（relay.py 默认 15555）
CLEANYOURTV_DIR="$HOME/cleanyourtv"   # CleanYourTV 仓库在手机上的位置

# 检查 Python 与工具
command -v python3 >/dev/null || { echo "缺 python3：先 pkg install python"; exit 1; }
[ -f "$CLEANYOURTV_DIR/tools/relay.py" ] || { echo "找不到 $CLEANYOURTV_DIR/tools/relay.py：先 git clone https://github.com/Gathin23/cleanyourtv"; exit 1; }

termux-wake-lock 2>/dev/null || true

echo "中继：127.0.0.1:${RELAY_PORT} -> ${TV_HOST}:${TV_PORT}"
echo "服务器侧用 TV_HOST=127.0.0.1 TV_PORT=<服务器本机转发端口> 连 tv.py"
exec python3 "$CLEANYOURTV_DIR/tools/relay.py" "${TV_HOST}:${TV_PORT}" --port "$RELAY_PORT"
