#\!/bin/bash
# skillforge.sh — Launch SkillForge (Flet UI)
cd "$(dirname "$0")"
conda activate skillforge
python -m skillforge.app
