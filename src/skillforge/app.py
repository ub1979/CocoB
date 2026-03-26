"""
Backward-compatible entry point — delegates to skillforge.flet.

The full Flet UI has been refactored into the skillforge.flet package.
This module is kept so that existing imports (e.g., ``from skillforge.app import main``)
continue to work.
"""

from skillforge.flet.app import main  # noqa: F401

if __name__ == "__main__":
    import flet as ft
    ft.app(target=main)
