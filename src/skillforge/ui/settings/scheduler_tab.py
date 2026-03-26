# =============================================================================
'''
    File Name : scheduler_tab.py

    Description : Gradio UI tab for managing scheduled tasks. Provides interface
                  for creating, editing, deleting, and monitoring cron-based
                  task execution.

    Modifying it on 2026-02-09

    Done by : Syed Usama Bukhari & Idrak AI Ltd Team

    Project : SkillForge - Persistent Memory AI Chatbot

    License : Open Source - Safe Open Community Project

    Mission : Making AI Useful for Everyone
'''
# =============================================================================

# =============================================================================
# Import Section
# =============================================================================
import gradio as gr
import asyncio
from datetime import datetime
from typing import TYPE_CHECKING, Optional, List, Tuple

if TYPE_CHECKING:
    from .state import AppState


# =============================================================================
# Common cron presets for user convenience
# =============================================================================
CRON_PRESETS = {
    "Every minute": "* * * * *",
    "Every 5 minutes": "*/5 * * * *",
    "Every 15 minutes": "*/15 * * * *",
    "Every hour": "0 * * * *",
    "Every day at 9 AM": "0 9 * * *",
    "Every day at 6 PM": "0 18 * * *",
    "Every Monday at 9 AM": "0 9 * * 1",
    "Every weekday at 9 AM": "0 9 * * 1-5",
    "First of month at 9 AM": "0 9 1 * *",
    "Custom": "",
}


# =============================================================================
'''
    create_scheduler_tab : Creates the Scheduler tab for the Gradio UI
'''
# =============================================================================
def create_scheduler_tab(app_state: "AppState"):
    """
    Create the Scheduler Settings tab.

    Args:
        app_state: Application state containing scheduler_manager

    Returns:
        None (modifies Gradio UI in context)
    """
    with gr.Tab("Scheduler"):
        gr.Markdown("## Scheduled Tasks")
        gr.Markdown(
            "Create and manage scheduled tasks that run automatically. "
            "Tasks can send messages or execute skills on a cron schedule."
        )

        # =========================================================================
        # Status Display
        # =========================================================================
        with gr.Row():
            scheduler_status = gr.Textbox(
                label="Scheduler Status",
                value=_get_scheduler_status(app_state),
                interactive=False,
                scale=3,
            )
            refresh_status_btn = gr.Button("Refresh", scale=1, size="sm")

        # =========================================================================
        # Task List Display
        # =========================================================================
        gr.Markdown("### Active Tasks")

        task_list = gr.Dataframe(
            headers=["ID", "Name", "Schedule", "Action", "Channel", "Status", "Next Run"],
            datatype=["str", "str", "str", "str", "str", "str", "str"],
            value=_get_task_list(app_state),
            interactive=False,
            wrap=True,
            row_count=(5, "dynamic"),
        )

        with gr.Row():
            refresh_list_btn = gr.Button("Refresh List", size="sm")
            selected_task_id = gr.Textbox(
                label="Selected Task ID",
                placeholder="Enter task ID to edit/delete",
                scale=2,
            )

        with gr.Row():
            pause_btn = gr.Button("Pause Task", size="sm", variant="secondary")
            resume_btn = gr.Button("Resume Task", size="sm", variant="secondary")
            delete_btn = gr.Button("Delete Task", size="sm", variant="stop")

        task_action_result = gr.Textbox(
            label="Result",
            interactive=False,
            visible=True,
        )

        # =========================================================================
        # Create New Task Section
        # =========================================================================
        gr.Markdown("### Create New Task")

        with gr.Row():
            with gr.Column(scale=1):
                task_name = gr.Textbox(
                    label="Task Name",
                    placeholder="Daily Summary",
                )
                task_description = gr.Textbox(
                    label="Description",
                    placeholder="Send daily summary message",
                    lines=2,
                )

            with gr.Column(scale=1):
                action_type = gr.Dropdown(
                    choices=["send_message", "execute_skill"],
                    value="send_message",
                    label="Action Type",
                )
                target_channel = gr.Dropdown(
                    choices=["telegram", "discord", "slack", "gradio"],
                    value="telegram",
                    label="Target Channel",
                )

        with gr.Row():
            with gr.Column(scale=1):
                target_user = gr.Textbox(
                    label="Target User ID",
                    placeholder="user-123 or @username",
                )
                target_chat = gr.Textbox(
                    label="Target Chat ID (optional)",
                    placeholder="Leave empty for DM",
                )

            with gr.Column(scale=1):
                cron_preset = gr.Dropdown(
                    choices=list(CRON_PRESETS.keys()),
                    value="Every day at 9 AM",
                    label="Schedule Preset",
                )
                cron_schedule = gr.Textbox(
                    label="Cron Expression",
                    value="0 9 * * *",
                    placeholder="* * * * * (min hour day month weekday)",
                )
                timezone = gr.Dropdown(
                    choices=["UTC", "US/Eastern", "US/Pacific", "Europe/London", "Europe/Paris", "Asia/Tokyo"],
                    value="UTC",
                    label="Timezone",
                )

        # =========================================================================
        # Action-specific fields
        # =========================================================================
        with gr.Group() as message_group:
            message_content = gr.Textbox(
                label="Message Content",
                placeholder="Good morning! Here's your daily update.",
                lines=3,
            )

        with gr.Group(visible=False) as skill_group:
            skill_name = gr.Textbox(
                label="Skill Name",
                placeholder="commit (without /)",
            )
            skill_params = gr.Textbox(
                label="Skill Parameters",
                placeholder="Optional parameters for the skill",
            )

        create_btn = gr.Button("Create Task", variant="primary")
        create_result = gr.Textbox(
            label="Create Result",
            interactive=False,
        )

        # =========================================================================
        # Execution Log Section
        # =========================================================================
        gr.Markdown("### Execution Log")

        execution_log = gr.Dataframe(
            headers=["Timestamp", "Task", "Success", "Error"],
            datatype=["str", "str", "str", "str"],
            value=_get_execution_log(app_state),
            interactive=False,
            wrap=True,
            row_count=(5, "dynamic"),
        )

        refresh_log_btn = gr.Button("Refresh Log", size="sm")

        # =========================================================================
        # Event Handlers
        # =========================================================================

        # Toggle action-specific fields
        def toggle_action_fields(action: str):
            if action == "send_message":
                return gr.update(visible=True), gr.update(visible=False)
            else:
                return gr.update(visible=False), gr.update(visible=True)

        action_type.change(
            fn=toggle_action_fields,
            inputs=[action_type],
            outputs=[message_group, skill_group],
        )

        # Update cron from preset
        def update_cron_from_preset(preset: str) -> str:
            return CRON_PRESETS.get(preset, "")

        cron_preset.change(
            fn=update_cron_from_preset,
            inputs=[cron_preset],
            outputs=[cron_schedule],
        )

        # Refresh status
        def refresh_status():
            return _get_scheduler_status(app_state)

        refresh_status_btn.click(
            fn=refresh_status,
            inputs=[],
            outputs=[scheduler_status],
        )

        # Refresh task list
        def refresh_list():
            return _get_task_list(app_state)

        refresh_list_btn.click(
            fn=refresh_list,
            inputs=[],
            outputs=[task_list],
        )

        # Refresh log
        def refresh_log():
            return _get_execution_log(app_state)

        refresh_log_btn.click(
            fn=refresh_log,
            inputs=[],
            outputs=[execution_log],
        )

        # Create task
        def create_task(
            name: str,
            description: str,
            action: str,
            channel: str,
            user: str,
            chat: str,
            schedule: str,
            tz: str,
            message: str,
            skill: str,
            params: str,
        ) -> Tuple[str, list]:
            result = _create_task(
                app_state,
                name=name,
                description=description,
                action=action,
                channel=channel,
                user=user,
                chat=chat,
                schedule=schedule,
                timezone=tz,
                message=message,
                skill=skill,
                params=params,
            )
            return result, _get_task_list(app_state)

        create_btn.click(
            fn=create_task,
            inputs=[
                task_name,
                task_description,
                action_type,
                target_channel,
                target_user,
                target_chat,
                cron_schedule,
                timezone,
                message_content,
                skill_name,
                skill_params,
            ],
            outputs=[create_result, task_list],
        )

        # Pause task
        def pause_task(task_id: str) -> Tuple[str, list]:
            result = _pause_task(app_state, task_id)
            return result, _get_task_list(app_state)

        pause_btn.click(
            fn=pause_task,
            inputs=[selected_task_id],
            outputs=[task_action_result, task_list],
        )

        # Resume task
        def resume_task(task_id: str) -> Tuple[str, list]:
            result = _resume_task(app_state, task_id)
            return result, _get_task_list(app_state)

        resume_btn.click(
            fn=resume_task,
            inputs=[selected_task_id],
            outputs=[task_action_result, task_list],
        )

        # Delete task
        def delete_task(task_id: str) -> Tuple[str, list]:
            result = _delete_task(app_state, task_id)
            return result, _get_task_list(app_state)

        delete_btn.click(
            fn=delete_task,
            inputs=[selected_task_id],
            outputs=[task_action_result, task_list],
        )


# =============================================================================
# Helper Functions
# =============================================================================

def _get_scheduler_status(app_state: "AppState") -> str:
    """Get scheduler status string"""
    if not hasattr(app_state, 'scheduler_manager') or app_state.scheduler_manager is None:
        return "Scheduler not initialized"

    status = app_state.scheduler_manager.get_status()
    return (
        f"Running: {status['running']} | "
        f"Tasks: {status['task_count']} ({status['active_tasks']} active, {status['paused_tasks']} paused) | "
        f"Channels: {', '.join(status['registered_channels']) or 'None'}"
    )


def _get_task_list(app_state: "AppState") -> List[List[str]]:
    """Get task list for dataframe"""
    if not hasattr(app_state, 'scheduler_manager') or app_state.scheduler_manager is None:
        return []

    tasks = app_state.scheduler_manager.list_tasks()
    rows = []

    for task in tasks:
        next_run = task.get("next_run", "")
        if next_run:
            try:
                dt = datetime.fromisoformat(next_run.replace("Z", "+00:00"))
                next_run = dt.strftime("%Y-%m-%d %H:%M")
            except Exception:
                pass

        rows.append([
            task["id"],
            task["name"],
            task["schedule"],
            task["action"],
            task["target_channel"],
            task["status"],
            next_run or "N/A",
        ])

    return rows


def _get_execution_log(app_state: "AppState") -> List[List[str]]:
    """Get execution log for dataframe"""
    if not hasattr(app_state, 'scheduler_manager') or app_state.scheduler_manager is None:
        return []

    logs = app_state.scheduler_manager.get_execution_log(limit=20)
    rows = []

    for log in logs:
        timestamp = log.get("timestamp", "")
        if timestamp:
            try:
                dt = datetime.fromisoformat(timestamp)
                timestamp = dt.strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                pass

        rows.append([
            timestamp,
            log.get("task_name", "Unknown"),
            "Yes" if log.get("success") else "No",
            log.get("error") or "",
        ])

    return rows


def _create_task(
    app_state: "AppState",
    name: str,
    description: str,
    action: str,
    channel: str,
    user: str,
    chat: str,
    schedule: str,
    timezone: str,
    message: str,
    skill: str,
    params: str,
) -> str:
    """Create a new scheduled task"""
    if not hasattr(app_state, 'scheduler_manager') or app_state.scheduler_manager is None:
        return "Error: Scheduler not initialized"

    if not name:
        return "Error: Task name is required"

    if not user:
        return "Error: Target user is required"

    if not schedule:
        return "Error: Schedule is required"

    if action == "send_message" and not message:
        return "Error: Message content is required for send_message action"

    if action == "execute_skill" and not skill:
        return "Error: Skill name is required for execute_skill action"

    # Import here to avoid circular imports
    from skillforge.core.scheduler import ScheduledTask

    task = ScheduledTask(
        name=name,
        description=description,
        schedule=schedule,
        timezone=timezone,
        action=action,
        target_channel=channel,
        target_user=user,
        target_chat=chat or None,
        message=message if action == "send_message" else None,
        skill_name=skill if action == "execute_skill" else None,
        skill_params=params if action == "execute_skill" else None,
    )

    try:
        # Run async operation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            task_id = loop.run_until_complete(app_state.scheduler_manager.add_task(task))
        finally:
            loop.close()

        return f"Task created successfully! ID: {task_id}"

    except ValueError as e:
        return f"Error: {str(e)}"
    except Exception as e:
        return f"Error creating task: {str(e)}"


def _pause_task(app_state: "AppState", task_id: str) -> str:
    """Pause a scheduled task"""
    if not hasattr(app_state, 'scheduler_manager') or app_state.scheduler_manager is None:
        return "Error: Scheduler not initialized"

    if not task_id:
        return "Error: Please enter a task ID"

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            success = loop.run_until_complete(app_state.scheduler_manager.pause_task(task_id))
        finally:
            loop.close()

        if success:
            return f"Task {task_id} paused"
        else:
            return f"Task {task_id} not found"

    except Exception as e:
        return f"Error: {str(e)}"


def _resume_task(app_state: "AppState", task_id: str) -> str:
    """Resume a paused task"""
    if not hasattr(app_state, 'scheduler_manager') or app_state.scheduler_manager is None:
        return "Error: Scheduler not initialized"

    if not task_id:
        return "Error: Please enter a task ID"

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            success = loop.run_until_complete(app_state.scheduler_manager.resume_task(task_id))
        finally:
            loop.close()

        if success:
            return f"Task {task_id} resumed"
        else:
            return f"Task {task_id} not found"

    except Exception as e:
        return f"Error: {str(e)}"


def _delete_task(app_state: "AppState", task_id: str) -> str:
    """Delete a scheduled task"""
    if not hasattr(app_state, 'scheduler_manager') or app_state.scheduler_manager is None:
        return "Error: Scheduler not initialized"

    if not task_id:
        return "Error: Please enter a task ID"

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            success = loop.run_until_complete(app_state.scheduler_manager.remove_task(task_id))
        finally:
            loop.close()

        if success:
            return f"Task {task_id} deleted"
        else:
            return f"Task {task_id} not found"

    except Exception as e:
        return f"Error: {str(e)}"


# =============================================================================
'''
    End of File : scheduler_tab.py

    Project : SkillForge - Persistent Memory AI Chatbot

    License : Open Source - Safe Open Community Project

    Mission : Making AI Useful for Everyone

    Done by : Syed Usama Bukhari & Idrak AI Ltd Team
'''
# =============================================================================
