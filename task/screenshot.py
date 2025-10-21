"""Screenshot processing and validation for task execution"""

import base64
from datetime import datetime, UTC
from typing import Optional

from task.constants import MEDIA_DIR, TaskStatus, logger
from task.storage.base import DEFAULT_USER_ID


def process_screenshot_data(screenshot_data) -> Optional[bytes]:
    """Convert screenshot data from various formats to bytes"""
    if not screenshot_data:
        logger.warning("No screenshot data provided")
        return None

    if isinstance(screenshot_data, bytes):
        image_data = screenshot_data
    elif isinstance(screenshot_data, str):
        # Clean base64 data (remove data URL prefix if present)
        if screenshot_data.startswith("data:image/"):
            screenshot_data = screenshot_data.split(",", 1)[1]
        try:
            image_data = base64.b64decode(screenshot_data)
        except Exception as decode_error:
            logger.error(f"Failed to decode screenshot data: {decode_error}")
            return None
    else:
        logger.error(f"Unexpected screenshot data type: {type(screenshot_data)}")
        return None

    return image_data


def check_duplicate_screenshot(image_data: bytes, task_id: str) -> bool:
    """Check if screenshot is a duplicate based on size tolerance"""
    if not image_data:
        return False

    current_size = len(image_data)
    logger.debug(f"Current screenshot size: {current_size} bytes")

    # Check existing screenshots in the task media directory with size tolerance
    task_media_dir = MEDIA_DIR / task_id
    if task_media_dir.exists():
        existing_screenshots = list(task_media_dir.glob("*.png"))
        for existing_file in existing_screenshots:
            try:
                existing_size = existing_file.stat().st_size

                # Calculate size difference tolerance (0.5% of the larger size, min 1KB, max 10KB)
                larger_size = max(existing_size, current_size)
                size_tolerance = max(1024, min(10240, int(larger_size * 0.005)))
                size_diff = abs(existing_size - current_size)

                if size_diff <= size_tolerance:
                    logger.info(
                        f"Duplicate screenshot detected - size {current_size} bytes is within {size_tolerance} bytes of {existing_file.name} ({existing_size} bytes), difference: {size_diff} bytes"
                    )
                    return True
            except Exception as stat_error:
                logger.warning(f"Could not check size of {existing_file}: {stat_error}")
                continue

    return False


def validate_and_save_screenshot(
    image_data: bytes, task_id: str, user_id: str, task_status: str = None, task_storage=None
) -> Optional[str]:
    """Validate PNG data and save screenshot with appropriate filename"""
    if not image_data:
        return None

    # Validate PNG header
    png_signature = b"\x89PNG\r\n\x1a\n"
    if not image_data.startswith(png_signature):
        logger.warning("Image data does not have valid PNG signature, skipping save")
        return None

    # Create task media directory
    task_media_dir = MEDIA_DIR / task_id
    task_media_dir.mkdir(exist_ok=True, parents=True)

    # Generate filename
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    task = task_storage.get_task(task_id, user_id) if task_storage else None

    if task and "steps" in task and task["steps"]:
        current_step = task["steps"][-1]["step"] - 1
    else:
        current_step = "initial"

    if task_status == TaskStatus.FINISHED or (
        task and task["status"] == TaskStatus.FINISHED
    ):
        screenshot_filename = f"final-{timestamp}.png"
    elif task_status == TaskStatus.RUNNING or (
        task and task["status"] == TaskStatus.RUNNING
    ):
        screenshot_filename = f"status-step-{current_step}-{timestamp}.png"
    else:
        task_status_str = task_status or (task["status"] if task else "unknown")
        screenshot_filename = f"status-{task_status_str}-{timestamp}.png"

    screenshot_path = task_media_dir / screenshot_filename

    # Save the screenshot
    try:
        with open(screenshot_path, "wb") as f:
            f.write(image_data)

        if screenshot_path.exists() and screenshot_path.stat().st_size > 0:
            logger.info(
                f"New unique screenshot saved: {screenshot_path} ({screenshot_path.stat().st_size} bytes)"
            )
            # Add to task storage if available
            if task_storage:
                screenshot_url = f"/media/{task_id}/{screenshot_filename}"
                media_entry = {
                    "url": screenshot_url,
                    "type": "screenshot",
                    "filename": screenshot_filename,
                    "created_at": datetime.now(UTC).isoformat() + "Z",
                }
                task_storage.add_task_media(task_id, media_entry, user_id)
            return f"/media/{task_id}/{screenshot_filename}"
        else:
            logger.error(f"Screenshot file not created or empty: {screenshot_path}")
            return None
    except Exception as save_error:
        logger.error(f"Error saving screenshot: {save_error}")
        return None


async def automated_screenshot(agent, task_id, user_id=DEFAULT_USER_ID, task_storage=None):
    """Take automated screenshot during task execution with duplicate detection"""
    # Only proceed if browser_session is set up
    if not hasattr(agent, "browser_session") or agent.browser_session is None:
        logger.warning(
            f"Agent browser_session not set up for task {task_id}, skipping screenshot."
        )
        return

    try:
        # Take the screenshot
        try:
            screenshot_data = await agent.browser_session.take_screenshot(
                full_page=True
            )
            if not screenshot_data:
                logger.warning(f"No screenshot data returned for task {task_id}")
                return
        except Exception as screenshot_error:
            logger.error(
                f"Failed to take screenshot for task {task_id}: {screenshot_error}"
            )
            return

        # Process screenshot data
        image_data = process_screenshot_data(screenshot_data)
        if not image_data:
            logger.warning(f"No image data processed for task {task_id}")
            return

        # Check for duplicates
        if check_duplicate_screenshot(image_data, task_id):
            logger.info(f"Skipping duplicate screenshot for task {task_id}")
            return

        logger.info(f"Taking screenshot for task {task_id}")

        # Save the screenshot
        screenshot_url = validate_and_save_screenshot(image_data, task_id, user_id, task_storage=task_storage)
        if screenshot_url:
            logger.info(f"Screenshot saved successfully: {screenshot_url}")

    except Exception as e:
        logger.error(f"Error in automated_screenshot for task {task_id}: {str(e)}")


async def capture_screenshot(agent_or_context, task_id, user_id=DEFAULT_USER_ID, task_storage=None):
    """Capture screenshot with flexible input handling and duplicate detection"""
    logger.info(f"Capturing screenshot for task: {task_id}")

    # Handle different input types to get browser_session
    if hasattr(agent_or_context, "browser_session"):
        browser_session = getattr(agent_or_context, "browser_session", None)
    elif hasattr(agent_or_context, "take_screenshot"):
        browser_session = agent_or_context
    else:
        logger.warning(f"Unable to determine browser session type for task {task_id}")
        return

    if browser_session is None:
        logger.warning(f"No browser session available for task {task_id}")
        return

    if not hasattr(browser_session, "take_screenshot"):
        logger.error(
            f"browser_session does not have take_screenshot method for task {task_id}"
        )
        return

    try:
        # Check if browser session is still active before trying to take screenshot
        try:
            # Try to access a simple property to check if session is alive
            if (
                hasattr(browser_session, "is_connected")
                and not browser_session.is_connected()
            ):
                logger.info(
                    f"Browser session disconnected for task {task_id}, skipping screenshot"
                )
                return
        except (AttributeError, RuntimeError):
            # If we can't check connection status, we'll try the screenshot anyway
            pass

        # Take screenshot
        try:
            screenshot_data = await browser_session.take_screenshot(full_page=True)
            if not screenshot_data:
                logger.warning(f"No screenshot data returned for task {task_id}")
                return
        except Exception as screenshot_error:
            # Check if this is a CDP/connection related error
            error_msg = str(screenshot_error).lower()
            if any(
                keyword in error_msg
                for keyword in ["cdp", "connection", "websocket", "browser", "closed"]
            ):
                logger.info(
                    f"Browser session closed for task {task_id}, cannot take screenshot: {screenshot_error}"
                )
            else:
                logger.error(
                    f"Failed to take screenshot for task {task_id}: {screenshot_error}"
                )
            return

        # Process screenshot data
        image_data = process_screenshot_data(screenshot_data)
        if not image_data:
            logger.warning(f"No image data processed for task {task_id}")
            return

        # Check for duplicates
        if check_duplicate_screenshot(image_data, task_id):
            logger.info(
                f"Skipping duplicate screenshot in capture_screenshot for task {task_id}"
            )
            return

        # Save the screenshot
        screenshot_url = validate_and_save_screenshot(image_data, task_id, user_id, task_storage=task_storage)
        if screenshot_url:
            logger.info(f"Screenshot captured and saved successfully: {screenshot_url}")

    except Exception as e:
        logger.error(f"Error in capture_screenshot for task {task_id}: {str(e)}")
