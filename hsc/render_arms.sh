#!/bin/bash
# Render one video per arm (rule baseline + the arm's runs side by side): ./hsc/render_arms.sh results/session_v3 "LG7"
set -eu
cd "$(dirname "$0")/.."
source .venv/bin/activate
ROOT=$1; SC=$2
name_of() { case "$1" in opus) echo "Opus brief only";; haiku) echo "Haiku goals only";; both) echo "Opus + Haiku";; esac; }
RULE=$(ls $ROOT/rule/*.jsonl | head -1)
for arm in opus haiku both; do
  RUNS=($(ls $ROOT/$arm/*.jsonl | sort))
  N=$(name_of $arm)
  python -m hsc.replay "$RULE" "${RUNS[@]}" \
    --labels "Rule baseline" "$N (run 1)" "$N (run 2)" \
    --title "$SC fixture: rule baseline vs $N" \
    --out $ROOT/${arm}_vs_rule.mp4 --poster $ROOT/${arm}_vs_rule.png > $ROOT/render_$arm.log 2>&1
  echo "rendered $ROOT/${arm}_vs_rule.mp4"
done
echo done > $ROOT/RENDER_DONE
