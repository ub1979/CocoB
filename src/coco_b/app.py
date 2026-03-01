"""
Backward-compatible entry point — delegates to coco_b.flet.

The full Flet UI has been refactored into the coco_b.flet package.
This module is kept so that existing imports (e.g., ``from coco_b.app import main``)
continue to work.
"""

from coco_b.flet.app import main  # noqa: F401

if __name__ == "__main__":
    import flet as ft
    ft.app(target=main)
