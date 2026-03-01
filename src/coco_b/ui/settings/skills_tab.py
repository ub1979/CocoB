# =============================================================================
'''
    File Name : skills_tab.py
    
    Description : Skills Tab UI - Allows users to view all loaded skills,
                  edit skill content, save / save as new / delete skills,
                  and create new skills. Skills are reusable prompt templates
                  that teach the AI how to perform tasks.
    
    Modifying it on 2026-02-07
    
    Done by : Syed Usama Bukhari & Idrak AI Ltd Team
    
    Project : mr_bot - Persistent Memory AI Chatbot
    
    License : Open Source - Safe Open Community Project
    
    Mission : Making AI Useful for Everyone
'''
# =============================================================================

# =============================================================================
# Imports
# =============================================================================

import gradio as gr
from pathlib import Path
from typing import TYPE_CHECKING, Optional, Tuple, List

from coco_b.core.skills import SkillsManager, Skill
import config

if TYPE_CHECKING:
    from .state import AppState

# =============================================================================
'''
    create_skills_tab : Main UI creation function for skills management tab
'''
# =============================================================================

# =============================================================================
# =========================================================================
# Function create_skills_tab -> AppState to None
# =========================================================================
# =============================================================================
def create_skills_tab(app_state: "AppState"):
    """
    Create the Skills management tab.

    Args:
        app_state: Shared application state

    Returns:
        None (creates Gradio components in current context)
    """
    # Initialize skills manager
    skills_manager = SkillsManager(
        bundled_dir=Path(config.SKILLS_DIR),
        user_dir=Path(config.USER_SKILLS_DIR),
    )
    skills_manager.load_all_skills()

    # Store manager in app_state for access from other parts of the app
    app_state.skills_manager = skills_manager

    # Connect skills manager to router's personality for /command handling
    # ==================================
    if hasattr(app_state.router, 'personality'):
        app_state.router.personality.skills_manager = skills_manager

    with gr.Tab("Skills"):
        gr.Markdown("## Skills Management")
        gr.Markdown("Skills are reusable prompt templates that teach the AI how to perform tasks. Use `/skill-name` in chat to invoke a skill.")

        with gr.Row():
            # Left column: Skills list
            with gr.Column(scale=1):
                gr.Markdown("### Available Skills")

                # Skills list as radio buttons
                skills_list = gr.Radio(
                    choices=_get_skill_choices(skills_manager),
                    label="Select a skill to view/edit",
                    value=None,
                )

                # Refresh button
                refresh_btn = gr.Button("🔄 Refresh Skills", size="sm")

                gr.Markdown("---")
                gr.Markdown("### Create New Skill")

                new_skill_name = gr.Textbox(
                    label="Skill Name",
                    placeholder="my-skill",
                    info="Used as /command (e.g., /my-skill)"
                )
                create_btn = gr.Button("➕ Create New Skill", variant="secondary")
                create_status = gr.Textbox(
                    label="Status",
                    interactive=False,
                    visible=False
                )

            # Right column: Skill editor
            with gr.Column(scale=2):
                # Header showing which skill is being edited
                editor_header = gr.Markdown("### Select a skill to edit")

                # Skill metadata (read-only)
                with gr.Row():
                    skill_source = gr.Textbox(
                        label="Source",
                        interactive=False,
                        scale=1
                    )
                    skill_emoji = gr.Textbox(
                        label="Emoji",
                        placeholder="📝",
                        scale=1
                    )

                skill_description = gr.Textbox(
                    label="Description",
                    placeholder="What this skill does..."
                )

                skill_invocable = gr.Checkbox(
                    label="User Invocable (show as /command)",
                    value=True
                )

                # Full skill content editor
                skill_content = gr.TextArea(
                    label="Skill Content (Markdown)",
                    placeholder="# Skill Name\n\nInstructions for the AI...",
                    lines=20,
                )

                # Action buttons
                with gr.Row():
                    save_btn = gr.Button("💾 Save", variant="primary", scale=1)
                    save_as_btn = gr.Button("📋 Save As New...", scale=1)
                    delete_btn = gr.Button("🗑️ Delete", variant="stop", scale=1)

                # Status message
                editor_status = gr.Textbox(
                    label="Status",
                    interactive=False,
                    visible=False
                )

        # Hidden state to track current skill name
        current_skill_name = gr.State(value=None)

        # =============================================================================
        # Event Handlers Section
        # =============================================================================

        # =============================================================================
        # =========================================================================
        # Function on_refresh -> to gr.update
        # =========================================================================
        # =============================================================================
        def on_refresh():
            """Reload skills and update the list"""
            skills_manager.reload()
            choices = _get_skill_choices(skills_manager)
            return gr.update(choices=choices, value=None)

        # =============================================================================
        # =========================================================================
        # Function on_skill_select -> str to tuple
        # =========================================================================
        # =============================================================================
        def on_skill_select(skill_choice: str):
            """Load selected skill into editor"""
            # ==================================
            if not skill_choice:
                return (
                    "### Select a skill to edit",  # editor_header
                    "",  # skill_source
                    "",  # skill_emoji
                    "",  # skill_description
                    True,  # skill_invocable
                    "",  # skill_content
                    None,  # current_skill_name
                    gr.update(visible=False),  # editor_status
                )

            # Extract skill name from choice (format: "emoji name - description")
            skill_name = _extract_skill_name(skill_choice)
            skill = skills_manager.get_skill(skill_name)

            # ==================================
            if not skill:
                return (
                    f"### Skill not found: {skill_name}",
                    "",
                    "",
                    "",
                    True,
                    "",
                    None,
                    gr.update(value=f"Skill not found: {skill_name}", visible=True),
                )

            # Build full content (frontmatter + body) for editing
            full_content = _build_full_content(skill)

            source_display = f"{skill.source.title()}"
            # ==================================
            if skill.file_path:
                source_display += f" ({skill.file_path})"

            return (
                f"### Editing: {skill.get_display_name()}",  # editor_header
                source_display,  # skill_source
                skill.emoji,  # skill_emoji
                skill.description,  # skill_description
                skill.user_invocable,  # skill_invocable
                full_content,  # skill_content
                skill.name,  # current_skill_name
                gr.update(visible=False),  # editor_status
            )

        # =============================================================================
        # =========================================================================
        # Function on_save -> str, str, str, str, str, bool to tuple
        # =========================================================================
        # =============================================================================
        def on_save(skill_name: str, content: str, description: str, emoji: str, invocable: bool):
            """Save changes to current skill"""
            # ==================================
            if not skill_name:
                return (
                    gr.update(value="No skill selected", visible=True),
                    gr.update(),  # skills_list unchanged
                )

            skill = skills_manager.get_skill(skill_name)
            # ==================================
            if not skill:
                return (
                    gr.update(value=f"Skill not found: {skill_name}", visible=True),
                    gr.update(),
                )

            # Update skill with new values
            skill.instructions = content
            skill.description = description
            skill.emoji = emoji.strip() if emoji else ""
            skill.user_invocable = invocable

            # Save skill
            # ==================================
            if skills_manager.save_skill(skill):
                # Refresh the list to show updated info
                choices = _get_skill_choices(skills_manager)
                return (
                    gr.update(value=f"Saved skill: {skill_name}", visible=True),
                    gr.update(choices=choices),
                )
            else:
                return (
                    gr.update(value=f"Failed to save skill: {skill_name}", visible=True),
                    gr.update(),
                )

        # =============================================================================
        # =========================================================================
        # Function on_save_as_new -> str, str, str, bool to gr.update
        # =========================================================================
        # =============================================================================
        def on_save_as_new(content: str, description: str, emoji: str, invocable: bool):
            """Save as a new skill (opens dialog)"""
            # For now, we'll use a simple approach - return a message asking for new name
            return gr.update(
                value="Enter a new name in 'Create New Skill' section and click Create, then copy the content.",
                visible=True
            )

        # =============================================================================
        # =========================================================================
        # Function on_delete -> str to tuple
        # =========================================================================
        # =============================================================================
        def on_delete(skill_name: str):
            """Delete the current skill"""
            # ==================================
            if not skill_name:
                return (
                    gr.update(value="No skill selected", visible=True),
                    gr.update(),  # skills_list
                    "### Select a skill to edit",  # editor_header
                    "",  # skill_source
                    "",  # skill_emoji
                    "",  # skill_description
                    True,  # skill_invocable
                    "",  # skill_content
                    None,  # current_skill_name
                )

            skill = skills_manager.get_skill(skill_name)
            # ==================================
            if skill and skill.source == "bundled":
                return (
                    gr.update(value="Cannot delete bundled skills", visible=True),
                    gr.update(),
                    gr.update(),
                    gr.update(),
                    gr.update(),
                    gr.update(),
                    gr.update(),
                    gr.update(),
                    skill_name,
                )

            # ==================================
            if skills_manager.delete_skill(skill_name):
                choices = _get_skill_choices(skills_manager)
                return (
                    gr.update(value=f"Deleted skill: {skill_name}", visible=True),
                    gr.update(choices=choices, value=None),
                    "### Select a skill to edit",
                    "",
                    "",
                    "",
                    True,
                    "",
                    None,
                )
            else:
                return (
                    gr.update(value=f"Failed to delete skill: {skill_name}", visible=True),
                    gr.update(),
                    gr.update(),
                    gr.update(),
                    gr.update(),
                    gr.update(),
                    gr.update(),
                    gr.update(),
                    skill_name,
                )

        # =============================================================================
        # =========================================================================
        # Function on_create_new -> str to tuple
        # =========================================================================
        # =============================================================================
        def on_create_new(name: str):
            """Create a new skill"""
            # ==================================
            if not name or not name.strip():
                return (
                    gr.update(value="Please enter a skill name", visible=True),
                    gr.update(),  # skills_list
                )

            # Clean the name
            clean_name = name.strip().lower().replace(" ", "-")

            # Check if already exists
            # ==================================
            if skills_manager.get_skill(clean_name):
                return (
                    gr.update(value=f"Skill already exists: {clean_name}", visible=True),
                    gr.update(),
                )

            # Create with default content
            default_instructions = f"""# {clean_name.title().replace('-', ' ')} Skill

When the user invokes this skill:

## Instructions

1. Step one
2. Step two
3. Step three

## Tips
- Add helpful tips here
"""

            skill = skills_manager.create_skill(
                name=clean_name,
                description=f"Description for {clean_name}",
                instructions=default_instructions,
                emoji="✨",
                user_invocable=True
            )

            # ==================================
            if skill:
                choices = _get_skill_choices(skills_manager)
                return (
                    gr.update(value=f"Created skill: {clean_name}", visible=True),
                    gr.update(choices=choices),
                )
            else:
                return (
                    gr.update(value=f"Failed to create skill: {clean_name}", visible=True),
                    gr.update(),
                )

        # =============================================================================
        # Wire Up Events Section
        # =============================================================================

        # Refresh skills
        refresh_btn.click(
            fn=on_refresh,
            inputs=[],
            outputs=[skills_list]
        )

        # Skill selection
        skills_list.change(
            fn=on_skill_select,
            inputs=[skills_list],
            outputs=[
                editor_header,
                skill_source,
                skill_emoji,
                skill_description,
                skill_invocable,
                skill_content,
                current_skill_name,
                editor_status,
            ]
        )

        # Save skill
        save_btn.click(
            fn=on_save,
            inputs=[current_skill_name, skill_content, skill_description, skill_emoji, skill_invocable],
            outputs=[editor_status, skills_list]
        )

        # Save as new
        save_as_btn.click(
            fn=on_save_as_new,
            inputs=[skill_content, skill_description, skill_emoji, skill_invocable],
            outputs=[editor_status]
        )

        # Delete skill
        delete_btn.click(
            fn=on_delete,
            inputs=[current_skill_name],
            outputs=[
                editor_status,
                skills_list,
                editor_header,
                skill_source,
                skill_emoji,
                skill_description,
                skill_invocable,
                skill_content,
                current_skill_name,
            ]
        )

        # Create new skill
        create_btn.click(
            fn=on_create_new,
            inputs=[new_skill_name],
            outputs=[create_status, skills_list]
        )

        gr.Markdown("---")
        gr.Markdown("""
**Skill Locations:**
- Bundled: Shipped with mr_bot (read-only)
- User: `~/.mr_bot/skills/` (editable)

**Usage:** Type `/skill-name` in chat to invoke a skill (e.g., `/commit`)
        """)

# =============================================================================
'''
    Helper Functions : Utility functions for skill management
'''
# =============================================================================

# =============================================================================
# =========================================================================
# Function _get_skill_choices -> SkillsManager to List[str]
# =========================================================================
# =============================================================================
def _get_skill_choices(manager: SkillsManager) -> List[str]:
    """Build choices list for skills radio buttons"""
    skills = manager.get_skills()
    choices = []

    for skill in sorted(skills, key=lambda s: s.name):
        display = skill.get_display_name()
        # ==================================
        if skill.description:
            display += f" - {skill.description}"
        choices.append(display)

    return choices

# =============================================================================
# =========================================================================
# Function _extract_skill_name -> str to str
# =========================================================================
# =============================================================================
def _extract_skill_name(choice: str) -> str:
    """Extract skill name from choice string (format: 'emoji name - description')"""
    # Remove description if present
    # ==================================
    if " - " in choice:
        choice = choice.split(" - ")[0]

    # Remove emoji if present (emoji is typically first character(s) followed by space)
    parts = choice.strip().split(" ", 1)
    # ==================================
    if len(parts) == 2:
        # Check if first part is an emoji (very rough check)
        first = parts[0]
        # ==================================
        if len(first) <= 2 or not first.isalnum():
            return parts[1]

    return choice.strip()

# =============================================================================
# =========================================================================
# Function _build_full_content -> Skill to str
# =========================================================================
# =============================================================================
def _build_full_content(skill: Skill) -> str:
    """Build the full markdown content (instructions only, metadata shown separately)"""
    return skill.instructions

# =============================================================================
# End of File
# =============================================================================
# Project : mr_bot - Persistent Memory AI Chatbot
# License : Open Source - Safe Open Community Project
# Mission : Making AI Useful for Everyone
# =============================================================================
