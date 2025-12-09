# Browser-n8n-local 项目结构

这是 Browser-n8n-local 项目的完整技术栈和项目结构文档,针对 AI 代理优化。

## 项目元信息

- **项目名称**: browser-n8n-local
- **类型**: Python Web API 服务
- **主要用途**: n8n 本地浏览器自动化桥接服务
- **Python 版本**: 3.10+
- **主要框架**: FastAPI + Browser Use
- **架构模式**: 分层架构 (API → 业务逻辑 → 数据访问)

---

## 完整技术栈

### Web 框架层
| 组件 | 版本 | 用途 |
|------|------|------|
| **FastAPI** | >=0.104.0 | 异步 Web 框架,API 端点定义 |
| **Uvicorn** | >=0.24.0 | ASGI 服务器,运行 FastAPI 应用 |
| **Pydantic** | >=2.5.0 | 数据验证和序列化 |

### 浏览器自动化层
| 组件 | 版本/来源 | 用途 |
|------|------|------|
| **Browser Use** | git@6d3e276 | 核心浏览器自动化库 (固定提交) |
| **Playwright** | >=1.40.0 | 底层浏览器驱动 (通过 Patchright) |

### AI/LLM 集成层
| 组件 | 版本 | 提供商 |
|------|------|--------|
| **langchain** | >=0.3.0 | LLM 框架核心 |
| **langchain-openai** | >=0.3.0 | OpenAI 集成 |
| **langchain-anthropic** | >=0.3.0 | Anthropic Claude 集成 |
| **langchain-google-genai** | >=2.0.0 | Google Gemini 集成 |
| **langchain-mistralai** | >=0.0.2 | MistralAI 集成 |
| **langchain-ollama** | >=0.0.1 | Ollama 本地 LLM 集成 |
| **langchain-aws** | >=0.0.1 | AWS Bedrock 集成 |
| **openai** | >=1.0.0 | OpenAI 官方 SDK |
| **anthropic** | >=0.8.0 | Anthropic 官方 SDK |
| **google-generativeai** | >=0.3.0 | Google AI SDK |

### 工具库
| 组件 | 版本 | 用途 |
|------|------|------|
| **python-dotenv** | >=1.0.0 | 环境变量管理 |
| **requests** | >=2.31.0 | HTTP 客户端 (用于测试) |
| **pyyaml** | >=6.0 | YAML 解析 (测试管理) |

---

## 项目文件树

```
browser-n8n-local/
├── 📁 .claude/                      # Claude Code 配置
│   ├── 📁 commands/                 # 自定义 Slash 命令
│   │   ├── code-review.md          # 代码审查命令
│   │   ├── create-docs.md          # 文档生成命令
│   │   ├── full-context.md         # 完整上下文加载
│   │   ├── gemini-consult.md       # Gemini 咨询命令
│   │   ├── handoff.md              # 任务交接命令
│   │   ├── refactor.md             # 重构命令
│   │   └── update-docs.md          # 文档更新命令
│   ├── 📁 hooks/                    # 钩子脚本
│   │   └── subagent-context-injector.sh  # 子代理上下文注入
│   └── settings.local.json         # 本地 Claude 设置
│
├── 📁 app/                          # FastAPI 应用层
│   ├── __init__.py                 # 模块初始化
│   ├── bootstrap.py                # 应用启动和生命周期管理
│   ├── routes.py                   # API 端点定义 (491 行)
│   ├── models.py                   # Pydantic 请求/响应模型
│   ├── middleware.py               # CORS 和 Enum 序列化中间件
│   └── dependencies.py             # 依赖注入 (用户 ID 提取)
│
├── 📁 task/                         # 任务执行层
│   ├── __init__.py                 # 模块初始化
│   ├── executor.py                 # 任务编排和执行 (170 行)
│   ├── agent.py                    # Agent 配置构建
│   ├── llm.py                      # LLM 提供商集成 (158 行)
│   ├── browser_config.py           # 浏览器配置管理 (117 行)
│   ├── schema_utils.py             # JSON Schema → Pydantic 转换 (209 行)
│   ├── utils.py                    # 工具函数 (敏感数据提取)
│   ├── constants.py                # 常量、枚举、日志配置
│   └── 📁 storage/                  # 存储抽象层
│       ├── __init__.py             # 工厂函数
│       ├── base.py                 # TaskStorage 抽象基类
│       └── memory.py               # InMemoryTaskStorage 实现
│
├── 📁 test/                         # 测试模块
│   ├── __init__.py                 # 模块初始化
│   └── simple_test.py              # 端到端测试用例
│
├── 📁 data/                         # 运行时数据目录
│   ├── 📁 browser/                  # 浏览器数据
│   │   ├── storage_state.json      # 浏览器状态持久化
│   │   └── 📁 tmp_user_data_*/      # 临时用户数据目录
│   └── 📁 media/                    # 任务媒体文件 (截图等)
│       └── 📁 {task_id}/            # 按任务 ID 组织
│
├── 📁 docs/                         # 项目文档
│   ├── 📁 ai-context/               # AI 上下文文档 (第1层)
│   │   ├── project-structure.md    # 本文档
│   │   ├── docs-overview.md        # 文档架构概览
│   │   ├── deployment-infrastructure.md  # 部署文档 (模板)
│   │   ├── system-integration.md   # 系统集成文档 (模板)
│   │   └── handoff.md              # 任务交接文档 (模板)
│   ├── 📁 open-issues/              # 问题跟踪 (示例)
│   ├── 📁 specs/                    # 功能规格 (示例)
│   ├── CLAUDE.md                   # AI 上下文模板 (通用)
│   ├── CONTEXT-tier2-component.md  # 第2层文档模板
│   ├── CONTEXT-tier3-feature.md    # 第3层文档模板
│   ├── MCP-ASSISTANT-RULES.md      # MCP 助手规则 (模板)
│   └── README.md                   # 文档系统说明
│
├── app.py                          # 应用入口点 (1041 字节)
├── CLAUDE.md                       # 主 AI 上下文文档 (第1层)
├── README.md                       # 用户文档 (16111 字节)
├── requirements.txt                # Python 依赖清单
├── .env-example                    # 环境变量模板
├── .env                            # 环境变量配置 (本地,已忽略)
├── .gitignore                      # Git 忽略规则
├── LICENSE                         # MIT 许可证
└── latest_task_id.txt              # 最新任务 ID (运行时文件)
```

---

## 核心模块详解

### 1. 应用层 (`app/`)

#### 目的
处理 HTTP 请求,提供 RESTful API,管理应用生命周期。

#### 关键文件

**`app.py`** (入口点)
- 功能: 启动 Uvicorn 服务器,运行 FastAPI 应用
- 重构说明: 逻辑已提取到 `app/` 模块

**`app/bootstrap.py`** (应用启动)
- 创建 FastAPI 应用实例
- 配置 CORS 中间件
- 管理生命周期 (启动/关闭)
- 优雅关闭: 清理所有运行中的任务

**`app/routes.py`** (API 端点,491 行)
- 10+ RESTful 端点实现
- 任务 CRUD 操作
- 实时查看 UI
- 健康检查端点

**`app/models.py`** (数据模型)
- `TaskRequest`: 任务请求模型
- `TaskResponse`: 任务响应模型
- `TaskStatusResponse`: 状态响应模型
- 使用 Pydantic v2 进行验证

**`app/middleware.py`** (中间件)
- CORS 配置: 允许所有来源
- Enum 序列化: 自定义 JSON 编码器

**`app/dependencies.py`** (依赖注入)
- `get_user_id()`: 从 `X-User-ID` header 提取用户 ID
- 默认用户: `"default"`

---

### 2. 任务执行层 (`task/`)

#### 目的
编排任务执行,管理 Agent,配置 LLM 和浏览器。

#### 关键文件

**`task/executor.py`** (任务编排,170 行)
- `execute_task()`: 主执行函数 (10步流程)
- `cleanup_all_tasks()`: 优雅关闭时清理所有任务
- 错误处理: try/except/finally 三层防护
- 异步执行: asyncio.create_task()

**`task/agent.py`** (Agent 配置)
- `create_agent_config()`: 构建 Browser Use Agent 配置
- 支持 Vision 模式
- 支持结构化输出 (output_model_schema)

**`task/llm.py`** (LLM 集成,158 行)
- `get_llm(ai_provider)`: 工厂函数,动态选择 LLM
- 支持 7+ AI 提供商
- 环境变量驱动配置

**`task/browser_config.py`** (浏览器配置,117 行)
- `configure_browser_profile()`: 生成 BrowserSession 配置
- Headful/Headless 模式
- 临时用户数据目录管理
- 浏览器启动参数配置

**`task/schema_utils.py`** (Schema 处理,209 行)
- `parse_output_model_schema()`: JSON Schema → Pydantic 动态转换
- 递归模型创建
- 支持嵌套对象、数组、枚举

**`task/utils.py`** (工具函数)
- `get_sensitive_data()`: 提取 `X_*` 环境变量
- 敏感数据注入机制

**`task/constants.py`** (常量和枚举)
- `TaskStatus`: 7种任务状态枚举
- `DEFAULT_USER_ID`: 默认用户 ID
- 日志配置: logging.basicConfig()

---

### 3. 存储层 (`task/storage/`)

#### 目的
提供任务数据存储抽象,支持多种存储后端。

#### 关键文件

**`task/storage/base.py`** (抽象基类)
- `TaskStorage`: ABC 定义存储接口
- 方法: create_task, update_task_status, get_task, 等
- 多用户支持: 所有方法接受 `user_id` 参数

**`task/storage/memory.py`** (内存实现)
- `InMemoryTaskStorage`: 内存存储实现
- 数据结构: `Dict[user_id, Dict[task_id, task_data]]`
- Agent 实例管理: 不可序列化,仅内存存储

**`task/storage/__init__.py`** (工厂函数)
- `get_task_storage(storage_type)`: 存储工厂
- 默认: "memory"
- 扩展点: 可添加 PostgreSQL、MongoDB、Redis

---

### 4. 测试模块 (`test/`)

#### 目的
端到端测试,验证 API 功能。

#### 关键文件

**`test/simple_test.py`**
- `TestBrowserN8N`: 测试类
- 测试场景:
  - 任务创建和状态查询
  - 任务控制 (暂停/恢复/停止)
  - 完整流程测试
  - 结构化输出测试

---

### 5. 文档系统 (`docs/`)

#### 三层文档架构

**第1层 (基础/系统级)**
- `/CLAUDE.md`: 主 AI 上下文 (727 行,完整项目文档)
- `/docs/ai-context/project-structure.md`: 本文档
- `/docs/ai-context/docs-overview.md`: 文档导航

**第2层 (组件级)** - 模板
- 未使用 (项目为单体应用)

**第3层 (功能特定)** - 模板
- 未使用 (可为 `app/`, `task/` 等创建)

---

## 数据流架构

### 请求流程
```
Client Request
    ↓
[FastAPI Routes] (app/routes.py)
    ↓
[依赖注入] (app/dependencies.py) - 提取 user_id
    ↓
[任务创建] task_storage.create_task()
    ↓
[后台执行] asyncio.create_task(execute_task)
    ↓ (非阻塞返回)
[立即响应] TaskResponse(id, status=CREATED)
```

### 任务执行流程 (后台)
```
execute_task()
    ↓
[1] prepare_task_environment() - 更新状态为 RUNNING
    ↓
[2] get_llm(ai_provider) - 初始化 LLM
    ↓
[3] configure_browser_profile() - 配置浏览器
    ↓
[4] 处理高级特性 (Vision, Schema, 敏感数据)
    ↓
[5] create_agent_config() - 构建 Agent 配置
    ↓
[6] Agent(**config) - 创建 Agent 实例
    ↓
[7] await agent.run() - 执行浏览器自动化
    ↓
[8] 处理结果 (set_task_output, collect_cookies)
    ↓
[9] mark_task_finished() - 更新状态为 FINISHED/FAILED
    ↓
[10] cleanup_task() - 关闭浏览器,释放资源
```

---

## 环境配置

### 必需环境变量
- **至少一个 LLM 提供商的 API Key**
  - `OPENAI_API_KEY` + `OPENAI_MODEL_ID`
  - 或 `ANTHROPIC_API_KEY` + `ANTHROPIC_MODEL_ID`
  - 或 `GOOGLE_API_KEY` + `GOOGLE_MODEL_ID`

### 可选环境变量
- `PORT`: 服务端口 (默认 8000)
- `LOG_LEVEL`: 日志级别 (默认 INFO)
- `DEFAULT_AI_PROVIDER`: 默认 AI 提供商 (默认 openai)
- `BROWSER_USE_HEADFUL`: 显示浏览器 UI (默认 false)
- `CHROME_PATH`: 自定义 Chrome 路径
- `CHROME_USER_DATA`: Chrome 用户数据目录

### 敏感数据注入
- 以 `X_` 前缀的环境变量会被注入到 Agent
- 例如: `X_PASSWORD`, `X_API_KEY`, `X_USERNAME`

---

## API 端点概览

| 端点 | 方法 | 功能 | 源代码 |
|------|------|------|--------|
| `/api/v1/run-task` | POST | 启动浏览器任务 | routes.py:67-109 |
| `/api/v1/task/{task_id}` | GET | 获取任务详情 | routes.py:112-124 |
| `/api/v1/task/{task_id}/status` | GET | 获取任务状态 | routes.py:127-145 |
| `/api/v1/stop-task/{task_id}` | PUT | 停止任务 | routes.py:148-179 |
| `/api/v1/pause-task/{task_id}` | PUT | 暂停任务 | routes.py:182-207 |
| `/api/v1/resume-task/{task_id}` | PUT | 恢复任务 | routes.py:210-235 |
| `/api/v1/list-tasks` | GET | 列出任务(分页) | routes.py:238-268 |
| `/api/v1/ping` | GET | 健康检查 | routes.py:271-275 |
| `/api/v1/browser-config` | GET | 获取浏览器配置 | routes.py:359-377 |
| `/live/{task_id}` | GET | 实时查看 UI | routes.py:278-356 |

---

## 架构模式

### 设计模式
1. **分层架构**: API Layer → Business Logic → Data Access
2. **工厂模式**: LLM 提供商选择、存储后端选择
3. **抽象基类**: TaskStorage ABC 定义存储契约
4. **依赖注入**: FastAPI 依赖系统
5. **异步事件驱动**: asyncio 非阻塞任务执行

### 扩展点
- **新 LLM 提供商**: 在 `task/llm.py` 中添加 elif 分支
- **新存储后端**: 实现 `TaskStorage` 接口,在工厂中注册
- **新 API 端点**: 在 `app/routes.py` 中添加路由函数
- **新中间件**: 在 `app/middleware.py` 中添加中间件

---

## 开发工作流

### 本地开发
```bash
# 1. 创建虚拟环境
python -m venv venv
source venv/bin/activate  # macOS/Linux

# 2. 安装依赖
pip install -r requirements.txt

# 3. 配置环境变量
cp .env-example .env
# 编辑 .env 添加 API keys

# 4. 启动服务
python app.py

# 5. 访问 API 文档
# http://localhost:8000/docs
```

### 测试
```bash
# 运行测试
python test/simple_test.py
```

### 代码质量
- **类型注解**: 大部分函数有类型提示
- **日志记录**: 结构化日志 (时间戳 + 模块 + 级别 + 消息)
- **错误处理**: 三层防护 (try/except/finally)

---

## 部署

### 当前状态
- **Docker**: 未配置 (无 Dockerfile/docker-compose.yml)
- **部署方式**: 直接运行 Python 应用
- **进程管理**: 建议使用 systemd 或 supervisord

### 未来计划
- 容器化部署 (Docker/Docker Compose)
- 持久化存储 (PostgreSQL/MongoDB)
- 并发限制和任务队列

---

## 已知限制

1. **无任务持久化**: 服务重启后任务丢失 (仅内存存储)
2. **无并发限制**: 可能导致资源耗尽
3. **Agent 不可序列化**: 无法恢复运行中的任务
4. **截图功能已移除**: 自动截图功能已禁用
5. **Media 端点未实现**: 仅在文档中存在

---

## 相关文档

- **[CLAUDE.md](/CLAUDE.md)** - 完整 AI 上下文和架构文档
- **[README.md](/README.md)** - 用户友好的快速入门指南
- **[docs-overview.md](/docs/ai-context/docs-overview.md)** - 文档架构导航
- **[requirements.txt](/requirements.txt)** - Python 依赖清单
- **[.env-example](/.env-example)** - 环境变量配置示例

---

**文档版本**: 2025-12-09
**代码库版本**: master (commit: 753ba3b)
**针对**: AI 代理优化 - 提供快速导航和深度技术细节
