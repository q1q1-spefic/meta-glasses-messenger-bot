#!/bin/bash

# 启动脚本 - Meta Glasses AI Assistant Backend

cd "$(dirname "$0")"

# 激活虚拟环境
source venv/bin/activate

# 设置端口
export PORT=5001

# 启动Flask
python app.py
