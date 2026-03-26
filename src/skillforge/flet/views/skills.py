"""
SkillsPanel — skill browser/editor.
"""

import flet as ft
from flet import Icons as icons

from skillforge.flet.theme import AppColors
from skillforge.flet.components.widgets import StyledButton, StatusBadge


class SkillsPanel:
    """Skills management panel."""

    def __init__(self, page: ft.Page, app_state, skills_manager):
        self.page = page
        self.app_state = app_state
        self.skills_manager = skills_manager

    def build(self) -> ft.Column:
        header = ft.Container(
            content=ft.Row([
                ft.Text("Skills", size=24, weight=ft.FontWeight.W_700, color=AppColors.PRIMARY),
                ft.Container(expand=True),
                StyledButton("Refresh", icon=icons.REFRESH, on_click=self._refresh_skills, variant="outline"),
                ft.Container(width=8),
                StyledButton("New Skill", icon=icons.ADD, on_click=self._create_new_skill_dialog),
            ]),
            padding=ft.Padding.only(bottom=16),
            border=ft.Border.only(bottom=ft.BorderSide(1, AppColors.BORDER))
        )

        self.skills_list = ft.ListView(expand=True, spacing=8, padding=ft.Padding.all(8))
        self.skill_editor_panel = ft.Container(visible=False)
        self._populate_skills_list()

        return ft.Column([
            header,
            ft.Text("Skills are reusable prompt templates. Use /skill-name in chat to invoke.",
                    size=12, color=AppColors.TEXT_SECONDARY),
            ft.Container(height=8),
            self.skills_list,
        ], expand=True, spacing=0)

    def _populate_skills_list(self):
        self.skills_list.controls.clear()
        if not self.skills_manager:
            self.skills_list.controls.append(ft.Text("Skills manager not available", color=AppColors.TEXT_SECONDARY))
            return

        skills = self.skills_manager.get_skills()
        if not skills:
            self.skills_list.controls.append(ft.Text("No skills loaded", color=AppColors.TEXT_SECONDARY))
            return

        bundled = [s for s in skills if s.source == "bundled"]
        user_skills = [s for s in skills if s.source == "user"]
        project = [s for s in skills if s.source == "project"]

        if bundled:
            self.skills_list.controls.append(ft.Text("Bundled Skills", size=14, weight=ft.FontWeight.W_600, color=AppColors.TEXT_SECONDARY))
            for skill in sorted(bundled, key=lambda s: s.name):
                self.skills_list.controls.append(self._create_skill_card(skill))

        if user_skills:
            self.skills_list.controls.append(ft.Container(height=16))
            self.skills_list.controls.append(ft.Text("User Skills", size=14, weight=ft.FontWeight.W_600, color=AppColors.TEXT_SECONDARY))
            for skill in sorted(user_skills, key=lambda s: s.name):
                self.skills_list.controls.append(self._create_skill_card(skill, can_edit=True))

        if project:
            self.skills_list.controls.append(ft.Container(height=16))
            self.skills_list.controls.append(ft.Text("Project Skills", size=14, weight=ft.FontWeight.W_600, color=AppColors.TEXT_SECONDARY))
            for skill in sorted(project, key=lambda s: s.name):
                self.skills_list.controls.append(self._create_skill_card(skill))

    def _create_skill_card(self, skill, can_edit=False):
        emoji = skill.emoji if skill.emoji else "\u270d\ufe0f"
        invocable_badge = StatusBadge("/command", "success") if skill.user_invocable else StatusBadge("internal", "info")

        actions = []
        if can_edit:
            actions.append(ft.IconButton(
                icon=icons.DELETE, icon_color=AppColors.ERROR, icon_size=18,
                tooltip="Delete skill", on_click=lambda e, s=skill: self._delete_skill(s),
            ))

        card_content = ft.Row([
            ft.Container(content=ft.Text(emoji, size=24), width=40, height=40,
                        bgcolor=AppColors.SECONDARY_LIGHT, border_radius=ft.BorderRadius.all(8)),
            ft.Column([
                ft.Row([ft.Text(f"/{skill.name}", size=14, weight=ft.FontWeight.W_600, color=AppColors.PRIMARY), invocable_badge], spacing=8),
                ft.Text(skill.description or "No description", size=12, color=AppColors.TEXT_SECONDARY,
                        max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
            ], spacing=2, expand=True),
            ft.Row(actions, spacing=4) if actions else ft.Container(),
        ], spacing=12)

        return ft.Container(
            content=card_content, padding=ft.Padding.all(12), bgcolor=AppColors.SURFACE,
            border=ft.Border.all(1, AppColors.BORDER), border_radius=ft.BorderRadius.all(8),
        )

    def _refresh_skills(self, e=None):
        if self.skills_manager:
            self.skills_manager.reload()
            self._populate_skills_list()
            self._show_snackbar("Skills refreshed")
        self.page.update()

    def _create_new_skill_dialog(self, e):
        name_field = ft.TextField(label="Skill Name", hint_text="my-skill (will be invoked as /my-skill)",
                                  border_color=AppColors.BORDER, color=AppColors.TEXT_PRIMARY, bgcolor=AppColors.SURFACE)
        desc_field = ft.TextField(label="Description", hint_text="What this skill does",
                                  border_color=AppColors.BORDER, color=AppColors.TEXT_PRIMARY, bgcolor=AppColors.SURFACE)
        emoji_field = ft.TextField(label="Emoji", hint_text="\u270d\ufe0f", width=80,
                                   border_color=AppColors.BORDER, color=AppColors.TEXT_PRIMARY, bgcolor=AppColors.SURFACE)

        def close_dialog(e):
            dialog.open = False
            self.page.update()

        def create_skill(e):
            name = name_field.value.strip().lower().replace(" ", "-") if name_field.value else ""
            if not name:
                self._show_snackbar("Please enter a skill name", error=True)
                return
            if self.skills_manager.get_skill(name):
                self._show_snackbar(f"Skill '{name}' already exists", error=True)
                return

            default_instructions = f"""# {name.title().replace('-', ' ')} Skill

When the user invokes this skill:

## Instructions

1. Step one
2. Step two
3. Step three

## Tips
- Add helpful tips here
"""
            skill = self.skills_manager.create_skill(
                name=name, description=desc_field.value or f"Description for {name}",
                instructions=default_instructions,
                emoji=emoji_field.value.strip() if emoji_field.value else "\u2728",
                user_invocable=True,
            )
            if skill:
                self._show_snackbar(f"Created skill: /{name}")
                self._populate_skills_list()
                dialog.open = False
            else:
                self._show_snackbar("Failed to create skill", error=True)
            self.page.update()

        dialog = ft.AlertDialog(
            modal=True, title=ft.Text("Create New Skill", color=AppColors.TEXT_PRIMARY),
            content=ft.Column([name_field, desc_field, emoji_field], tight=True, spacing=16, width=400),
            actions=[ft.TextButton("Cancel", on_click=close_dialog), StyledButton("Create", on_click=create_skill)],
            actions_alignment=ft.MainAxisAlignment.END, bgcolor=AppColors.SURFACE,
        )
        self.page.overlay.append(dialog)
        dialog.open = True
        self.page.update()

    def _delete_skill(self, skill):
        def close_dialog(e):
            dialog.open = False
            self.page.update()

        def confirm_delete(e):
            if self.skills_manager.delete_skill(skill.name):
                self._show_snackbar(f"Deleted skill: /{skill.name}")
                self._populate_skills_list()
            else:
                self._show_snackbar("Failed to delete skill", error=True)
            dialog.open = False
            self.page.update()

        dialog = ft.AlertDialog(
            modal=True, title=ft.Text(f"Delete /{skill.name}?", color=AppColors.TEXT_PRIMARY),
            content=ft.Text("This action cannot be undone.", color=AppColors.TEXT_SECONDARY),
            actions=[ft.TextButton("Cancel", on_click=close_dialog),
                     ft.TextButton("Delete", style=ft.ButtonStyle(color=AppColors.ERROR), on_click=confirm_delete)],
            actions_alignment=ft.MainAxisAlignment.END, bgcolor=AppColors.SURFACE,
        )
        self.page.overlay.append(dialog)
        dialog.open = True
        self.page.update()

    def _show_snackbar(self, message, error=False):
        snackbar = ft.SnackBar(
            content=ft.Text(message, color=AppColors.TEXT_ON_PRIMARY),
            bgcolor=AppColors.ERROR if error else AppColors.SUCCESS, open=True,
        )
        self.page.overlay.append(snackbar)
        self.page.update()
