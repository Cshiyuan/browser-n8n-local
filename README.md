# Browser Use Local Bridge for n8n

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

A local bridge service that enables n8n to communicate with the [Browser Use](https://github.com/browser-use/browser-use) Python library. This service mimics Browser Use Cloud API endpoints but runs locally, giving you full control over browser automation tasks without cloud dependencies.

## Table of Contents

- [Features](#features)
- [Quick Start](#quick-start)
- [Tech Stack](#tech-stack)
- [Installation](#installation)
- [Configuration](#configuration)
- [API Reference](#api-reference)
- [Usage Examples](#usage-examples)
- [Testing](#testing)
- [Architecture](#architecture)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [License](#license)

## Features

### Core Capabilities
- **Cloud API Compatible**: Drop-in replacement for Browser Use Cloud API endpoints
- **Multi-LLM Support**: Works with OpenAI, Anthropic, Google AI, MistralAI, Ollama, Azure OpenAI, and AWS Bedrock
- **Complete Task Management**: Run, pause, resume, and stop browser automation tasks
- **Real-time Monitoring**: Live view UI and status tracking for running tasks
- **Media Capture**: Automatic screenshots at each execution step with deduplication
- **Flexible Deployment**: Run locally or in containers

### Advanced Features
- Headful/Headless browser modes
- Browser profile and cookie persistence
- Custom Chrome installation support
- Structured output with JSON Schema validation
- Vision mode for visual understanding tasks
- RESTful API with interactive documentation (Swagger UI)

## Quick Start

```bash
# Clone and setup
git clone https://github.com/henry0hai/browser-n8n-local.git
cd browser-n8n-local
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env-example .env
# Edit .env and add your API keys

# Run the server
python app.py
```

Visit http://localhost:8000/docs for the interactive API documentation.

## Tech Stack

- **Web Framework**: [FastAPI](https://fastapi.tiangolo.com/) + [Uvicorn](https://www.uvicorn.org/)
- **Browser Automation**: [Browser Use](https://github.com/browser-use/browser-use) (powered by Patchright/Playwright)
- **AI Integration**: Multi-provider support via LangChain
  - OpenAI (GPT-4o, GPT-4, etc.)
  - Anthropic (Claude 3 Opus, Sonnet, etc.)
  - Google AI (Gemini 1.5 Pro, etc.)
  - MistralAI, Ollama, Azure OpenAI, AWS Bedrock
- **Language**: Python 3.10+

## Prerequisites

- Python 3.10 or higher
- pip (Python package manager)
- Browser Use Python library (installed via requirements.txt)
- API keys for your preferred LLM provider(s)

## Installation

1. Clone this repository:
   ```bash
   git clone https://github.com/henry0hai/browser-n8n-local.git
   cd browser-n8n-local
   ```

2. Create a virtual environment (recommended):
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Set up environment variables:
   ```bash
   cp .env-example .env
   ```
   Then edit the `.env` file to add your OpenAI and/or Anthropic API keys.

## Running the Service

### Local Development

```bash
# Activate virtual environment
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Start the server
python app.py
```

The server will start at http://localhost:8000 by default.

### Access Points

- **API Documentation (Swagger UI)**: http://localhost:8000/docs
- **Alternative API Docs (ReDoc)**: http://localhost:8000/redoc
- **Health Check**: http://localhost:8000/api/v1/ping

## Configuration

Configure the service by editing the `.env` file. Below are the available configuration options grouped by category.

### General Settings

```env
PORT=8000                # Server port (default: 8000)
LOG_LEVEL=INFO           # Logging level: DEBUG, INFO, WARNING, ERROR
```

### Browser Settings

```env
# Display mode
BROWSER_USE_HEADFUL=false  # Set to "true" to show browser UI

# Custom Chrome installation (optional)
CHROME_PATH=/path/to/chrome
CHROME_USER_DATA=/path/to/user/data
```

### AI Provider Configuration

Set the default provider with `DEFAULT_AI_PROVIDER` (default: `openai`). You can override this per request using the `ai_provider` parameter.

#### OpenAI
```env
OPENAI_API_KEY=sk-...
OPENAI_MODEL_ID=gpt-4o
OPENAI_BASE_URL=https://api.openai.com/v1  # Optional, for compatible APIs
```

#### Anthropic
```env
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_MODEL_ID=claude-3-opus-20240229
```

#### Google AI
```env
GOOGLE_API_KEY=...
GOOGLE_MODEL_ID=gemini-1.5-pro
```

#### MistralAI
```env
MISTRAL_API_KEY=...
MISTRAL_MODEL_ID=mistral-large-latest
```

#### Ollama (Local)
```env
OLLAMA_API_BASE=http://localhost:11434
OLLAMA_MODEL_ID=llama3
```

#### Azure OpenAI
```env
AZURE_API_KEY=...
AZURE_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_DEPLOYMENT_NAME=your-deployment
AZURE_API_VERSION=2023-05-15
```

#### AWS Bedrock
```env
BEDROCK_MODEL_ID=anthropic.claude-3-sonnet-20240229-v1:0
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_REGION=us-east-1
```

## API Reference

### Endpoints Overview

| Method | Endpoint                           | Description                       |
|--------|-------------------------------------|-----------------------------------|
| POST   | `/api/v1/run-task`                  | Start a new browser task          |
| GET    | `/api/v1/task/{task_id}`            | Get complete task details         |
| GET    | `/api/v1/task/{task_id}/status`     | Get task execution status         |
| PUT    | `/api/v1/stop-task/{task_id}`       | Stop a running task               |
| PUT    | `/api/v1/pause-task/{task_id}`      | Pause a running task              |
| PUT    | `/api/v1/resume-task/{task_id}`     | Resume a paused task              |
| GET    | `/api/v1/list-tasks`                | List all tasks (paginated)        |
| GET    | `/live/{task_id}`                   | Live browser view UI              |
| GET    | `/api/v1/ping`                      | Health check endpoint             |
| GET    | `/api/v1/task/{task_id}/media`      | Get latest task screenshot        |
| GET    | `/api/v1/task/{task_id}/media/list` | List all task media files         |
| GET    | `/api/v1/media/{task_id}/{filename}`| Retrieve specific media file      |

### Key Request Parameters

**POST /api/v1/run-task**
- `task` (required): Description of the task to execute
- `ai_provider` (optional): AI provider to use (default: configured `DEFAULT_AI_PROVIDER`)
  - Options: `openai`, `anthropic`, `google`, `mistral`, `ollama`, `azure`, `bedrock`
- `headful` (optional): Run browser in headful mode (default: `false`)
- `save_browser_data` (optional): Persist browser cookies and session (default: `false`)
- `use_vision` (optional): Enable vision mode for visual understanding (default: `false`)
- `output_schema` (optional): JSON Schema for structured output validation

## Usage Examples

### Basic Task Execution

```bash
# Start a simple search task
curl -X POST http://localhost:8000/api/v1/run-task \
  -H "Content-Type: application/json" \
  -d '{
    "task": "Go to google.com and search for n8n automation",
    "ai_provider": "openai"
  }'

# Response
{
  "task_id": "abc123",
  "status": "running",
  "message": "Task started successfully"
}
```

### Advanced Task with Options

```bash
# Run with headful browser and save session data
curl -X POST http://localhost:8000/api/v1/run-task \
  -H "Content-Type: application/json" \
  -d '{
    "task": "Login to example.com and navigate to dashboard",
    "ai_provider": "anthropic",
    "headful": true,
    "save_browser_data": true
  }'
```

### Structured Output Example

```bash
# Extract data with JSON Schema validation
curl -X POST http://localhost:8000/api/v1/run-task \
  -H "Content-Type: application/json" \
  -d '{
    "task": "Go to news.ycombinator.com and extract top 5 stories",
    "output_schema": {
      "type": "object",
      "properties": {
        "stories": {
          "type": "array",
          "items": {
            "type": "object",
            "properties": {
              "title": {"type": "string"},
              "url": {"type": "string"},
              "points": {"type": "number"}
            }
          }
        }
      }
    }
  }'
```

### Vision Mode Example

```bash
# Use vision for visual understanding
curl -X POST http://localhost:8000/api/v1/run-task \
  -H "Content-Type: application/json" \
  -d '{
    "task": "Analyze the layout of example.com homepage",
    "use_vision": true
  }'
```

### Task Management

```bash
# Check task status
curl http://localhost:8000/api/v1/task/{task_id}/status

# Get complete task details
curl http://localhost:8000/api/v1/task/{task_id}

# Pause a running task
curl -X PUT http://localhost:8000/api/v1/pause-task/{task_id}

# Resume a paused task
curl -X PUT http://localhost:8000/api/v1/resume-task/{task_id}

# Stop a task
curl -X PUT http://localhost:8000/api/v1/stop-task/{task_id}

# List all tasks (with pagination)
curl "http://localhost:8000/api/v1/list-tasks?page=1&per_page=10"
```

### Media Retrieval

```bash
# Get latest screenshot
curl http://localhost:8000/api/v1/task/{task_id}/media \
  --output screenshot.png

# List all media files
curl http://localhost:8000/api/v1/task/{task_id}/media/list

# Get specific media file
curl http://localhost:8000/api/v1/media/{task_id}/final-1234567890.png \
  --output final.png
```

## Architecture

### System Overview

```
┌─────────────┐         ┌──────────────────┐         ┌─────────────┐
│   n8n or    │  HTTP   │  FastAPI Bridge  │         │  Browser    │
│   Client    │────────▶│                  │────────▶│  Use Agent  │
└─────────────┘         │  - API Routes    │         └─────────────┘
                        │  - Task Storage  │               │
                        │  - LLM Provider  │               │
                        └──────────────────┘               │
                                 │                         │
                                 ▼                         ▼
                        ┌──────────────────┐    ┌─────────────────┐
                        │   LLM Providers  │    │  Chromium via   │
                        │  (OpenAI, etc.)  │    │  Patchright     │
                        └──────────────────┘    └─────────────────┘
```

### Core Components

1. **Task Storage**: In-memory storage managing task lifecycle, execution steps, and media files
2. **LLM Integration**: Dynamic provider selection supporting 7+ AI providers
3. **Browser Management**: Automated browser control with screenshot capture and deduplication
4. **API Layer**: RESTful endpoints with FastAPI providing async task execution

### Task Lifecycle

```
CREATED → RUNNING → FINISHED
    ↓        ↓
  PAUSED ← STOPPED
    ↓
  FAILED
```

For more detailed architecture information, see `CLAUDE.md`.

## Testing

The project includes a comprehensive test suite to verify all API functionality.

### Quick Start

```bash
# Run all test suites
./run_tests.sh

# Or use Python directly
python test/run_tests.py
```

### Test Suite Options

```bash
# Run specific test suite
python test/run_tests.py --suite basic_tests

# Run multiple test suites
python test/run_tests.py --suite basic_tests --suite vision_tests

# Enable verbose output
python test/run_tests.py --verbose

# Generate JSON report
python test/run_tests.py --report test_results.json
```

### Interactive Testing

```bash
# Interactive test runner
python test/test_api.py

# Test specific features
python test/test_api.py --test vision      # Vision mode tests
python test/test_api.py --test schema      # Schema validation tests
python test/test_api.py --test control     # Task control tests
```

### Available Test Suites

| Suite | Description | Coverage |
|-------|-------------|----------|
| `basic_tests` | Core functionality | Search, navigation, screenshots |
| `vision_tests` | Vision capabilities | Visual understanding modes |
| `schema_tests` | Structured output | JSON Schema parsing and validation |

### Test Documentation

For comprehensive testing documentation:
- **[test/README.md](test/README.md)** - Test suite overview and setup
- **[test/TEST_GUIDE.md](test/TEST_GUIDE.md)** - Detailed testing guide and best practices

## Troubleshooting

### Common Issues

**ImportError: browser-use module not found**
```bash
# Ensure browser-use and dependencies are installed
pip install -r requirements.txt
patchright install chromium
```

**API Key Errors**
- Verify API keys are correctly set in `.env`
- Check for extra spaces or quotes around keys
- Ensure the key has appropriate permissions

**Port Already in Use**
```bash
# Change port in .env
PORT=8001

# Or set environment variable
PORT=8001 python app.py
```

**Browser Launch Failures**
```bash
# Install Chromium for Patchright
patchright install chromium

# Or specify custom Chrome path in .env
CHROME_PATH=/path/to/chrome
```

**Task Execution Timeouts**
- Check your LLM provider's rate limits
- Verify network connectivity to LLM API
- Try with a different AI provider

**Test Failures**
```bash
# Run with verbose output for details
python test/run_tests.py --verbose

# Check server is running
curl http://localhost:8000/api/v1/ping
```

### Getting Help

- Check the [Issues](https://github.com/henry0hai/browser-n8n-local/issues) page
- Review [CLAUDE.md](CLAUDE.md) for detailed architecture information
- Open a new issue with:
  - Error messages and stack traces
  - Your environment (OS, Python version)
  - Steps to reproduce the problem

## Contributing

Contributions are welcome! Here's how you can help:

### Development Setup

```bash
# Fork and clone the repository
git clone https://github.com/YOUR_USERNAME/browser-n8n-local.git
cd browser-n8n-local

# Create a virtual environment
python -m venv venv
source venv/bin/activate

# Install development dependencies
pip install -r requirements.txt

# Run tests to ensure everything works
./run_tests.sh
```

### Contribution Guidelines

1. **Fork the repository** and create a feature branch
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes** following the existing code style

3. **Test your changes** thoroughly
   ```bash
   python test/run_tests.py
   ```

4. **Commit with clear messages**
   ```bash
   git commit -m "Add feature: description of your changes"
   ```

5. **Push and create a Pull Request**
   ```bash
   git push origin feature/your-feature-name
   ```

### What to Contribute

- Bug fixes and improvements
- New AI provider integrations
- Enhanced test coverage
- Documentation improvements
- Performance optimizations

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgements

This project is built on the shoulders of giants:

- **[Browser Use](https://github.com/browser-use/browser-use)** - The powerful browser automation library that makes this possible
- **[FastAPI](https://fastapi.tiangolo.com/)** - The modern, high-performance web framework
- **[Patchright](https://github.com/Kaliiiiiiiiii-Vinyzu/patchright)** - Patched Playwright for enhanced browser control
- **[n8n](https://n8n.io/)** - The workflow automation platform this bridge is designed to integrate with

---

**Made with ❤️ for the automation community**
