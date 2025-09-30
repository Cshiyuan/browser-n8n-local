from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid
import base64
import mimetypes

from typing import Optional
from datetime import datetime, UTC
from enum import Enum
from typing import cast
from types import TracebackType


import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, Response, Query, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles

from langchain_anthropic import ChatAnthropic
from langchain_mistralai import ChatMistralAI
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_ollama import ChatOllama
from langchain_aws import ChatBedrock
from langchain_openai import AzureChatOpenAI, ChatOpenAI
from pydantic import BaseModel

# This import will work once browser-use is installed
# For development, you may need to add the browser-use repo to your PYTHONPATH
# from browser_use import Agent
# from browser_use.agent.views import AgentHistoryList
# from browser_use import BrowserConfig, Browser
# from browser_use.browser.context import BrowserContext

# from browser_use.llm import LLMProvider

from browser_use import Agent
from browser_use.agent.views import AgentHistoryList
from browser_use import BrowserProfile, Browser


from browser_use.llm import (
    ChatAnthropic,
    ChatOpenAI,
    ChatGoogle,
    ChatOllama,
    ChatAzureOpenAI,
    ChatAWSBedrock,
)

from pathlib import Path

# Import our task storage abstraction
from task_storage import get_task_storage
from task_storage.base import DEFAULT_USER_ID


# Define task status enum
class TaskStatus(str, Enum):
    CREATED = "created"  # Task is initialized but not yet started
    RUNNING = "running"  # Task is currently executing
    FINISHED = "finished"  # Task has completed successfully
    STOPPED = "stopped"  # Task was manually stopped
    PAUSED = "paused"  # Task execution is temporarily paused
    FAILED = "failed"  # Task encountered an error and could not complete
    STOPPING = "stopping"  # Task is in the process of stopping (transitional state)


# Load environment variables from .env file
load_dotenv()

# Create media directory if it doesn't exist
MEDIA_DIR = Path("media")
MEDIA_DIR.mkdir(exist_ok=True)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("browser-use-bridge")

app = FastAPI(title="Browser Use Bridge API")

# Mount static files
app.mount("/media", StaticFiles(directory=str(MEDIA_DIR)), name="media")


# Custom JSON encoder for Enum serialization
class EnumJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Enum):
            return obj.value
        return super().default(obj)


# Configure FastAPI to use custom JSON serialization for responses
@app.middleware("http")
async def add_json_serialization(request: Request, call_next):
    response = await call_next(request)

    # Only attempt to modify JSON responses and check if body() method exists
    if response.headers.get("content-type") == "application/json" and hasattr(
        response, "body"
    ):
        try:
            content = await response.body()
            content_str = content.decode("utf-8")
            content_dict = json.loads(content_str)
            # Convert any Enum values to their string representation
            content_str = json.dumps(content_dict, cls=EnumJSONEncoder)
            response = Response(
                content=content_str,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type="application/json",
            )
        except Exception as e:
            logger.error(f"Error serializing JSON response: {str(e)}")

    return response


# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize task storage
task_storage = get_task_storage()


# Models
class TaskRequest(BaseModel):
    task: str
    ai_provider: Optional[str] = os.environ.get(
        "DEFAULT_AI_PROVIDER", "openai"
    )  # Default to OpenAI or env var
    save_browser_data: Optional[bool] = False  # Whether to save browser cookies
    headful: Optional[bool] = None  # Override BROWSER_USE_HEADFUL setting
    use_custom_chrome: Optional[bool] = (
        None  # Whether to use custom Chrome from env vars
    )


class TaskResponse(BaseModel):
    id: str
    status: str
    live_url: str


class TaskStatusResponse(BaseModel):
    status: str
    result: Optional[str] = None
    error: Optional[str] = None


# Dependency to get user_id from headers
async def get_user_id(x_user_id: Optional[str] = Header(None)) -> str:
    """Extract user ID from header or use default"""
    return x_user_id or DEFAULT_USER_ID


# Utility functions
def get_llm(ai_provider: str):
    """Get LLM based on provider"""
    if ai_provider == "anthropic":
        return ChatAnthropic(
            model=os.environ.get("ANTHROPIC_MODEL_ID", "claude-3-opus-20240229")
        )
    # elif ai_provider == "mistral":
    #     return LLMProvider.MISTRAL(
    #         model=os.environ.get("MISTRAL_MODEL_ID", "mistral-large-latest")
    #     )
    elif ai_provider == "google":
        return ChatGoogle(model=os.environ.get("GOOGLE_MODEL_ID", "gemini-1.5-pro"))
    elif ai_provider == "ollama":
        return ChatOllama(model=os.environ.get("OLLAMA_MODEL_ID", "llama3"))
    elif ai_provider == "azure":
        return ChatAzureOpenAI(
            model=os.environ.get("AZURE_MODEL_ID", "gpt-4o"),
            azure_deployment=os.environ.get("AZURE_DEPLOYMENT_NAME"),
            api_version=os.environ.get("AZURE_API_VERSION", "2023-05-15"),
            azure_endpoint=os.environ.get("AZURE_ENDPOINT"),
        )
    elif ai_provider == "bedrock":
        return ChatAWSBedrock(
            model=os.environ.get(
                "BEDROCK_MODEL_ID", "anthropic.claude-3-sonnet-20240229-v1:0"
            )
        )
    else:  # default to OpenAI
        base_url = os.environ.get("OPENAI_BASE_URL")
        model = os.environ.get("OPENAI_MODEL_ID", "gpt-4o")

        if base_url:
            return ChatOpenAI(model=model, base_url=base_url)
        else:
            return ChatOpenAI(model=model)


async def execute_task(
    task_id: str, instruction: str, ai_provider: str, user_id: str = DEFAULT_USER_ID
):
    """Execute browser task in background

    Chrome paths (CHROME_PATH and CHROME_USER_DATA) are only sourced from
    environment variables for security reasons.
    """
    # Initialize browser variable outside the try block
    browser = None
    try:
        # Update task status
        task_storage.update_task_status(task_id, TaskStatus.RUNNING, user_id)

        # Get LLM
        llm = get_llm(ai_provider)

        # Get task-specific browser configuration if available
        task = task_storage.get_task(task_id, user_id)
        task_browser_config = task.get("browser_config", {}) if task else {}

        # Create task media directory up front
        task_media_dir = MEDIA_DIR / task_id
        task_media_dir.mkdir(exist_ok=True, parents=True)
        logger.info(f"Created media directory for task {task_id}: {task_media_dir}")

        # Configure browser headless/headful mode (task setting overrides env var)
        task_headful = task_browser_config.get("headful")
        if task_headful is not None:
            headful = task_headful
        else:
            headful = os.environ.get("BROWSER_USE_HEADFUL", "false").lower() == "true"
            browser_config_args = {
                "headless": not headful,
            }

        # Get Chrome path and user data directory (task settings override env vars)
        use_custom_chrome = task_browser_config.get("use_custom_chrome")

        if use_custom_chrome is False:
            # Explicitly disabled custom Chrome for this task
            chrome_path = None
            chrome_user_data = None
        else:
            # Only use environment variables for Chrome paths
            chrome_path = os.environ.get("CHROME_PATH")
            chrome_user_data = os.environ.get("CHROME_USER_DATA")

        sensitive_data = {}
        for key, value in os.environ.items():
            if key.startswith("X_") and value:
                sensitive_data[key] = value

        # Configure agent options - start with basic configuration
        agent_kwargs = {
            "task": instruction,
            "llm": llm,
            "sensitive_data": sensitive_data,
        }

        # Only configure and include browser if we need a custom browser setup
        if not headful or chrome_path:
            extra_chromium_args = []
            # Configure browser
            browser_config_args = {
                "headless": not headful,
                "chrome_instance_path": None,
                "viewport": {"width": 1280, "height": 720},
                "window_size": {"width": 1280, "height": 720},
            }
            # For older Chrome versions
            extra_chromium_args += ["--headless=new"]
            logger.info(
                f"Task {task_id}: Browser config args: {browser_config_args.get('headless')}"
            )
            # Add Chrome executable path if provided
            if chrome_path and chrome_path.lower() != "false":
                browser_config_args["chrome_instance_path"] = chrome_path
                logger.info(
                    f"Task {task_id}: Using custom Chrome executable: {chrome_path}"
                )

            # Add Chrome user data directory if provided
            if chrome_user_data:
                extra_chromium_args += [f"--user-data-dir={chrome_user_data}"]
                logger.info(
                    f"Task {task_id}: Using Chrome user data directory: {chrome_user_data}"
                )

            browser_config = BrowserProfile(**browser_config_args)
            browser = Browser(browser_profile=browser_config)

            # Add browser to agent kwargs - let Agent manage its own browser session
            agent_kwargs["browser"] = browser

        logger.info(f"Agent kwargs: {agent_kwargs}")
        # Pass the browser to Agent
        agent = Agent(**agent_kwargs)

        # Store agent in task
        task_storage.set_task_agent(task_id, agent, user_id)

        # Run agent
        result = await agent.run(
            on_step_end=lambda agent_instance: asyncio.create_task(
                automated_screenshot(agent_instance, task_id, user_id)
            )
        )

        # Update finished timestamp and task status
        task_storage.mark_task_finished(task_id, user_id, TaskStatus.FINISHED)

        # Extract result
        if isinstance(result, AgentHistoryList):
            final_result = result.final_result()
            task_storage.set_task_output(task_id, final_result or "", user_id)
        else:
            task_storage.set_task_output(task_id, str(result), user_id)

        # Collect browser data if requested
        task = task_storage.get_task(task_id, user_id)
        if task and task.get("save_browser_data") and hasattr(agent, "browser_session"):
            try:
                cookies = []
                browser_session = None
                try:
                    browser_session = agent.browser_session
                except (AssertionError, AttributeError):
                    logger.warning(
                        f"BrowserSession is not set up for task {task_id}, skipping cookie collection."
                    )

                if browser_session:
                    if hasattr(browser_session, "get_cookies"):
                        cookies = await browser_session.get_cookies()
                    else:
                        logger.warning(
                            f"No known method to collect cookies for task {task_id}"
                        )
                else:
                    logger.warning(f"No browser_session available for task {task_id}")

                task_storage.update_task(
                    task_id, {"browser_data": {"cookies": cookies}}, user_id
                )
            except Exception as e:
                logger.error(f"Failed to collect browser data: {str(e)}")
                task_storage.update_task(
                    task_id, {"browser_data": {"cookies": [], "error": str(e)}}, user_id
                )

    except Exception as e:
        logger.exception(f"Error executing task {task_id}")
        task_storage.update_task_status(task_id, TaskStatus.FAILED, user_id)
        task_storage.set_task_error(task_id, str(e), user_id)
        task_storage.mark_task_finished(task_id, user_id, TaskStatus.FAILED)
    finally:
        # Always close the browser, regardless of success or failure
        if browser is not None:
            logger.info(f"Closing browser for task {task_id}")
            try:
                logger.info(
                    f"Taking final screenshot for task {task_id} after completion"
                )

                # Get agent to take screenshot
                agent = task_storage.get_task_agent(task_id, user_id)
                if agent and hasattr(agent, "browser_session"):
                    # Take final screenshot using our capture_screenshot function
                    await capture_screenshot(agent, task_id, user_id)
            except Exception as e:
                logger.error(f"Error taking final screenshot: {str(e)}")
            finally:
                if browser:
                    try:
                        await browser.close()
                    except Exception as e:
                        logger.error(
                            f"Error closing browser for task {task_id}: {str(e)}"
                        )


# API Routes
@app.post("/api/v1/run-task", response_model=TaskResponse)
async def run_task(request: TaskRequest, user_id: str = Depends(get_user_id)):
    """Start a browser automation task"""
    task_id = str(uuid.uuid4())
    now = datetime.now(UTC).isoformat() + "Z"

    # Generate live URL
    live_url = f"/live/{task_id}"

    # Initialize task record
    task_data = {
        "id": task_id,
        "task": request.task,
        "ai_provider": request.ai_provider,
        "status": TaskStatus.CREATED,
        "created_at": now,
        "finished_at": None,
        "output": None,  # Final result
        "error": None,
        "steps": [],  # Will store step information
        "agent": None,
        "save_browser_data": request.save_browser_data,
        "browser_data": None,  # Will store browser cookies if requested
        # Store browser configuration options
        "browser_config": {
            "headful": request.headful,
            "use_custom_chrome": request.use_custom_chrome,
        },
        "live_url": live_url,
    }

    # Store the task in storage
    task_storage.create_task(task_id, task_data, user_id)

    # Start task in background
    ai_provider = request.ai_provider or "openai"
    asyncio.create_task(execute_task(task_id, request.task, ai_provider, user_id))

    return TaskResponse(id=task_id, status=TaskStatus.CREATED, live_url=live_url)


async def automated_screenshot(agent, task_id, user_id=DEFAULT_USER_ID):
    # Only proceed if browser_session is set up
    if not hasattr(agent, "browser_session") or agent.browser_session is None:
        logger.warning(
            f"Agent browser_session not set up for task {task_id}, skipping screenshot."
        )
        return

    try:
        # (Optional) Log current and previous URLs for debugging
        current_url = "unknown"
        previous_url = None
        try:
            if hasattr(agent, "state") and hasattr(agent.state, "history"):
                history = agent.state.history
                visit_log = history.urls() if hasattr(history, "urls") else []
                if visit_log:
                    current_url = visit_log[-1]
                if len(visit_log) >= 2:
                    previous_url = visit_log[-2]
        except Exception as e:
            logger.warning(f"Couldn't get visit log from agent history: {str(e)}")

        logger.info(
            f"Agent was last on URL: {previous_url} and is now on {current_url}"
        )

        # Call the screenshot function (which will use browser_session)
        await capture_screenshot(agent, task_id, user_id)
    except Exception as e:
        logger.error(f"Error in automated_screenshot for task {task_id}: {str(e)}")


@app.get("/api/v1/task/{task_id}/status", response_model=TaskStatusResponse)
async def get_task_status(task_id: str, user_id: str = Depends(get_user_id)):
    """Get status of a task"""
    task = task_storage.get_task(task_id, user_id)

    agent = task_storage.get_task_agent(task_id, user_id)

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Only increment steps for running tasks
    if task["status"] == TaskStatus.RUNNING:
        # Initialize steps array if not present
        current_step = len(task.get("steps", [])) + 1

        # Add step info
        step_info = {
            "step": current_step,
            "timestamp": datetime.now(UTC).isoformat() + "Z",
            "next_goal": f"Progress check {current_step}",
            "evaluation_previous_goal": "In progress",
        }

        task_storage.add_task_step(task_id, step_info, user_id)
        logger.info(f"Added step {current_step} for task {task_id}")

    try:
        _ = agent.browser_session
        await capture_screenshot(agent, task_id, user_id)
        # await capture_screenshot(task_storage.get_task_agent(task_id, user_id), task_id, user_id)
    except (AssertionError, AttributeError):
        logger.info(
            f"BrowserSession not ready for task {task_id}, skipping screenshot."
        )

    return TaskStatusResponse(
        status=task["status"],
        result=task.get("output"),
        error=task.get("error"),
    )


async def capture_screenshot(agent_or_context, task_id, user_id=DEFAULT_USER_ID):
    logger.info(f"Capturing screenshot for task: {task_id}")

    # Handle different input types
    browser_session = None

    if hasattr(agent_or_context, "browser_session"):
        # This is an Agent instance
        browser_session = getattr(agent_or_context, "browser_session", None)
    elif hasattr(agent_or_context, "take_screenshot"):
        # This is already a browser session/context
        browser_session = agent_or_context
    else:
        logger.warning(f"Unable to determine browser session type for task {task_id}")
        return

    if browser_session is None:
        logger.warning(f"No browser session available for task {task_id}")
        return

    # Check for take_screenshot method
    if not hasattr(browser_session, "take_screenshot"):
        logger.error(
            f"browser_session does not have take_screenshot method for task {task_id}"
        )
        return

    try:
        # Try to get current page dimensions for debugging
        try:
            if hasattr(browser_session, "get_current_page"):
                page = await browser_session.get_current_page()
                if page and hasattr(page, "viewport_size"):
                    viewport_info = await page.viewport_size()
                    logger.info(f"Current viewport size: {viewport_info}")
        except Exception as viewport_e:
            logger.debug(f"Could not get viewport info: {viewport_e}")

        # Try taking screenshot with error handling for zero width issue
        logger.debug(f"Attempting to take screenshot for task {task_id}")
        try:
            screenshot_b64 = await browser_session.take_screenshot(full_page=True)
            logger.debug(f"Screenshot method returned type: {type(screenshot_b64)}")

            # Quick validation of returned data
            if screenshot_b64 and isinstance(screenshot_b64, str):
                if len(screenshot_b64) < 100:
                    logger.warning(
                        f"Screenshot data suspiciously short: {len(screenshot_b64)} chars"
                    )
                    logger.warning(f"Data: {screenshot_b64}")

                    # Try alternative screenshot method if available
                    logger.info(
                        "Attempting alternative screenshot method without full_page"
                    )
                    try:
                        screenshot_b64 = await browser_session.take_screenshot(
                            full_page=False
                        )
                        logger.debug(
                            f"Alternative screenshot length: {len(screenshot_b64) if screenshot_b64 else 0}"
                        )
                    except Exception as alt_error:
                        logger.error(f"Alternative screenshot also failed: {alt_error}")

        except Exception as screenshot_error:
            logger.error(
                f"Browser session screenshot method failed: {screenshot_error}"
            )
            return

        if not screenshot_b64:
            logger.warning("Screenshot unavailable - empty response from browser")
            return

        # Save screenshot with appropriate file handling
        task_media_dir = MEDIA_DIR / task_id
        task_media_dir.mkdir(exist_ok=True, parents=True)
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        task = task_storage.get_task(task_id, user_id)
        if task and "steps" in task and task["steps"]:
            current_step = task["steps"][-1]["step"] - 1
        else:
            current_step = "initial"

        if task and task["status"] == TaskStatus.FINISHED:
            screenshot_filename = f"final-{timestamp}.png"
        elif task and task["status"] == TaskStatus.RUNNING:
            screenshot_filename = f"status-step-{current_step}-{timestamp}.png"
        else:
            task_status = task["status"] if task else "unknown"
            screenshot_filename = f"status-{task_status}-{timestamp}.png"

        screenshot_path = task_media_dir / screenshot_filename

        try:
            # Debug: log info about the base64 data
            logger.debug(
                f"Screenshot base64 length: {len(screenshot_b64) if screenshot_b64 else 0}"
            )
            logger.debug(
                f"Screenshot base64 first 50 chars: {screenshot_b64[:50] if screenshot_b64 else 'None'}"
            )

            # Validate base64 data before decoding
            if not screenshot_b64:
                logger.error("Empty screenshot base64 data")
                return

            # Handle different data types from take_screenshot
            if isinstance(screenshot_b64, bytes):
                logger.debug(
                    "Screenshot returned as bytes - using directly as image data"
                )
                image_data = screenshot_b64
                # Skip base64 decoding since we already have bytes
            elif isinstance(screenshot_b64, str):
                logger.debug("Screenshot returned as base64 string - decoding")
                # Continue with base64 decoding process below
                screenshot_is_b64_string = True
            else:
                logger.error(
                    f"Screenshot data is unexpected type: {type(screenshot_b64)}"
                )
                return

            # Process screenshot data based on type
            if isinstance(screenshot_b64, str):
                # Check for known corrupted pattern in base64 strings
                try:
                    temp_decode = base64.b64decode(screenshot_b64[:20])
                    if temp_decode.startswith(b"<\xd1\x88\x1c4U"):
                        logger.error(
                            "Detected corrupted screenshot pattern - screenshot capture is failing"
                        )
                        return
                except Exception:
                    pass  # Continue with normal processing if quick check fails

                # Clean base64 data (remove data URL prefix if present)
                if screenshot_b64.startswith("data:image/"):
                    # Remove data URL prefix like "data:image/png;base64,"
                    screenshot_b64 = screenshot_b64.split(",", 1)[1]
                    logger.debug("Removed data URL prefix from screenshot")

                # Validate base64 format
                import string

                valid_b64_chars = string.ascii_letters + string.digits + "+/="
                if not all(c in valid_b64_chars for c in screenshot_b64):
                    logger.error("Screenshot data contains invalid base64 characters")
                    logger.debug(
                        f"Invalid chars found in first 200 chars: {[c for c in screenshot_b64[:200] if c not in valid_b64_chars]}"
                    )
                    return

                image_data = base64.b64decode(screenshot_b64)
                logger.debug(f"Decoded image data length: {len(image_data)} bytes")
            # If image_data was already set above (bytes case), we skip base64 decoding

            # Ensure we have image_data (should be set in either case above)
            if "image_data" not in locals():
                logger.error("Image data not set - this shouldn't happen")
                return

            logger.debug(f"Final image data length: {len(image_data)} bytes")

            # Validate PNG header
            png_signature = b"\x89PNG\r\n\x1a\n"
            if not image_data.startswith(png_signature):
                logger.warning("Image data does not have valid PNG signature")
                logger.debug(
                    f"Image data starts with: {image_data[:20].hex() if len(image_data) >= 20 else 'too short'}"
                )

                # Don't save invalid image data
                logger.error(
                    "Refusing to save invalid image data - screenshot capture appears to be broken"
                )
                return

            with open(screenshot_path, "wb") as f:
                f.write(image_data)

            if screenshot_path.exists() and screenshot_path.stat().st_size > 0:
                logger.info(
                    f"Screenshot saved: {screenshot_path} ({screenshot_path.stat().st_size} bytes)"
                )
                screenshot_url = f"/media/{task_id}/{screenshot_filename}"
                media_entry = {
                    "url": screenshot_url,
                    "type": "screenshot",
                    "filename": screenshot_filename,
                    "created_at": datetime.now(UTC).isoformat() + "Z",
                }
                task_storage.add_task_media(task_id, media_entry, user_id)
            else:
                logger.error(f"Screenshot file not created or empty: {screenshot_path}")
        except Exception as e:
            logger.error(f"Error saving screenshot: {str(e)}")

    except Exception as e:
        error_str = str(e)
        logger.error(f"Error taking screenshot: {error_str}")

        # Try fallback screenshot without full_page if we get a width error
        if "0 width" in error_str or "width" in error_str.lower():
            logger.info(
                f"Attempting fallback screenshot without full_page for task {task_id}"
            )
            try:
                screenshot_b64 = await browser_session.take_screenshot(full_page=False)
                if screenshot_b64:
                    logger.info("Fallback screenshot successful")
                    # Save the fallback screenshot using the same logic
                    task_media_dir = MEDIA_DIR / task_id
                    task_media_dir.mkdir(exist_ok=True, parents=True)
                    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
                    task = task_storage.get_task(task_id, user_id)
                    if task and "steps" in task and task["steps"]:
                        current_step = task["steps"][-1]["step"] - 1
                    else:
                        current_step = "initial"

                    if task and task["status"] == TaskStatus.FINISHED:
                        screenshot_filename = f"final-fallback-{timestamp}.png"
                    elif task and task["status"] == TaskStatus.RUNNING:
                        screenshot_filename = (
                            f"status-step-{current_step}-fallback-{timestamp}.png"
                        )
                    else:
                        task_status = task["status"] if task else "unknown"
                        screenshot_filename = (
                            f"status-{task_status}-fallback-{timestamp}.png"
                        )

                    screenshot_path = task_media_dir / screenshot_filename

                    try:
                        # Debug fallback screenshot data
                        logger.debug(
                            f"Fallback screenshot data type: {type(screenshot_b64)}, length: {len(screenshot_b64) if screenshot_b64 else 0}"
                        )

                        # Handle fallback screenshot data based on type
                        if isinstance(screenshot_b64, bytes):
                            logger.debug(
                                "Fallback screenshot returned as bytes - using directly"
                            )
                            image_data = screenshot_b64
                        elif isinstance(screenshot_b64, str):
                            # Clean base64 data (remove data URL prefix if present)
                            if screenshot_b64.startswith("data:image/"):
                                screenshot_b64 = screenshot_b64.split(",", 1)[1]
                                logger.debug(
                                    "Removed data URL prefix from fallback screenshot"
                                )
                            image_data = base64.b64decode(screenshot_b64)
                        else:
                            logger.error(
                                f"Fallback screenshot has unexpected type: {type(screenshot_b64)}"
                            )
                            return

                        logger.debug(
                            f"Fallback final image data length: {len(image_data)} bytes"
                        )

                        with open(screenshot_path, "wb") as f:
                            f.write(image_data)

                        if (
                            screenshot_path.exists()
                            and screenshot_path.stat().st_size > 0
                        ):
                            logger.info(f"Fallback screenshot saved: {screenshot_path}")
                            screenshot_url = f"/media/{task_id}/{screenshot_filename}"
                            media_entry = {
                                "url": screenshot_url,
                                "type": "screenshot",
                                "filename": screenshot_filename,
                                "created_at": datetime.now(UTC).isoformat() + "Z",
                            }
                            task_storage.add_task_media(task_id, media_entry, user_id)
                    except Exception as fallback_save_e:
                        logger.error(
                            f"Error saving fallback screenshot: {fallback_save_e}"
                        )
            except Exception as fallback_e:
                logger.error(f"Fallback screenshot also failed: {fallback_e}")


@app.get("/api/v1/task/{task_id}", response_model=dict)
async def get_task(task_id: str, user_id: str = Depends(get_user_id)):
    """Get full task details"""
    task = task_storage.get_task(task_id, user_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    return task


@app.put("/api/v1/stop-task/{task_id}")
async def stop_task(task_id: str, user_id: str = Depends(get_user_id)):
    """Stop a running task"""
    task = task_storage.get_task(task_id, user_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if task["status"] in [
        TaskStatus.FINISHED,
        TaskStatus.FAILED,
        TaskStatus.STOPPED,
    ]:
        return {"message": f"Task already in terminal state: {task['status']}"}

    # Get agent
    agent = task_storage.get_task_agent(task_id, user_id)
    if agent:
        # Call agent's stop method
        agent.stop()
        task_storage.update_task_status(task_id, TaskStatus.STOPPING, user_id)
        return {"message": "Task stopping"}
    else:
        task_storage.update_task_status(task_id, TaskStatus.STOPPED, user_id)
        task_storage.mark_task_finished(task_id, user_id, TaskStatus.STOPPED)
        return {"message": "Task stopped (no agent found)"}


@app.put("/api/v1/pause-task/{task_id}")
async def pause_task(task_id: str, user_id: str = Depends(get_user_id)):
    """Pause a running task"""
    task = task_storage.get_task(task_id, user_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if task["status"] != TaskStatus.RUNNING:
        return {"message": f"Task not running: {task['status']}"}

    # Get agent
    agent = task_storage.get_task_agent(task_id, user_id)
    if agent:
        # Call agent's pause method
        agent.pause()
        task_storage.update_task_status(task_id, TaskStatus.PAUSED, user_id)
        return {"message": "Task paused"}
    else:
        return {"message": "Task could not be paused (no agent found)"}


@app.put("/api/v1/resume-task/{task_id}")
async def resume_task(task_id: str, user_id: str = Depends(get_user_id)):
    """Resume a paused task"""
    task = task_storage.get_task(task_id, user_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if task["status"] != TaskStatus.PAUSED:
        return {"message": f"Task not paused: {task['status']}"}

    # Get agent
    agent = task_storage.get_task_agent(task_id, user_id)
    if agent:
        # Call agent's resume method
        agent.resume()
        task_storage.update_task_status(task_id, TaskStatus.RUNNING, user_id)
        return {"message": "Task resumed"}
    else:
        return {"message": "Task could not be resumed (no agent found)"}


@app.get("/api/v1/list-tasks")
async def list_tasks(
    user_id: str = Depends(get_user_id),
    page: int = Query(1, ge=1),
    per_page: int = Query(100, ge=1, le=1000),
):
    """List all tasks"""
    return task_storage.list_tasks(user_id, page, per_page)


@app.get("/live/{task_id}", response_class=HTMLResponse)
async def live_view(task_id: str, user_id: str = Depends(get_user_id)):
    """Get a live view of a task that can be embedded in an iframe"""
    task = task_storage.get_task(task_id, user_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Browser Use Task {task_id}</title>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {{ font-family: Arial, sans-serif; margin: 0; padding: 20px; }}
            .container {{ max-width: 1200px; margin: 0 auto; }}
            .status {{ padding: 10px; border-radius: 4px; margin-bottom: 20px; }}
            .{TaskStatus.RUNNING} {{ background-color: #e3f2fd; }}
            .{TaskStatus.FINISHED} {{ background-color: #e8f5e9; }}
            .{TaskStatus.FAILED} {{ background-color: #ffebee; }}
            .{TaskStatus.PAUSED} {{ background-color: #fff8e1; }}
            .{TaskStatus.STOPPED} {{ background-color: #eeeeee; }}
            .{TaskStatus.CREATED} {{ background-color: #f3e5f5; }}
            .{TaskStatus.STOPPING} {{ background-color: #fce4ec; }}
            .controls {{ margin-bottom: 20px; }}
            button {{ padding: 8px 16px; margin-right: 10px; cursor: pointer; }}
            pre {{ background-color: #f5f5f5; padding: 15px; border-radius: 4px; overflow: auto; }}
            .step {{ margin-bottom: 10px; padding: 10px; border: 1px solid #ddd; border-radius: 4px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Browser Use Task</h1>
            <div id="status" class="status">Loading...</div>
            
            <div class="controls">
                <button id="pauseBtn">Pause</button>
                <button id="resumeBtn">Resume</button>
                <button id="stopBtn">Stop</button>
            </div>
            
            <h2>Result</h2>
            <pre id="result">Loading...</pre>
            
            <h2>Steps</h2>
            <div id="steps">Loading...</div>
            
            <script>
                const taskId = '{task_id}';
                const FINISHED = '{TaskStatus.FINISHED}';
                const FAILED = '{TaskStatus.FAILED}';
                const STOPPED = '{TaskStatus.STOPPED}';
                const userId = '{user_id}';
                
                // Set user ID in request headers if available
                const headers = {{}};
                if (userId && userId !== 'default') {{
                    headers['X-User-ID'] = userId;
                }}
                
                // Update status function
                function updateStatus() {{
                    fetch(`/api/v1/task/${{taskId}}/status`, {{ headers }})
                        .then(response => response.json())
                        .then(data => {{
                            // Update status element
                            const statusEl = document.getElementById('status');
                            statusEl.textContent = `Status: ${{data.status}}`;
                            statusEl.className = `status ${{data.status}}`;
                            
                            // Update result if available
                            if (data.result) {{
                                document.getElementById('result').textContent = data.result;
                            }} else if (data.error) {{
                                document.getElementById('result').textContent = `Error: ${{data.error}}`;
                            }}
                            
                            // Continue polling if not in terminal state
                            if (![FINISHED, FAILED, STOPPED].includes(data.status)) {{
                                setTimeout(updateStatus, 2000);
                            }}
                        }})
                        .catch(error => {{
                            console.error('Error fetching status:', error);
                            setTimeout(updateStatus, 5000);
                        }});
                        
                    // Also fetch full task to get steps
                    fetch(`/api/v1/task/${{taskId}}`, {{ headers }})
                        .then(response => response.json())
                        .then(data => {{
                            if (data.steps && data.steps.length > 0) {{
                                const stepsHtml = data.steps.map(step => `
                                    <div class="step">
                                        <strong>Step ${{step.step}}</strong>
                                        <p>Next Goal: ${{step.next_goal || 'N/A'}}</p>
                                        <p>Evaluation: ${{step.evaluation_previous_goal || 'N/A'}}</p>
                                    </div>
                                `).join('');
                                document.getElementById('steps').innerHTML = stepsHtml;
                            }} else {{
                                document.getElementById('steps').textContent = 'No steps recorded yet.';
                            }}
                        }})
                        .catch(error => {{
                            console.error('Error fetching task details:', error);
                        }});
                }}
                
                // Setup control buttons
                document.getElementById('pauseBtn').addEventListener('click', () => {{
                    fetch(`/api/v1/pause-task/${{taskId}}`, {{ 
                        method: 'PUT',
                        headers
                    }})
                        .then(response => response.json())
                        .then(data => alert(data.message))
                        .catch(error => console.error('Error pausing task:', error));
                }});
                
                document.getElementById('resumeBtn').addEventListener('click', () => {{
                    fetch(`/api/v1/resume-task/${{taskId}}`, {{ 
                        method: 'PUT',
                        headers
                    }})
                        .then(response => response.json())
                        .then(data => alert(data.message))
                        .catch(error => console.error('Error resuming task:', error));
                }});
                
                document.getElementById('stopBtn').addEventListener('click', () => {{
                    if (confirm('Are you sure you want to stop this task? This action cannot be undone.')) {{
                        fetch(`/api/v1/stop-task/${{taskId}}`, {{ 
                            method: 'PUT',
                            headers
                        }})
                            .then(response => response.json())
                            .then(data => alert(data.message))
                            .catch(error => console.error('Error stopping task:', error));
                    }}
                }});
                
                // Start status updates
                updateStatus();
                
                // Refresh every 5 seconds
                setInterval(updateStatus, 5000);
            </script>
        </div>
    </body>
    </html>
    """

    return HTMLResponse(content=html_content)


@app.get("/api/v1/ping")
async def ping():
    """Health check endpoint"""
    return {"status": "success", "message": "API is running"}


@app.get("/api/v1/browser-config")
async def browser_config():
    """Get current browser configuration

    Note: Chrome paths (CHROME_PATH and CHROME_USER_DATA) can only be set via
    environment variables for security reasons and cannot be overridden in task requests.
    """
    headful = os.environ.get("BROWSER_USE_HEADFUL", "false").lower() == "true"
    chrome_path = os.environ.get("CHROME_PATH", None)
    chrome_user_data = os.environ.get("CHROME_USER_DATA", None)

    return {
        "headful": headful,
        "headless": not headful,
        "chrome_path": chrome_path,
        "chrome_user_data": chrome_user_data,
        "using_custom_chrome": chrome_path is not None,
        "using_user_data": chrome_user_data is not None,
    }


@app.get("/api/v1/task/{task_id}/media")
async def get_task_media(
    task_id: str, user_id: str = Depends(get_user_id), type: Optional[str] = None
):
    """Returns links to any recordings or media generated during task execution"""
    task = task_storage.get_task(task_id, user_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Check if task is completed
    if task["status"] not in [
        TaskStatus.FINISHED,
        TaskStatus.FAILED,
        TaskStatus.STOPPED,
    ]:
        raise HTTPException(
            status_code=400, detail="Media only available for completed tasks"
        )

    # Check if the media directory exists and contains files
    task_media_dir = MEDIA_DIR / task_id
    media_files = []

    if task_media_dir.exists():
        media_files = list(task_media_dir.glob("*"))
        logger.info(
            f"Media directory for task {task_id} contains {len(media_files)} files: {[f.name for f in media_files]}"
        )
    else:
        logger.warning(f"Media directory for task {task_id} does not exist")

    # If we have files but no media entries, create them now
    if media_files and (not task.get("media") or len(task.get("media", [])) == 0):
        for file_path in media_files:
            if file_path.suffix.lower() in [".png", ".jpg", ".jpeg"]:
                file_url = f"/media/{task_id}/{file_path.name}"
                media_entry = {
                    "url": file_url,
                    "type": "screenshot",
                    "filename": file_path.name,
                }
                task_storage.add_task_media(task_id, media_entry, user_id)

    # Get updated task with media
    task = task_storage.get_task(task_id, user_id)
    if task is not None:
        media_list = task.get("media", [])
    else:
        media_list = []

    # Filter by type if specified
    if type and isinstance(media_list, list):
        if all(isinstance(item, dict) for item in media_list):
            # Dictionary format with type info
            media_list = [item for item in media_list if item.get("type") == type]
            recordings = [item["url"] for item in media_list]
        else:
            # Just URLs without type info
            recordings = []
            logger.warning(
                f"Media list for task {task_id} doesn't contain type information"
            )
    else:
        # Return all media
        if isinstance(media_list, list):
            if media_list and all(isinstance(item, dict) for item in media_list):
                recordings = [item["url"] for item in media_list]
            else:
                recordings = media_list
        else:
            recordings = []

    logger.info(f"Returning {len(recordings)} media items for task {task_id}")
    return {"recordings": recordings}


@app.get("/api/v1/task/{task_id}/media/list")
async def list_task_media(
    task_id: str, user_id: str = Depends(get_user_id), type: Optional[str] = None
):
    """Returns detailed information about media files associated with a task"""
    # Check if the media directory exists
    task_media_dir = MEDIA_DIR / task_id

    if not task_storage.task_exists(task_id, user_id):
        raise HTTPException(status_code=404, detail="Task not found")

    if not task_media_dir.exists():
        return {
            "media": [],
            "count": 0,
            "message": f"No media found for task {task_id}",
        }

    media_info = []

    media_files = list(task_media_dir.glob("*"))
    logger.info(f"Found {len(media_files)} media files for task {task_id}")

    for file_path in media_files:
        # Determine media type based on file extension
        file_type = "unknown"
        if file_path.suffix.lower() in [".png", ".jpg", ".jpeg"]:
            file_type = "screenshot"
        elif file_path.suffix.lower() in [".mp4", ".webm"]:
            file_type = "recording"

        # Get file stats
        stats = file_path.stat()

        file_info = {
            "filename": file_path.name,
            "type": file_type,
            "size_bytes": stats.st_size,
            "created_at": datetime.fromtimestamp(stats.st_ctime).isoformat(),
            "url": f"/media/{task_id}/{file_path.name}",
        }
        media_info.append(file_info)

    # Filter by type if specified
    if type:
        media_info = [item for item in media_info if item["type"] == type]

    logger.info(f"Returning {len(media_info)} media items for task {task_id}")
    return {"media": media_info, "count": len(media_info)}


@app.get("/api/v1/media/{task_id}/{filename}")
async def get_media_file(
    task_id: str,
    filename: str,
    download: bool = Query(
        False, description="Force download instead of viewing in browser"
    ),
):
    """Serve a media file with options for viewing or downloading"""
    # Construct the file path
    file_path = MEDIA_DIR / task_id / filename

    # Check if file exists
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Media file not found")

    # Determine content type
    content_type, _ = mimetypes.guess_type(file_path)

    # Set headers based on download preference
    headers = {}
    if download:
        headers["Content-Disposition"] = f'attachment; filename="{filename}"'
    else:
        headers["Content-Disposition"] = f'inline; filename="{filename}"'

    # Return the file with appropriate headers
    return FileResponse(
        path=file_path, media_type=content_type, headers=headers, filename=filename
    )


@app.get("/api/v1/test-screenshot")
async def test_screenshot(ai_provider: str = "google"):
    """Test endpoint to verify screenshot functionality using Agent like the main task flow"""
    logger.info(f"Testing screenshot functionality with provider: {ai_provider}")

    agent = None
    browser = None

    try:
        # Get LLM provider (simplified version)
        if ai_provider.lower() == "google":
            llm = ChatGoogle(model="gemini-1.5-flash")
        elif ai_provider.lower() == "openai":
            llm = ChatOpenAI(model="gpt-4o")
        else:
            llm = ChatGoogle(model="gemini-1.5-flash")

        # Configure browser same as main code
        headful = os.environ.get("BROWSER_USE_HEADFUL", "false").lower() == "true"
        browser_config_args = {
            "headless": not headful,
            "chrome_instance_path": None,
            "viewport": {"width": 1280, "height": 720},
            "window_size": {"width": 1280, "height": 720},
        }

        chrome_path = os.environ.get("CHROME_PATH")
        if chrome_path:
            browser_config_args["chrome_instance_path"] = chrome_path

        logger.info(f"Creating browser with config: {browser_config_args}")
        browser_config = BrowserProfile(**browser_config_args)
        browser = Browser(browser_profile=browser_config)

        # Create Agent with browser (like main code)
        task_instruction = "Navigate to example.com and take a screenshot"

        agent = Agent(
            task_instruction,
            llm=llm,
            browser=browser,
        )

        # Initialize agent browser session first (this might be needed)
        logger.info("Checking agent browser session initialization")
        logger.info(f"Agent has browser_session: {hasattr(agent, 'browser_session')}")

        # Try to access browser_session to trigger initialization
        try:
            if hasattr(agent, "browser_session"):
                logger.info(f"browser_session type: {type(agent.browser_session)}")
                logger.info(f"browser_session is None: {agent.browser_session is None}")

            # Navigate to test page
            logger.info("Navigating to example.com for test")
            await agent.browser_session.navigate_to("https://example.com")

            logger.info("Navigation completed, browser_session should be ready now")

            # Test screenshot using our capture_screenshot function
            logger.info("Testing screenshot capture")
            test_task_id = "screenshot-test"

            # First try direct screenshot
            logger.info("Trying direct screenshot on browser_session")
            try:
                direct_screenshot = await agent.browser_session.take_screenshot(
                    full_page=True
                )
                logger.info(f"Direct screenshot result type: {type(direct_screenshot)}")
                logger.info(
                    f"Direct screenshot length: {len(direct_screenshot) if direct_screenshot else 0}"
                )
                if direct_screenshot:
                    logger.info(
                        f"Direct screenshot first 100 chars: {direct_screenshot[:100]}"
                    )
            except Exception as direct_error:
                logger.error(f"Direct screenshot failed: {direct_error}")

            # Then try our capture_screenshot function
            await capture_screenshot(agent, test_task_id, "test-user")

        except Exception as nav_error:
            logger.error(f"Error during navigation or screenshot: {nav_error}")
            return {"error": f"Navigation/screenshot error: {nav_error}"}

        # Check if screenshot was created
        test_media_dir = MEDIA_DIR / test_task_id
        logger.info(f"Checking for media directory: {test_media_dir}")
        logger.info(f"Media directory exists: {test_media_dir.exists()}")
        if test_media_dir.exists():
            screenshots = list(test_media_dir.glob("*.png"))
            if screenshots:
                latest_screenshot = max(screenshots, key=lambda x: x.stat().st_mtime)
                file_size = latest_screenshot.stat().st_size

                logger.info(
                    f"Test screenshot found: {latest_screenshot} ({file_size} bytes)"
                )

                return {
                    "success": True,
                    "message": "Screenshot test completed",
                    "file_size": file_size,
                    "file_path": str(latest_screenshot),
                    "url": f"/media/{test_task_id}/{latest_screenshot.name}",
                    "working_method": "agent.browser_session.take_screenshot via capture_screenshot",
                }
            else:
                return {"error": "No screenshots found after test"}
        else:
            return {"error": "Test media directory not created"}

    except Exception as e:
        logger.exception("Error in screenshot test")
        return {"error": f"Test failed: {str(e)}"}
    finally:
        # Clean up resources
        if browser:
            try:
                await browser.stop()  # Use stop instead of close for Browser
            except Exception as e:
                logger.warning(f"Error stopping browser: {str(e)}")


# Run server if executed directly
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
