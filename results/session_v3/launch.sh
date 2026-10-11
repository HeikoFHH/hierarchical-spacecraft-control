#!/bin/bash
# Rule baseline, then Opus-only / Haiku-only / both on the LG7 fixture (2 repeats each, in parallel). Needs ANTHROPIC_API_KEY.
set -u
cd "$(dirname "$0")/../.."
source .venv/bin/activate
set -a; . ~/.config/hsc/anthropic.env; set +a
OUT=results/session_v3
COMMON=(--env fixture --fixture-scenario i2:lg7 --episode --thrust-magnitude 0.5 --burn-duration-s 0.25
        --max-observation-age-s 300 --request-timeout-s 60)
python -m hsc.kspdg_loop "${COMMON[@]}" --decider rule --trace-dir $OUT/rule > $OUT/rule.out 2>&1
for rep in 1 2; do
  python -m hsc.kspdg_loop "${COMMON[@]}" --decider hier_rule --hier-layers opus  --trace-dir $OUT/opus  > $OUT/opus_$rep.out 2>&1 &
  python -m hsc.kspdg_loop "${COMMON[@]}" --decider hier_rule --hier-layers haiku --fixture-pace-s 0.25 --trace-dir $OUT/haiku > $OUT/haiku_$rep.out 2>&1 &
  python -m hsc.kspdg_loop "${COMMON[@]}" --decider hier_rule --hier-layers both  --fixture-pace-s 0.25 --trace-dir $OUT/both  > $OUT/both_$rep.out 2>&1 &
done
wait
echo done > $OUT/ALL_DONE
