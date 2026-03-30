#!/bin/bash
# skillforge.sh — Launch SkillForge (Flet UI)
cd "$(dirname "$0")"

# Activate conda env (mr_bot)
eval "$(conda shell.bash hook)"
conda activate mr_bot

# Add src to Python path
export PYTHONPATH="$PWD/src:$PYTHONPATH"

python -m skillforge.app
