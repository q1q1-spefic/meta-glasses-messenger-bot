# Conversation Assistant Backend

Meta Glasses实时对话助手的Flask后端服务器。

## 功能特性

- 🤖 基于OpenAI GPT-4的智能对话建议生成
- 📊 支持多种场景（面试、社交、商务、日常）
- 💾 对话历史管理
- 🔄 RESTful API设计
- ⚡ 快速响应（通常<2秒）

## 快速开始

### 1. 安装依赖

```bash
cd conversation-assistant-backend

# 创建虚拟环境（推荐）
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
# 复制配置文件
cp .env.example .env

# 编辑 .env 文件，添加你的OpenAI API密钥
# OPENAI_API_KEY=sk-xxx
```

### 3. 启动服务器

```bash
# 开发模式
python app.py

# 生产模式（使用gunicorn）
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

服务器将在 `http://localhost:5000` 启动

### 4. 测试API

```bash
# 健康检查
curl http://localhost:5000/

# 测试对话建议生成
curl -X POST http://localhost:5000/api/conversation-suggest \
  -H "Content-Type: application/json" \
  -d '{
    "message": "你对我们公司有什么了解？",
    "context": {
      "scenario": "interview",
      "user_background": "5年软件开发经验",
      "conversation_goal": "获得offer"
    }
  }'
```

## API文档

### 1. 对话建议生成

**端点：** `POST /api/conversation-suggest`

**请求体：**
```json
{
  "message": "对方说的话",
  "context": {
    "scenario": "interview",  // 可选：interview, social, business, general
    "user_background": "用户背景信息",  // 可选
    "conversation_goal": "对话目标"  // 可选
  }
}
```

**响应：**
```json
{
  "success": true,
  "data": {
    "suggestion": "建议的回答内容",
    "analysis": "对问题的分析",
    "tips": ["技巧1", "技巧2"],
    "confidence": 0.85,
    "timestamp": "2025-01-17T..."
  }
}
```

### 2. 获取对话历史

**端点：** `GET /api/conversation-history`

**响应：**
```json
{
  "success": true,
  "data": [
    {"role": "user", "content": "..."},
    {"role": "assistant", "content": "..."}
  ]
}
```

### 3. 清空对话历史

**端点：** `DELETE /api/conversation-history`

### 4. 获取支持的场景

**端点：** `GET /api/scenarios`

## 场景类型说明

| 场景类型 | 适用场景 | 特点 |
|---------|---------|------|
| `interview` | 求职面试 | STAR法则、突出优势 |
| `social` | 社交场合 | 轻松友好、真诚幽默 |
| `business` | 商务沟通 | 专业高效、数据驱动 |
| `general` | 日常对话 | 自然真诚、灵活调整 |

## 高级配置

### 自定义模型

在 `.env` 中修改：
```env
OPENAI_MODEL=gpt-4  # 使用更强大的模型
```

### 调整响应长度

修改 `app.py` 中的 `max_tokens`:
```python
response = openai_client.chat.completions.create(
    model=self.model,
    messages=messages,
    max_tokens=800,  # 增加到800
    ...
)
```

### 添加数据库持久化

未来可集成SQLite/PostgreSQL存储对话历史：
```python
# TODO: 实现数据库存储
# from flask_sqlalchemy import SQLAlchemy
# app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///conversations.db'
```

## 部署指南

### 本地开发
```bash
python app.py
```

### 使用gunicorn（生产）
```bash
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

### Docker部署（可选）
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5000", "app:app"]
```

### 云服务部署

**推荐平台：**
- Railway.app (免费额度)
- Render.com (免费额度)
- Fly.io
- AWS EC2

## 故障排查

### API密钥错误
```
Error: OPENAI_API_KEY not found
```
**解决：** 确保 `.env` 文件中配置了正确的API密钥

### CORS错误
```
Access-Control-Allow-Origin error
```
**解决：** 已启用CORS，检查浏览器扩展配置

### 响应慢
- 检查网络连接
- 考虑使用 `gpt-4o-mini` 而不是 `gpt-4`
- 减少 `max_tokens`

## 安全注意事项

⚠️ **生产环境必做：**
1. 修改 `FLASK_SECRET_KEY` 为随机字符串
2. 设置 `FLASK_DEBUG=False`
3. 使用HTTPS
4. 添加请求速率限制
5. 实现用户认证

## 许可证

MIT License
