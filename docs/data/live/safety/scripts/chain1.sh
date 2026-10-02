#!/usr/bin/env bash
# The rest of the native validation, one fresh simulator per run.
D="$(cd "$(dirname "$0")" && pwd)"
R=/home/gautham/.claude/jobs/eb997671/tmp/runs
"$D/run.sh" "$R/stop_climb" stop CLIMB yellow 3
"$D/run.sh" "$R/stop_approach" stop APPROACH_TARGET blue 2
"$D/run.sh" "$R/stop_grasp" stop GRASP red 5
"$D/run.sh" "$R/stop_descend" stop DESCEND yellow 3
"$D/run.sh" "$R/nav_native" nav
"$D/run.sh" "$R/fetch_native" fetch blue
echo CHAIN1 DONE
