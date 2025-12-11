"""Task execution orchestration"""

from typing import Optional

from browser_use import Agent, BrowserSession
from browser_use.agent.views import AgentHistoryList

from task.constants import TaskStatus, logger, MAX_HISTORY_ITEMS
from task.llm import get_llm
from task.browser_config import configure_browser_profile
from task.agent import create_agent_config
from task.utils import get_sensitive_data, prepare_task_environment, trigger_webhook
from task.storage.base import DEFAULT_USER_ID
from task.schema_utils import parse_output_model_schema


async def process_task_result(result, task_id: str, user_id: str, task_storage):
    """Process and store task execution result"""
    if isinstance(result, AgentHistoryList):
        final_result = result.final_result()
        task_storage.set_task_output(task_id, final_result or "", user_id)
    else:
        task_storage.set_task_output(task_id, str(result), user_id)


async def collect_browser_cookies(agent, task_id: str, user_id: str, task_storage):
    """Collect browser cookies if requested and available"""
    task = task_storage.get_task(task_id, user_id)
    if (
        not task
        or not task.get("save_browser_data")
        or not hasattr(agent, "browser_session")
    ):
        return

    try:
        cookies = []
        browser_session = None
        try:
            browser_session = agent.browser_session
        except (AssertionError, AttributeError):
            logger.warning(
                f"BrowserSession is not set up for task {task_id}, skipping cookie collection."
            )

        if browser_session and hasattr(browser_session, "get_cookies"):
            # Check if browser connection is still alive before attempting cookie collection
            try:
                # Verify browser context is available and not closed
                if hasattr(browser_session, 'context') and browser_session.context:
                    cookies = await browser_session.get_cookies()
                    logger.info(f"Successfully collected {len(cookies)} cookies for task {task_id}")
                else:
                    logger.warning(f"Browser context already closed for task {task_id}, skipping cookie collection")
            except Exception as conn_err:
                # Browser connection already closed - this is expected after agent.run() completes
                logger.info(f"Browser connection closed for task {task_id}, skipping cookie collection: {str(conn_err)}")
        else:
            logger.warning(f"No method to collect cookies for task {task_id}")

        task_storage.update_task(
            task_id, {"browser_data": {"cookies": cookies}}, user_id
        )
    except Exception as e:
        logger.error(f"Failed to collect browser data: {str(e)}")
        task_storage.update_task(
            task_id, {"browser_data": {"cookies": [], "error": str(e)}}, user_id
        )


async def cleanup_task(browser: Optional[BrowserSession], task_id: str, user_id: str, task_storage):
    """Clean up task resources after execution"""
    # 1. Stop agent (sets stop flag)
    try:
        agent = task_storage.get_task_agent(task_id, user_id)
        if agent:
            logger.info(f"Stopping agent for task {task_id}")
            try:
                agent.stop()  # No parameters - just sets stopped flag
            except Exception as e:
                logger.warning(f"Error stopping agent for task {task_id}: {e}")
    except Exception as e:
        logger.warning(f"Error during agent stop for task {task_id}: {e}")

    # 2. Close browser (this cleans up BrowserSession EventBus)
    if browser is not None:
        logger.info(f"Closing browser for task {task_id}")
        try:
            await browser.stop()
        except Exception as e:
            logger.error(f"Error closing browser for task {task_id}: {str(e)}")

    # 3. Remove agent reference from storage (enables garbage collection)
    try:
        task_storage.remove_task_agent(task_id, user_id)
    except Exception as e:
        logger.warning(f"Error removing agent reference for task {task_id}: {e}")


async def execute_task(
    task_id: str, instruction: str, ai_provider: str, user_id: str = DEFAULT_USER_ID, task_storage=None
):
    """Execute browser task in background - main orchestration function

    Chrome paths (CHROME_PATH and CHROME_USER_DATA) are only sourced from
    environment variables for security reasons.
    """
    browser: Optional[BrowserSession] = None
    try:
        # Update task status and prepare environment
        task_storage.update_task_status(task_id, TaskStatus.RUNNING, user_id)
        prepare_task_environment(task_id, user_id)

        # Get task configuration
        task = task_storage.get_task(task_id, user_id)
        task_browser_config = task.get("browser_config", {}) if task else {}

        # Set up LLM and browser
        llm = get_llm(ai_provider)
        browser, browser_info = configure_browser_profile(task_browser_config)
        logger.info(f"Task {task_id}: Browser configuration: {browser_info}")

        # Process agent configuration options
        use_vision = None
        output_model = None

        # Extract and convert use_vision parameter
        use_vision_str = task.get("use_vision") if task else None
        if use_vision_str:
            if use_vision_str.lower() == "auto":
                use_vision = "auto"
            elif use_vision_str.lower() == "true":
                use_vision = True
            elif use_vision_str.lower() == "false":
                use_vision = False
            logger.info(f"Task {task_id}: use_vision set to {use_vision}")

        # Parse output model schema if provided
        output_model_schema_str = task.get("output_model_schema") if task else None
        if output_model_schema_str:
            logger.info(f"Task {task_id}: Parsing output model schema")
            output_model = parse_output_model_schema(output_model_schema_str)
            if output_model:
                logger.info(f"Task {task_id}: Successfully created output model: {output_model.__name__}")
            else:
                logger.warning(f"Task {task_id}: Failed to parse output model schema")

        # Create agent with all configuration
        sensitive_data = get_sensitive_data()
        logger.info(f"Task {task_id}: MAX_HISTORY_ITEMS={MAX_HISTORY_ITEMS}")
        agent_config = create_agent_config(
            instruction, llm, sensitive_data, browser, use_vision, output_model, MAX_HISTORY_ITEMS
        )
        logger.info(f"Agent config keys: {list(agent_config.keys())}")
        logger.info(f"Agent config max_history_items: {agent_config.get('max_history_items')}")

        agent = Agent(**agent_config)

        # Configure EventBus max_history_size to reduce memory usage
        # EventBus defaults to max_history_size=50, which causes high memory consumption
        # Agent uses 'eventbus' attribute (no underscore)
        if hasattr(agent, 'eventbus') and agent.eventbus:
            try:
                old_size = agent.eventbus.max_history_size
                agent.eventbus.max_history_size = MAX_HISTORY_ITEMS
                logger.info(f"Task {task_id}: Agent EventBus max_history_size: {old_size} -> {MAX_HISTORY_ITEMS}")
            except Exception as e:
                logger.warning(f"Task {task_id}: Failed to set Agent EventBus max_history_size: {e}")
        else:
            logger.warning(f"Task {task_id}: Agent has no eventbus attribute")

        task_storage.set_task_agent(task_id, agent, user_id)

        # Execute task without automated screenshots
        result = await agent.run()

        # Process results
        task_storage.mark_task_finished(task_id, user_id, TaskStatus.FINISHED)
        await process_task_result(result, task_id, user_id, task_storage)
        await collect_browser_cookies(agent, task_id, user_id, task_storage)
        
        # Trigger webhook on successful completion
        webhook_url = task.get("webhook_url") if task else None
        webhook_events = task.get("webhook_events", []) if task else []
        if webhook_url and "task.completed" in webhook_events:
            output = task_storage.get_task(task_id, user_id).get("output") if task_storage.get_task(task_id, user_id) else None
            await trigger_webhook(
                webhook_url=webhook_url,
                task_id=task_id,
                status="completed",
                event_type="task.completed",
                result=output
            )

    except Exception as e:
        logger.exception(f"Error executing task {task_id}")
        task_storage.update_task_status(task_id, TaskStatus.FAILED, user_id)
        task_storage.set_task_error(task_id, str(e), user_id)
        task_storage.mark_task_finished(task_id, user_id, TaskStatus.FAILED)
        
        # Trigger webhook on failure
        try:
            task = task_storage.get_task(task_id, user_id)
            webhook_url = task.get("webhook_url") if task else None
            webhook_events = task.get("webhook_events", []) if task else []
            if webhook_url and "task.failed" in webhook_events:
                await trigger_webhook(
                    webhook_url=webhook_url,
                    task_id=task_id,
                    status="failed",
                    event_type="task.failed",
                    error=str(e)
                )
        except Exception as webhook_error:
            logger.error(f"Failed to trigger webhook on task failure: {webhook_error}")
    finally:
        await cleanup_task(browser, task_id, user_id, task_storage)


async def cleanup_all_tasks(task_storage):
    """Clean up all running tasks on shutdown"""
    try:
        # Get all tasks from storage
        all_tasks = task_storage.list_tasks()
        if isinstance(all_tasks, dict) and "tasks" in all_tasks:
            tasks_list = all_tasks["tasks"]

            for task_summary in tasks_list:
                task_id = task_summary["id"]
                task = task_storage.get_task(task_id)

                if task and task.get("status") in [
                    TaskStatus.RUNNING,
                    TaskStatus.PAUSED,
                ]:
                    logger.info(f"Cleaning up running task: {task_id}")

                    # Get agent and try to stop it gracefully
                    agent = task_storage.get_task_agent(task_id)
                    if agent:
                        try:
                            agent.stop()  # No parameters - just sets stopped flag
                        except Exception as e:
                            logger.warning(
                                f"Error stopping agent for task {task_id}: {e}"
                            )
                        # Remove agent from storage to enable garbage collection
                        task_storage.remove_task_agent(task_id)

                    # Update task status
                    task_storage.update_task_status(task_id, TaskStatus.STOPPED)
                    task_storage.mark_task_finished(task_id, status=TaskStatus.STOPPED)

        logger.info("Task cleanup completed")
    except Exception as e:
        logger.error(f"Error during task cleanup: {e}")
