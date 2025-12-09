# CLAUDE.md

这是为 Claude Code AI 助手提供的项目上下文文档。

## 快速参考

### 关键文件路径
- **入口点**: `app.py` - 应用启动
- **API 路由**: `app/routes.py:73-491` - 所有 API 端点定义
- **任务执行**: `task/executor.py:37-170` - 核心任务编排逻辑
- **LLM 集成**: `task/llm.py:14-158` - 多提供商 LLM 配置
- **浏览器配置**: `task/browser_config.py:22-117` - 浏览器自动化配置
- **存储抽象**: `task/storage/base.py` + `task/storage/memory.py` - 任务存储层

### 常用命令速查
```bash
# 启动服务
python app.py

# 运行测试
python test/simple_test.py

# 查看 API 文档
# http://localhost:8000/docs

# 健康检查
curl http://localhost:8000/api/v1/ping
```

### 核心环境变量
| 变量 | 用途 | 默认值 |
|------|------|--------|
| `PORT` | 服务端口 | 8000 |
| `DEFAULT_AI_PROVIDER` | 默认 AI 提供商 | openai |
| `BROWSER_USE_HEADFUL` | 显示浏览器 UI | false |
| `OPENAI_API_KEY` | OpenAI API 密钥 | 必需 |
| `CHROME_PATH` | 自定义 Chrome 路径 | 可选 |

---

## 项目概述

这是一个本地桥接服务,使 n8n 能够与 Browser Use Python 库通信。它模拟 Browser Use Cloud API 端点但在本地运行,允许执行浏览器自动化任务而无需依赖云服务。

### 核心价值主张
- **本地控制**: 完全本地运行,无云依赖
- **多 LLM 支持**: 7+ AI 提供商集成
- **API 兼容**: 兼容 Browser Use Cloud API 端点
- **灵活配置**: Headful/Headless、视觉模式、结构化输出

---

## 核心技术栈

### Web 框架层
- **FastAPI** (`>=0.104.0`) - 现代异步 Web 框架
  - 自动生成 OpenAPI 文档 (`/docs`, `/redoc`)
  - 基于 Pydantic 的请求/响应验证
  - 异步路由处理

- **Uvicorn** (`>=0.24.0`) - ASGI 服务器
  - 配置: `host="0.0.0.0"`, `port=8000` (可配置)
  - 异步事件循环: `asyncio`

- **Pydantic** (`>=2.5.0`) - 数据验证与序列化
  - 请求模型: `TaskRequest` (`app/models.py:8-17`)
  - 响应模型: `TaskResponse`, `TaskStatusResponse`

### 浏览器自动化层
- **Browser Use** - 核心浏览器自动化库
  - 来源: Git 仓库 `https://github.com/browser-use/browser-use.git@6d3e276`
  - 固定到特定提交以保持稳定性

- **Patchright/Playwright** (`>=1.40.0`) - 底层浏览器驱动
  - 使用 Chromium 引擎
  - 支持 Headful/Headless 模式

### AI/LLM 集成层
支持的 AI 提供商 (通过 LangChain):

| 提供商 | 模型类 | 默认模型 | 环境变量 |
|--------|--------|----------|----------|
| **OpenAI** | `ChatOpenAI` | gpt-4o | `OPENAI_API_KEY`, `OPENAI_MODEL_ID`, `OPENAI_BASE_URL` (可选) |
| **Anthropic** | `ChatAnthropic` | claude-3-opus-20240229 | `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL_ID` |
| **Google AI** | `ChatGoogle` | gemini-1.5-pro | `GOOGLE_API_KEY`, `GOOGLE_MODEL_ID` |
| **MistralAI** | (未启用) | mistral-large-latest | `MISTRAL_API_KEY`, `MISTRAL_MODEL_ID` |
| **Ollama** | `ChatOllama` | llama3 | `OLLAMA_MODEL_ID`, `OLLAMA_API_BASE` |
| **Azure OpenAI** | `ChatAzureOpenAI` | gpt-4o | `AZURE_API_KEY`, `AZURE_ENDPOINT`, `AZURE_DEPLOYMENT_NAME`, `AZURE_API_VERSION` |
| **AWS Bedrock** | `ChatAWSBedrock` | anthropic.claude-3-sonnet-20240229-v1:0 | `BEDROCK_MODEL_ID`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION` |

**LLM 选择机制**: `task/llm.py:14-158` - `get_llm(ai_provider)` 工厂函数

### 依赖包
- **langchain** (`>=0.3.0`) - LLM 框架核心
- **langchain-openai** (`>=0.3.0`) - OpenAI 集成
- **langchain-anthropic** (`>=0.3.0`) - Anthropic Claude 集成
- **langchain-google-genai** (`>=2.0.0`) - Google Gemini 集成
- **python-dotenv** (`>=1.0.0`) - 环境变量管理

---

## 代码组织结构

项目已重构为模块化架构 (`app.py:1-7`):

```
browser-n8n-local/
├── app/                    # FastAPI 应用层
│   ├── bootstrap.py       # 应用启动和生命周期管理
│   ├── routes.py          # API 端点定义 (491 行)
│   ├── models.py          # Pydantic 请求/响应模型
│   ├── middleware.py      # CORS 和 Enum 序列化中间件
│   └── dependencies.py    # 依赖注入 (提取 X-User-ID)
├── task/                   # 任务执行层
│   ├── executor.py        # 任务编排和执行 (170 行)
│   ├── agent.py           # Agent 配置构建
│   ├── llm.py             # LLM 提供商集成 (158 行)
│   ├── browser_config.py  # 浏览器配置管理 (117 行)
│   ├── schema_utils.py    # JSON Schema → Pydantic 动态转换 (209 行)
│   ├── utils.py           # 工具函数 (敏感数据提取)
│   ├── constants.py       # 常量、枚举、日志配置
│   └── storage/           # 存储抽象层
│       ├── base.py        # 抽象基类 (TaskStorage ABC)
│       ├── memory.py      # 内存存储实现 (InMemoryTaskStorage)
│       └── __init__.py    # 工厂函数 get_task_storage()
├── test/                   # 测试模块
│   └── simple_test.py     # 端到端测试用例
├── app.py                  # 应用入口点
├── requirements.txt        # Python 依赖
├── .env-example            # 环境变量模板
└── README.md               # 用户文档
```

---

## 架构设计

### 核心设计模式

#### 1. 分层架构 (Layered Architecture)
```
┌─────────────────────────────┐
│   API Layer (app/)          │  ← FastAPI 路由、中间件、依赖注入
├─────────────────────────────┤
│   Business Logic (task/)    │  ← 任务编排、Agent 配置、LLM 集成
├─────────────────────────────┤
│   Data Access (storage/)    │  ← 抽象存储接口、内存实现
└─────────────────────────────┘
```

**优势**:
- 关注点分离
- 易于测试和维护
- 层间低耦合

#### 2. 工厂模式 (Factory Pattern)
**位置**: `task/storage/__init__.py`, `task/llm.py`

```python
# 存储工厂
def get_task_storage(storage_type="memory") -> TaskStorage:
    if storage_type == "memory":
        return InMemoryTaskStorage()
    # 可扩展: PostgreSQL, Redis, MongoDB

# LLM 工厂
def get_llm(ai_provider: str):
    if ai_provider == "anthropic":
        return ChatAnthropic(...)
    elif ai_provider == "google":
        return ChatGoogle(...)
    # ... 其他提供商
```

**用途**: 解耦接口和具体实现,易于扩展新提供商/存储后端

#### 3. 抽象基类模式 (ABC Pattern)
**位置**: `task/storage/base.py`

```python
class TaskStorage(ABC):
    @abstractmethod
    def create_task(self, task_id: str, task_data: Dict, user_id: str) -> None:
        pass
    # ... 其他抽象方法
```

**用途**: 定义存储接口契约,强制实现类遵循规范

#### 4. 依赖注入 (Dependency Injection)
**位置**: `app/routes.py`, `app/dependencies.py`

```python
# app/dependencies.py
async def get_user_id(x_user_id: Optional[str] = Header(None)) -> str:
    return x_user_id or DEFAULT_USER_ID

# app/routes.py
async def run_task(request: TaskRequest, user_id: str = Depends(get_user_id)):
    # user_id 通过依赖注入获取
```

**优势**: 易于测试,解耦路由和身份识别逻辑

#### 5. 异步事件驱动 (Async Event-Driven)
**位置**: `app/routes.py:77`, `task/executor.py`

```python
# 立即返回任务 ID,不阻塞 API 响应
asyncio.create_task(execute_task(task_id, request.task, ai_provider, user_id, task_storage))
return TaskResponse(id=task_id, status=TaskStatus.CREATED, live_url=live_url)
```

**流程**:
```
Client Request → [API Handler] → create_task() → return task_id (立即返回)
                       ↓
                 asyncio.create_task(execute_task)
                       ↓
                 [Background Worker 异步执行]
```

---

## 任务存储层 (Task Storage)

### 抽象基类 (`task/storage/base.py`)
定义标准存储接口:
- 任务 CRUD 操作
- 状态管理
- 执行步骤历史
- 媒体文件关联
- Agent 实例管理 (内存中,不可序列化)
- 多用户支持 (通过 `user_id` 隔离)

### 内存存储实现 (`task/storage/memory.py`)
```python
class InMemoryTaskStorage:
    def __init__(self):
        self._tasks: Dict[str, Dict[str, Dict]] = {}  # 按 user_id 隔离
        self._agents: Dict[str, Dict[str, Any]] = {}  # Agent 实例 (不持久化)
```

**默认用户**: `DEFAULT_USER_ID = "default"` (`task/constants.py`)

**扩展点**: 可实现 PostgreSQL、MongoDB、Redis 存储后端

---

## 任务状态机

### 状态定义 (`task/constants.py`)
```python
class TaskStatus(str, Enum):
    CREATED = "created"
    RUNNING = "running"
    FINISHED = "finished"
    STOPPED = "stopped"
    PAUSED = "paused"
    FAILED = "failed"
    STOPPING = "stopping"  # 过渡状态,防止重复停止
```

### 状态转换规则
```
CREATED → RUNNING → FINISHED
    ↓        ↓         ↓
  PAUSED → STOPPED ← STOPPING
    ↓
  FAILED
```

**关键规则**:
- `CREATED → RUNNING`: 任务开始执行
- `RUNNING → PAUSED/STOPPING/FAILED/FINISHED`: 运行中可能的转换
- `PAUSED → RUNNING/STOPPED`: 暂停后可恢复或停止
- `STOPPING → STOPPED`: 过渡状态,确保优雅停止

---

## 异步任务执行流程

### 完整生命周期 (`task/executor.py:37-170`)

```
┌─────────────────────────────┐
│ 1. POST /api/v1/run-task    │  创建任务记录 (status=CREATED)
└──────────┬──────────────────┘
           │
           ▼
┌─────────────────────────────┐
│ 2. asyncio.create_task()    │  启动后台任务 (非阻塞)
│    execute_task()            │
└──────────┬──────────────────┘
           │
           ▼
┌─────────────────────────────┐
│ 3. 准备任务环境              │  prepare_task_environment()
│    - 更新状态为 RUNNING      │  task_storage.update_task_status()
│    - 获取任务配置            │
└──────────┬──────────────────┘
           │
           ▼
┌─────────────────────────────┐
│ 4. 初始化 LLM 提供商         │  get_llm(ai_provider)
└──────────┬──────────────────┘
           │
           ▼
┌─────────────────────────────┐
│ 5. 配置浏览器                │  configure_browser_profile()
│    - BrowserSession          │  - viewport, window_size
│    - headful/headless        │  - user_data_dir (临时或持久)
└──────────┬──────────────────┘
           │
           ▼
┌─────────────────────────────┐
│ 6. 处理高级特性              │
│    - Vision 模式             │  use_vision: "auto"/"true"/"false"
│    - 结构化输出              │  output_model_schema (JSON Schema)
│    - 敏感数据注入            │  get_sensitive_data() (X_* 环境变量)
└──────────┬──────────────────┘
           │
           ▼
┌─────────────────────────────┐
│ 7. 创建 Agent                │  Agent(**agent_config)
│    - create_agent_config     │  task/agent.py
└──────────┬──────────────────┘
           │
           ▼
┌─────────────────────────────┐
│ 8. 执行浏览器自动化          │  await agent.run()
│    (注: 截图功能已移除)      │
└──────────┬──────────────────┘
           │
           ▼
┌─────────────────────────────┐
│ 9. 处理结果                  │
│    - 存储输出                │  set_task_output()
│    - 收集 Cookies (可选)     │  collect_browser_cookies()
└──────────┬──────────────────┘
           │
           ▼
┌─────────────────────────────┐
│ 10. 完成和清理               │
│     - mark_task_finished()   │  status=FINISHED/FAILED
│     - cleanup_task()         │  关闭浏览器,释放资源
└─────────────────────────────┘
```

### 错误处理机制 (`task/executor.py:122-143`)
```python
try:
    result = await agent.run()
    # 处理成功结果
except Exception as e:
    logger.exception(f"Error executing task {task_id}")
    task_storage.update_task_status(task_id, TaskStatus.FAILED, user_id)
    task_storage.set_task_error(task_id, str(e), user_id)
finally:
    await cleanup_task(browser, task_id, user_id, task_storage)
```

**三层防护**:
1. **异常捕获**: 记录错误并更新任务状态为 FAILED
2. **日志记录**: `logger.exception()` 包含完整堆栈跟踪
3. **资源清理**: `finally` 确保浏览器关闭,防止进程泄漏

---

## API 端点详细说明

### 端点概览 (`app/routes.py`)

| 端点 | 方法 | 功能 | 源代码位置 |
|------|------|------|------------|
| `/api/v1/run-task` | POST | 启动浏览器任务 | routes.py:67-109 |
| `/api/v1/task/{task_id}` | GET | 获取任务详情 | routes.py:112-124 |
| `/api/v1/task/{task_id}/status` | GET | 获取任务状态 | routes.py:127-145 |
| `/api/v1/stop-task/{task_id}` | PUT | 停止任务 | routes.py:148-179 |
| `/api/v1/pause-task/{task_id}` | PUT | 暂停任务 | routes.py:182-207 |
| `/api/v1/resume-task/{task_id}` | PUT | 恢复任务 | routes.py:210-235 |
| `/api/v1/list-tasks` | GET | 列出任务 (分页) | routes.py:238-268 |
| `/api/v1/ping` | GET | 健康检查 | routes.py:271-275 |
| `/api/v1/browser-config` | GET | 获取浏览器配置 | routes.py:359-377 |
| `/live/{task_id}` | GET | 实时查看 UI | routes.py:278-356 |

### 关键请求参数 (`app/models.py:8-17`)

**POST /api/v1/run-task**
```python
class TaskRequest(BaseModel):
    task: str                              # 任务描述 (必需)
    ai_provider: Optional[str] = None      # AI 提供商 (默认: DEFAULT_AI_PROVIDER)
    headful: bool = False                  # 有头浏览器模式
    save_browser_data: bool = False        # 持久化 Cookies
    use_vision: Optional[str] = "auto"     # Vision 模式: "auto"/"true"/"false"
    output_model_schema: Optional[str] = None  # JSON Schema 字符串
    browser_config: Optional[Dict] = {}    # 自定义浏览器配置
```

---

## 高级特性

### 1. Vision 模式 (`task/executor.py:99-107`)
**用途**: 启用 LLM 的视觉理解能力

**配置**:
- `"auto"`: 自动检测 (默认)
- `"true"`: 强制启用视觉模式
- `"false"`: 禁用视觉模式

**代码示例**:
```python
if use_vision.lower() == "true":
    vision_value = True
elif use_vision.lower() == "false":
    vision_value = False
else:
    vision_value = "auto"
```

### 2. 结构化输出 (JSON Schema) (`task/schema_utils.py`)
**用途**: 强制 LLM 返回符合预定义 schema 的结构化数据

**实现**: `parse_output_model_schema(schema_str)` (209 行)
- JSON Schema → Pydantic 动态模型转换
- 支持嵌套对象、数组、枚举
- 递归模型创建,避免使用裸 dict

**使用示例**:
```json
{
  "output_model_schema": {
    "type": "object",
    "properties": {
      "title": {"type": "string"},
      "price": {"type": "number"},
      "tags": {"type": "array", "items": {"type": "string"}}
    },
    "required": ["title", "price"]
  }
}
```

### 3. 敏感数据注入 (`task/utils.py`)
**用途**: 将敏感数据 (密码、API keys) 安全地传递给 Agent

**机制**:
```python
def get_sensitive_data():
    """提取以 X_ 开头的环境变量作为敏感数据"""
    sensitive_data = {}
    for key, value in os.environ.items():
        if key.startswith("X_") and value:
            sensitive_data[key] = value
    return sensitive_data
```

**命名约定**:
- 环境变量以 `X_` 前缀命名 (例如: `X_PASSWORD`, `X_API_KEY`)
- 这些数据在任务执行时对 Agent 可用,但不会记录在日志中

### 4. 浏览器配置高级选项 (`task/browser_config.py`)

**核心配置** (`browser_config.py:22-117`):
```python
{
    "headless": bool,                      # 无头/有头模式
    "chrome_instance_path": str,           # Chrome 可执行路径
    "viewport": {"width": 1280, "height": 720},
    "window_size": {"width": 1280, "height": 720},
    "wait_for_network_idle_page_load_time": 2.0,
    "wait_between_actions": 1.0,
    "dom_highlight_elements": False,
    "disable_security": False,
    "storage_state": "data/browser/storage_state.json",
    "user_data_dir": str,                  # 动态生成或自定义
}
```

**临时用户数据目录** (`browser_config.py:67-69`):
```python
# 每次任务使用独立浏览器环境
timestamp = time.strftime("%Y%m%d_%H%M%S")
unique_id = str(uuid.uuid4())[:8]
user_data_path = browser_data_dir / f"tmp_user_data_{timestamp}_{unique_id}"
```

**浏览器启动参数**:
- **通用**: `--disable-blink-features=AutomationControlled`, `--disable-dev-shm-usage`
- **Headful**: `--start-maximized`
- **Headless**: `--no-sandbox`, `--disable-gpu`, `--window-size=1920,1080`

**自定义窗口配置** (`browser_config.py:92-95`):
```python
# 请求中可传递 window_config 覆盖默认配置
window_config = task_browser_config.get("window_config")
if window_config:
    browser_config_args.update(window_config)
```

---

## 多用户支持

### 用户隔离机制
- **用户 ID 提取**: 通过 `X-User-ID` HTTP header 传递 (`app/dependencies.py`)
- **默认用户**: `DEFAULT_USER_ID = "default"` (未提供 header 时)
- **存储隔离**: 所有 task_storage 操作都支持 `user_id` 参数

### 实现细节 (`task/storage/memory.py`)
```python
self._tasks: Dict[str, Dict[str, Dict]] = {}  # 第一层 key 为 user_id
self._agents: Dict[str, Dict[str, Any]] = {}  # 第一层 key 为 user_id
```

---

## 生命周期管理

### 应用启动和关闭 (`app/bootstrap.py`)

**Lifespan 上下文管理器**:
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动逻辑
    logger.info("FastAPI application started")
    yield
    # 关闭逻辑
    logger.info("Shutting down, cleaning up tasks...")
    await cleanup_all_tasks()
```

**优雅关闭**: `cleanup_all_tasks()` (`task/executor.py:148-170`)
- 遍历所有用户的所有任务
- 更新运行中任务状态为 STOPPED
- 关闭所有 Agent 和浏览器实例
- 防止僵尸进程

**信号处理** (Unix 平台):
- 捕获 SIGTERM, SIGINT 信号
- 触发优雅关闭流程

---

## 安全设计

### 1. Chrome 路径安全限制 (`app/routes.py:360-377`)
**决策**: Chrome 路径仅通过环境变量配置,不接受请求参数

**原因**: 防止恶意请求指定任意可执行文件路径 (命令注入风险)

**配置方式**:
```python
# 仅从环境变量读取
CHROME_PATH = os.environ.get("CHROME_PATH")
CHROME_USER_DATA = os.environ.get("CHROME_USER_DATA")
```

**注释**: `routes.py:360-362`
```
# Note: Chrome paths (CHROME_PATH and CHROME_USER_DATA) can only be set via
# environment variables for security reasons and cannot be overridden in task requests.
```

### 2. 敏感数据处理
- API keys 仅通过环境变量传递
- `X_` 前缀敏感数据不记录在日志中
- 用户 ID 隔离防止跨用户数据泄漏

---

## 已知限制和未来扩展

### 当前限制

1. **无任务持久化**: 服务重启后所有任务丢失
   - **原因**: 仅实现内存存储
   - **扩展点**: 实现 PostgreSQL/MongoDB 存储后端

2. **无并发限制**: 可能导致资源耗尽
   - **建议**: 添加 `asyncio.Semaphore` 限制并发数

3. **Agent 实例不可序列化**: 无法恢复运行中的任务
   - **原因**: Agent 对象包含复杂运行时状态
   - **解决方案**: 设计任务检查点机制

4. **截图功能已移除**: 自动截图功能已禁用
   - **位置**: `task/executor.py:129` 注释
   - **状态**: 计划重新实现或完全移除

5. **Media 端点未实现**: `/api/v1/task/{task_id}/media` 端点仅在文档中
   - **验证**: `app/routes.py` 中未找到实现
   - **建议**: 移除文档或实现功能

### 扩展点

#### 存储层扩展
```python
# task/storage/postgres.py (未来)
class PostgreSQLTaskStorage(TaskStorage):
    def create_task(self, task_id, task_data, user_id):
        # 实现 PostgreSQL 存储逻辑
        pass
```

#### LLM 提供商扩展
```python
# task/llm.py
def get_llm(ai_provider: str):
    # 添加新提供商
    elif ai_provider == "cohere":
        return ChatCohere(...)
```

---

## 环境变量配置

### 关键配置
- `PORT`: 服务端口 (默认 8000)
- `LOG_LEVEL`: 日志级别 (默认 INFO)
- `BROWSER_USE_HEADFUL`: 是否显示浏览器 UI (默认 false)
- `DEFAULT_AI_PROVIDER`: 默认 AI 提供商 (默认 openai)

### AI 提供商配置
每个 AI 提供商需要相应的 API key 和 model ID (详见 `.env-example`):
- **OpenAI**: `OPENAI_API_KEY`, `OPENAI_MODEL_ID`, `OPENAI_BASE_URL` (可选)
- **Anthropic**: `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL_ID`
- **Google**: `GOOGLE_API_KEY`, `GOOGLE_MODEL_ID`
- **Azure**: `AZURE_API_KEY`, `AZURE_ENDPOINT`, `AZURE_DEPLOYMENT_NAME`, `AZURE_API_VERSION`
- **Bedrock**: `BEDROCK_MODEL_ID`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`
- **Ollama**: `OLLAMA_MODEL_ID`, `OLLAMA_API_BASE`

### Browser 配置
- `CHROME_PATH`: Chrome 可执行文件路径 (可选)
- `CHROME_USER_DATA`: Chrome 用户数据目录 (可选)

---

## 开发指南

### 命名约定
- **模块命名**: 全小写,下划线分隔 (`task_storage`, `browser_config`)
- **类命名**: 大驼峰 (`TaskStorage`, `InMemoryTaskStorage`)
- **函数命名**: 小写,下划线分隔 (`get_llm()`, `execute_task()`)
- **私有函数**: 前缀 `_` (`_parse_field_schema()`)
- **常量命名**: 全大写 (`DEFAULT_USER_ID`, `PORT`)

### 日志记录 (`task/constants.py`)
```python
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("browser-use-bridge")
```

**日志级别使用**:
- `INFO`: 任务状态变化、配置信息
- `WARNING`: 非致命问题 (如缺少 Cookie 方法)
- `ERROR`: 执行失败
- `EXCEPTION`: 包含堆栈跟踪的错误

### 配置管理优先级
1. 请求参数 (最高优先级)
2. 环境变量
3. 硬编码默认值 (最低优先级)

---

## 测试

### 测试文件
- **主测试文件**: `test/simple_test.py` (非 `test_api.py`)
- **测试类**: `TestBrowserN8N`
- **测试场景**: 任务创建、状态查询、任务控制、完整流程、结构化输出

### 运行测试
```bash
# 运行所有测试
python test/simple_test.py

# 配置测试
BASE_URL = "http://localhost:8000"
AI_PROVIDER = "google"  # 可配置
HEADFUL = True          # 显示浏览器窗口
```

---

## 故障排查

### Browser Use 导入错误
```bash
pip install -r requirements.txt
patchright install chromium
```

### API Key 问题
- 验证 `.env` 文件中的 API keys 是否正确设置
- 检查是否有多余空格或引号

### 端口冲突
```bash
# 修改 .env 中的 PORT
PORT=8001
```

---

## 相关文档

- **[README.md](/README.md)** - 用户友好的项目介绍和快速入门
- **[.env-example](/.env-example)** - 完整的环境变量配置示例
- **[app/routes.py](/app/routes.py)** - API 端点实现
- **[task/executor.py](/task/executor.py)** - 任务执行核心逻辑
- **[task/llm.py](/task/llm.py)** - LLM 提供商集成

---

**文档版本**: 2025-12-09
**代码库版本**: master (commit: 753ba3b)
**针对**: Claude Code AI 助手优化
