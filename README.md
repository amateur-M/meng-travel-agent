# CoupleTrip — 情侣旅游规划 Agent

AI 驱动的旅游规划助手，根据日期、出发地、目的地、天气、景点、美食、预算与偏好，自动生成可执行的情侣行程。

## 技术栈

- **前端**：React 18 + TypeScript + Tailwind CSS + Framer Motion + Zustand
- **后端**：Python 3.13 + FastAPI + LangChain + LangGraph
- **LLM**：OpenAI GPT-4o

## 快速启动

### 后端

```bash
cd backend
cp .env.example .env   # 编辑 .env 填入 API 密钥
pip install -r requirements.txt
python main.py
```

### 前端

```bash
cd frontend
npm install
npm run dev
```

### Docker

```bash
docker-compose up
```

## 项目文档

新会话恢复上下文请按顺序阅读 `memory/` 目录下的文件。
