#!/usr/bin/env bash
set -e

echo "========================================="
echo "  iWiki — 个人知识库构建工具"
echo "  安装配置脚本"
echo "========================================="
echo ""

# Detect OS
OS="$(uname -s)"
case "$OS" in
  Darwin)  echo "[✓] 检测到 macOS" ;;
  Linux)   echo "[✓] 检测到 Linux" ;;
  *)       echo "[!] 未知操作系统: $OS，继续尝试..." ;;
esac

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Helper: open a file or URL in browser
open_browser() {
  if command -v open &>/dev/null; then
    open "$1"
  elif command -v xdg-open &>/dev/null; then
    xdg-open "$1"
  fi
}

# Check Python
echo ""
echo "[1/5] 检查 Python..."
PYTHON=""
for cmd in python3 python; do
  if command -v $cmd &>/dev/null; then
    VER=$($cmd --version 2>&1 | grep -Eo '[0-9]+\.[0-9]+' | head -1)
    if [ -n "$VER" ]; then
      MAJOR=$(echo $VER | cut -d. -f1)
      MINOR=$(echo $VER | cut -d. -f2)
      if [ "$MAJOR" -ge 3 ] && [ "$MINOR" -ge 10 ]; then
        PYTHON=$cmd
        echo "[✓] $cmd $VER"
        break
      else
        echo "[✗] $cmd 版本 $VER < 3.10，跳过"
      fi
    fi
  fi
done

if [ -z "$PYTHON" ]; then
  echo "[✗] 未找到 Python >= 3.10"
  echo "    下载地址: https://www.python.org/downloads/"
  exit 1
fi

# Setup venv
echo ""
echo "[2/4] 准备虚拟环境..."
if [ -d "venv" ] && [ -f "venv/bin/activate" ]; then
  echo "[✓] 虚拟环境已存在"
else
  $PYTHON -m venv venv
  echo "[✓] 虚拟环境已创建"
fi
source venv/bin/activate

# Check if deps already installed
echo ""
echo "[3/4] 检查依赖..."
if $PYTHON -c "import fastapi, uvicorn, litellm, networkx" 2>/dev/null; then
  echo "[✓] 依赖已安装，跳过"
else
  echo "  依赖未安装，即将下载..."

  # Choose mirror
  echo ""
  echo "  选择 PyPI 镜像源："
  echo "    1) 清华镜像 (国内用户推荐，速度快)"
  echo "    2) 官方源"
  read -p "  请选择 (1/2，回车默认 1): " -r MIRROR_CHOICE
  echo

  # Install deps
  echo "[4/4] 安装依赖..."
  if [ "$MIRROR_CHOICE" = "2" ]; then
    pip install --quiet -r requirements.txt
  else
    pip install --quiet -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple --trusted-host pypi.tuna.tsinghua.edu.cn
  fi
  echo "[✓] 依赖安装完成"
fi

# Done
echo ""
echo "========================================="
echo "  安装完成！"
echo "========================================="
echo ""

# Start server in background
echo "正在后台启动 iWiki 服务..."
PID_FILE="$SCRIPT_DIR/.iwiki-server.pid"
LOG_FILE="$SCRIPT_DIR/.iwiki-server.log"
python server/server.py > "$LOG_FILE" 2>&1 &
SERVER_PID=$!
echo $SERVER_PID > "$PID_FILE"
sleep 2

# Cleanup: kill server when terminal closes or Ctrl+C
cleanup() {
  kill $SERVER_PID 2>/dev/null
  rm -f "$PID_FILE"
  echo ""
  echo "服务已停止"
}
trap cleanup EXIT INT TERM HUP

# Check server actually started
if kill -0 $SERVER_PID 2>/dev/null; then
  echo "[✓] 服务已启动 (PID: $SERVER_PID)"
else
  echo "[✗] 服务启动失败，请查看日志: $LOG_FILE"
  rm -f "$PID_FILE"
  exit 1
fi

echo ""

# Open the graph page
IWIKI_URL="http://localhost:8765"
echo "正在打开知识图谱页面..."
open_browser "$IWIKI_URL"

echo ""
echo "  图谱页面: $IWIKI_URL"
echo "  关闭本终端或按 Ctrl+C 停止服务"
echo ""

# Keep running until Ctrl+C or terminal close
wait $SERVER_PID
