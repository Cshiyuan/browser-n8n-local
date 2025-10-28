"""Browser configuration for task execution"""

import os
import time
import uuid
from pathlib import Path
from typing import Optional

from browser_use import BrowserProfile, BrowserSession

from task.constants import logger


def configure_browser_profile(
    task_browser_config: dict,
) -> tuple[Optional[BrowserSession], dict]:
    """Configure browser based on task and environment settings"""
    # Configure browser headless/headful mode (task setting overrides env var)
    task_headful = task_browser_config.get("headful")
    if task_headful is not None:
        headful = task_headful
    else:
        headful = os.environ.get("BROWSER_USE_HEADFUL", "false").lower() == "true"

    # Get Chrome path and user data directory (task settings override env vars)
    use_custom_chrome = task_browser_config.get("use_custom_chrome")

    if use_custom_chrome is False:
        chrome_path = None
        chrome_user_data = None
    else:
        chrome_path = os.environ.get("CHROME_PATH")
        chrome_user_data = os.environ.get("CHROME_USER_DATA")

    browser = None
    browser_info = {
        "headful": headful,
        "chrome_path": chrome_path,
        "chrome_user_data": chrome_user_data,
    }


    browser_args = [
            "--disable-blink-features=AutomationControlled",
            "--disable-dev-shm-usage",
            "--disable-infobars",
    ]

    if headful:
            browser_args.append("--start-maximized")
            logger.info("Headful mode: maximize browser window")
    else:
            browser_args.extend(["--no-sandbox", "--disable-gpu", "--window-size=1920,1080"])
            logger.info("Headless mode: set window size to 1920x1080")

    wait_page_load = 2.0
    wait_actions = 1.0

    browser_data_dir = Path("data/browser")
    browser_data_dir.mkdir(parents=True, exist_ok=True)

    storage_state_path = browser_data_dir / "storage_state.json"

    if chrome_user_data:
        user_data_path = Path(chrome_user_data)
    else:
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        unique_id = str(uuid.uuid4())[:8]
        user_data_path = browser_data_dir / f"tmp_user_data_{timestamp}_{unique_id}"

    logger.info(f"Browser storage: state={storage_state_path}, data={user_data_path}")

    browser_config_args = {
            "headless": not headful,
            "chrome_instance_path": None,
            "viewport": {"width": 1280, "height": 720},
            "window_size": {"width": 1280, "height": 720},
            "args": browser_args,
            "ignore_default_args": ["--enable-automation"],
            "dom_highlight_elements": False,
            "disable_security": False,
            "wait_for_network_idle_page_load_time": wait_page_load,
            "wait_between_actions": wait_actions,
            "storage_state": str(storage_state_path),
            "user_data_dir": str(user_data_path),
        }

    if chrome_path and chrome_path.lower() != "false":
            browser_config_args["chrome_instance_path"] = chrome_path
            logger.info(f"Using custom Chrome executable: {chrome_path}")

    window_config = task_browser_config.get("window_config")
    if window_config:
            browser_config_args.update(window_config)
            logger.info(f"Using custom window config: {window_config}")

    browser_config = BrowserProfile(**browser_config_args)
    browser = BrowserSession(browser_profile=browser_config)
    browser_info["browser_config_args"] = browser_config_args

    return browser, browser_info
