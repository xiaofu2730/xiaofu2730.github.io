#!/bin/bash
# XiaoFu Blog Studio - macOS Launcher
cd "$(dirname "$0")"

echo "=================================================="
echo "  🚀 正在启动 XiaoFu Blog Studio 创作发布助手..."
echo "=================================================="

if [ -f "./.venv/bin/python3" ]; then
    ./.venv/bin/python3 scripts/blog_assistant.py
else
    python3 scripts/blog_assistant.py
fi
