#\!/bin/bash
# cocob.sh — Launch coco B (Flet UI)
cd "$(dirname "$0")"
conda activate mr_bot
python -m coco_b.app
