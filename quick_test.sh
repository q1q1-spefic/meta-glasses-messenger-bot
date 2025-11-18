#!/bin/bash

echo "🧪 快速测试Flask后端"
echo "===================="

cd "$(dirname "$0")"

# 激活虚拟环境
source venv/bin/activate

echo ""
echo "1️⃣ 测试环境变量..."
python -c "
import os
from dotenv import load_dotenv
load_dotenv()
api_key = os.getenv('OPENAI_API_KEY')
if api_key and api_key.startswith('sk-proj-'):
    print('✅ OpenAI API Key已配置')
else:
    print('❌ OpenAI API Key未配置')
    exit(1)
"

echo ""
echo "2️⃣ 测试OpenAI连接..."
python -c "
from openai import OpenAI
import os
from dotenv import load_dotenv

load_dotenv()
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

try:
    response = client.chat.completions.create(
        model='gpt-4o-mini',
        messages=[{'role': 'user', 'content': '说一个字：好'}],
        max_tokens=5
    )
    print('✅ OpenAI API连接成功')
    print(f'   响应: {response.choices[0].message.content}')
except Exception as e:
    print(f'❌ OpenAI API连接失败: {e}')
    exit(1)
"

echo ""
echo "✨ 所有测试通过！Flask后端已准备就绪！"
echo ""
echo "下一步："
echo "1. 启动服务器: python app.py"
echo "2. 查看 YOUR_NEXT_STEPS.md 完成剩余配置"
