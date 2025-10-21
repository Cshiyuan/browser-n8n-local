"""API routes for browser automation tasks"""

import asyncio
import mimetypes
import os
import uuid
from datetime import datetime, UTC
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.responses import HTMLResponse, FileResponse

from app.models import TaskRequest, TaskResponse, TaskStatusResponse
from app.dependencies import get_user_id
from task.constants import TaskStatus, MEDIA_DIR, logger
from task.executor import execute_task
from task.screenshot import capture_screenshot
from task.llm import get_llm
from task.browser_config import configure_browser_profile
from task.agent import create_agent_config
from task.utils import get_sensitive_data
from browser_use import Agent
from browser_use.llm import ChatGoogle, ChatOpenAI
from task.storage import get_task_storage

# Initialize task storage
task_storage = get_task_storage()

# Create API router
router = APIRouter()


def _validate_task_and_get_agent(task_id: str, user_id: str, expected_status: TaskStatus):
    """Helper function to validate task and get agent"""
    task = task_storage.get_task(task_id, user_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if task["status"] != expected_status:
        return None, {"message": f"Task status is {task['status']}, expected {expected_status}"}

    agent = task_storage.get_task_agent(task_id, user_id)
    return agent, task


@router.post("/api/v1/run-task", response_model=TaskResponse)
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
        # Agent configuration options
        "use_vision": request.use_vision,
        "output_model_schema": request.output_model_schema,
        "live_url": live_url,
    }

    # Store the task in storage
    task_storage.create_task(task_id, task_data, user_id)

    # Start task in background
    ai_provider = request.ai_provider or "openai"
    asyncio.create_task(execute_task(task_id, request.task, ai_provider, user_id, task_storage))

    return TaskResponse(id=task_id, status=TaskStatus.CREATED, live_url=live_url)


@router.get("/api/v1/task/{task_id}/status", response_model=TaskStatusResponse)
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
        await capture_screenshot(agent, task_id, user_id, task_storage)
    except (AssertionError, AttributeError):
        logger.info(
            f"BrowserSession not ready for task {task_id}, skipping screenshot."
        )

    return TaskStatusResponse(
        status=task["status"],
        result=task.get("output"),
        error=task.get("error"),
    )


@router.get("/api/v1/task/{task_id}", response_model=dict)
async def get_task(task_id: str, user_id: str = Depends(get_user_id)):
    """Get full task details"""
    task = task_storage.get_task(task_id, user_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    return task


@router.put("/api/v1/stop-task/{task_id}")
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


@router.put("/api/v1/pause-task/{task_id}")
async def pause_task(task_id: str, user_id: str = Depends(get_user_id)):
    """Pause a running task"""
    agent, result = _validate_task_and_get_agent(task_id, user_id, TaskStatus.RUNNING)

    # If result is a dict, it means status check failed
    if isinstance(result, dict):
        return result

    if agent:
        agent.pause()
        task_storage.update_task_status(task_id, TaskStatus.PAUSED, user_id)
        return {"message": "Task paused"}
    else:
        return {"message": "Task could not be paused (no agent found)"}


@router.put("/api/v1/resume-task/{task_id}")
async def resume_task(task_id: str, user_id: str = Depends(get_user_id)):
    """Resume a paused task"""
    agent, result = _validate_task_and_get_agent(task_id, user_id, TaskStatus.PAUSED)

    # If result is a dict, it means status check failed
    if isinstance(result, dict):
        return result

    if agent:
        agent.resume()
        task_storage.update_task_status(task_id, TaskStatus.RUNNING, user_id)
        return {"message": "Task resumed"}
    else:
        return {"message": "Task could not be resumed (no agent found)"}


@router.get("/api/v1/list-tasks")
async def list_tasks(
    user_id: str = Depends(get_user_id),
    page: int = Query(1, ge=1),
    per_page: int = Query(100, ge=1, le=1000),
):
    """List all tasks"""
    return task_storage.list_tasks(user_id, page, per_page)


@router.get("/live/{task_id}", response_class=HTMLResponse)
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


@router.get("/api/v1/ping")
async def ping():
    """Health check endpoint"""
    return {"status": "success", "message": "API is running"}


@router.get("/api/v1/browser-config")
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


@router.get("/api/v1/task/{task_id}/media")
async def get_task_media(
    task_id: str, user_id: str = Depends(get_user_id), media_type: Optional[str] = None
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
    if media_type and isinstance(media_list, list):
        if all(isinstance(item, dict) for item in media_list):
            # Dictionary format with type info
            media_list = [item for item in media_list if item.get("type") == media_type]
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


@router.get("/api/v1/task/{task_id}/media/list")
async def list_task_media(
    task_id: str, user_id: str = Depends(get_user_id), media_type: Optional[str] = None
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
    if media_type:
        media_info = [item for item in media_info if item["type"] == media_type]

    logger.info(f"Returning {len(media_info)} media items for task {task_id}")
    return {"media": media_info, "count": len(media_info)}


@router.get("/api/v1/media/{task_id}/{filename}")
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


@router.get("/api/v1/test-screenshot")
async def test_screenshot(ai_provider: str = "google"):
    """Test endpoint to verify screenshot functionality using refactored utility functions"""
    logger.info(f"Testing screenshot functionality with provider: {ai_provider}")

    browser = None
    try:
        # Use our get_llm utility (fallback for test providers)
        if ai_provider.lower() == "google":
            llm = ChatGoogle(model="gemini-1.5-flash")
        elif ai_provider.lower() == "openai":
            llm = ChatOpenAI(model="gpt-4o")
        else:
            # Use our standard get_llm function for consistency
            llm = get_llm(ai_provider)

        # Use our configure_browser_profile utility
        test_browser_config = {"headful": False}  # Force headless for testing
        browserSession, browser_info = configure_browser_profile(test_browser_config)
        logger.info(f"Test browser configuration: {browser_info}")

        # Use our create_agent_config utility
        task_instruction = "Navigate to example.com and take a screenshot"
        sensitive_data = get_sensitive_data()
        agent_config = create_agent_config(
            task_instruction, llm, sensitive_data, browserSession
        )

        agent = Agent(**agent_config)

        # Navigate to test page
        logger.info("Navigating to example.com for test")
        await agent.browser_session.navigate_to("https://example.com")

        # Test our capture_screenshot function
        test_task_id = "screenshot-test"
        logger.info("Testing screenshot capture with utility function")
        await capture_screenshot(agent, test_task_id, "test-user", task_storage)

        # Check results using the same logic but simplified
        test_media_dir = MEDIA_DIR / test_task_id
        if test_media_dir.exists():
            screenshots = list(test_media_dir.glob("*.png"))
            if screenshots:
                latest_screenshot = max(screenshots, key=lambda x: x.stat().st_mtime)
                file_size = latest_screenshot.stat().st_size

                return {
                    "success": True,
                    "message": "Screenshot test completed using refactored utilities",
                    "file_size": file_size,
                    "file_path": str(latest_screenshot),
                    "url": f"/media/{test_task_id}/{latest_screenshot.name}",
                    "utilities_used": [
                        "configure_browser_profile",
                        "create_agent_config",
                        "capture_screenshot",
                    ],
                }
            else:
                return {"error": "No screenshots found after test"}
        else:
            return {"error": "Test media directory not created"}

    except Exception as e:
        logger.exception("Error in screenshot test")
        return {"error": f"Test failed: {str(e)}"}
    finally:
        # Cleanup browser
        if browser:
            try:
                await browser.close()
            except Exception as e:
                logger.error(f"Error closing test browser: {str(e)}")
