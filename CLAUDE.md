# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

这是一个本地桥接服务,使 n8n 能够与 Browser Use Python 库通信。它模拟 Browser Use Cloud API 端点但在本地运行,允许执行浏览器自动化任务而无需依赖云服务。

## 核心技术栈

- **Web 框架**: FastAPI + Uvicorn
- **浏览器自动化**: Browser Use (使用 Patchright/Playwright)
- **AI 集成**: 支持多种 LLM 提供商
  - OpenAI (gpt-4o)
  - Anthropic (claude-3-opus)
  - Google AI (gemini-1.5-pro)
  - MistralAI
  - Ollama (本地)
  - Azure OpenAI
  - AWS Bedrock
- **语言**: Python 3.10+

## 开发命令

### 环境设置
```bash
# 创建虚拟环境
python -m venv venv

# 激活虚拟环境
source venv/bin/activate  # macOS/Linux
venv\Scripts\activate     # Windows

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env-example .env
# 编辑 .env 文件添加 API keys
```

### 运行服务
```bash
# 启动 FastAPI 服务器
python app.py

# 使用 Docker Compose
docker-compose up -d

# 构建 Docker 镜像
docker build -t browser-n8n-bridge .
```

### 测试
```bash
# 运行 API 测试
python test_api.py

# 使用不同的 AI 提供商测试
python test_api.py --provider anthropic
python test_api.py --provider google

# 启用有头浏览器模式测试
python test_api.py --headful

# 自定义任务和 URL
python test_api.py --url http://localhost:8000 --task "搜索 n8n"
```

### API 文档
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- Health Check: http://localhost:8000/api/v1/ping

## 架构设计

### 核心模块

#### 1. Task Storage (`task_storage/`)
- **抽象层**: `base.py` 定义 `TaskStorage` 抽象基类
- **实现**: `memory.py` 提供内存存储实现 `InMemoryTaskStorage`
- **默认用户**: `DEFAULT_USER_ID = "default"`
- **工厂模式**: `get_task_storage()` 用于获取存储实例

任务存储负责:
- 任务生命周期管理 (创建、更新、删除)
- 任务状态跟踪
- 执行步骤历史记录
- 媒体文件关联
- Agent 实例管理

#### 2. Task 状态机
```python
TaskStatus:
  CREATED → RUNNING → FINISHED
           ↓         ↓
         PAUSED → STOPPED
           ↓
         FAILED
```

特殊状态:
- `STOPPING`: 过渡状态,任务正在停止过程中

#### 3. LLM 提供商集成 (`get_llm()`)
根据 `ai_provider` 参数动态选择 LLM:
- 每个提供商有独立的环境变量配置
- 默认为 OpenAI,可通过 `DEFAULT_AI_PROVIDER` 修改
- 支持自定义 base_url (用于兼容 OpenAI 的 API)

#### 4. Browser 配置
- **Headful/Headless**: 通过 `BROWSER_USE_HEADFUL` 或请求参数控制
- **浏览器路径**: `CHROME_PATH` 指定自定义 Chrome 位置
- **用户数据**: `CHROME_USER_DATA` 用于持久化浏览器数据
- **截图**: 自动保存任务执行过程截图到 `media/{task_id}/`

#### 5. Media 管理
截图命名规则:
- 初始: `status-step-{step}-{timestamp}.png`
- 完成: `final-{timestamp}.png`
- 其他状态: `status-{status}-{timestamp}.png`

去重逻辑:
- 基于文件大小差异检测 (容差 0.5%,最小 1KB,最大 10KB)
- PNG 签名验证

### 主要 API 端点

| 端点 | 方法 | 功能 | 关键参数 |
|------|------|------|----------|
| `/api/v1/run-task` | POST | 启动浏览器任务 | task, ai_provider, headful, save_browser_data |
| `/api/v1/task/{task_id}` | GET | 获取任务详情 | task_id |
| `/api/v1/task/{task_id}/status` | GET | 获取任务状态 | task_id |
| `/api/v1/stop-task/{task_id}` | PUT | 停止任务 | task_id |
| `/api/v1/pause-task/{task_id}` | PUT | 暂停任务 | task_id |
| `/api/v1/resume-task/{task_id}` | PUT | 恢复任务 | task_id |
| `/api/v1/list-tasks` | GET | 列出所有任务 | page, per_page |
| `/live/{task_id}` | GET | 实时查看 UI | task_id |
| `/api/v1/task/{task_id}/media` | GET | 获取任务媒体 | task_id |

### 异步任务执行流程

1. **任务创建**: `run_task()` 接收请求,创建任务记录
2. **后台执行**: `execute_task()` 在 asyncio 任务中运行
3. **Agent 初始化**: 根据配置创建 Browser + LLM Agent
4. **步骤记录**: 使用回调函数 `action_callback()` 记录每个执行步骤
5. **截图捕获**: 每步执行后自动截图并去重保存
6. **结果存储**: 完成后更新任务状态和结果

### 重要实现细节

#### Browser Profile 管理
- 使用 `BrowserProfile` 类管理浏览器配置
- `save_browser_data=True` 时保存 cookies
- 支持自定义 Chrome 路径和用户数据目录

#### 生命周期管理
- `lifespan` 上下文管理器处理启动/关闭
- `cleanup_all_tasks()` 清理所有运行中的任务
- 优雅关闭机制确保浏览器实例正确释放

#### 多用户支持
- 通过 `X-User-Id` header 传递用户 ID
- 所有 task_storage 操作都支持 user_id 参数
- 默认使用 `DEFAULT_USER_ID` 如果未提供

#### 认证 (可选)
- Docker Compose 配置中可设置 `X_NAME` 和 `X_PASSWORD`
- 适用于需要基础认证的部署场景

## 环境变量

### 关键配置
- `PORT`: 服务端口 (默认 8000)
- `LOG_LEVEL`: 日志级别 (默认 INFO)
- `BROWSER_USE_HEADFUL`: 是否显示浏览器 UI (默认 false)
- `DEFAULT_AI_PROVIDER`: 默认 AI 提供商 (默认 openai)

### AI 提供商配置
每个 AI 提供商需要相应的 API key 和 model ID:
- OpenAI: `OPENAI_API_KEY`, `OPENAI_MODEL_ID`, `OPENAI_BASE_URL` (可选)
- Anthropic: `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL_ID`
- Google: `GOOGLE_API_KEY`, `GOOGLE_MODEL_ID`
- Azure: `AZURE_API_KEY`, `AZURE_ENDPOINT`, `AZURE_DEPLOYMENT_NAME`, `AZURE_API_VERSION`
- Bedrock: `BEDROCK_MODEL_ID`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`

### Browser 配置
- `CHROME_PATH`: Chrome 可执行文件路径
- `CHROME_USER_DATA`: Chrome 用户数据目录

## 部署

### Docker
- 基础镜像: `python:3.11-slim`
- Playwright 浏览器: 使用 patchright 安装 chromium
- 非 root 用户: `appuser` 运行服务
- 健康检查: 定期 ping `/api/v1/ping` 端点
- 数据持久化: 挂载 `./data` 到 `/app/data`

### 端口映射
- Docker Compose 默认: `24006:8000`
- 本地开发: `8000`

## 常见问题

### Browser Use 导入错误
确保已安装 browser-use 及其依赖:
```bash
pip install browser-use>=0.5.9
patchright install chromium
```

### API Key 问题
验证 `.env` 文件中的 API keys 是否正确设置

### 端口冲突
如果 8000 端口已被占用,修改 `.env` 中的 `PORT` 设置

### Docker 浏览器问题
确保 Dockerfile 中已安装所有 Playwright 依赖的系统库
