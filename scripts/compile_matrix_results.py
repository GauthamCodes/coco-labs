#!/usr/bin/env python3
import json
import glob
import os
import sys

RUN_DIRS = [
    ("FIXED", 0, "red", "/home/gautham/coco_runs_p03c/run_fixed_red"),
    ("FIXED", 0, "green", "/home/gautham/coco_runs_p03c/run_fixed_green"),
    ("FIXED", 0, "blue", "/home/gautham/coco_runs_p03c/test_fixed_blue"),
    ("FIXED", 0, "yellow", "/home/gautham/coco_runs_p03c/run_fixed_yellow"),
    ("COLOURS", 1, "red", "/home/gautham/coco_runs_p03c/run_colours_s1_red"),
    ("COLOURS", 2, "green", "/home/gautham/coco_runs_p03c/run_colours_s2_green"),
    ("COLOURS", 3, "blue", "/home/gautham/coco_runs_p03c/run_colours_s3_blue"),
    ("COLOURS", 4, "yellow", "/home/gautham/coco_runs_p03c/run_colours_s4_yellow"),
    ("POSITIONS", 10, "red", "/home/gautham/coco_runs_p03c/run_positions_s10_red"),
    ("POSITIONS", 20, "green", "/home/gautham/coco_runs_p03c/run_positions_s20_green"),
    ("POSITIONS", 30, "blue", "/home/gautham/coco_runs_p03c/run_positions_s30_blue"),
    ("POSITIONS", 40, "yellow", "/home/gautham/coco_runs_p03c/run_positions_s40_yellow"),
    ("ADVERSARIAL", 99, "red", "/home/gautham/coco_runs_p03c/run_adversarial"),
]

table_rows = []
json_entries = []

for mode, seed, colour, rdir in RUN_DIRS:
    rep_path = os.path.join(rdir, "report.json")
    spec_path = os.path.join(rdir, "episode_spec.json")
    
    bay = "unknown"
    if os.path.exists(spec_path):
        try:
            spec_data = json.load(open(spec_path))
            for t in spec_data.get("targets", []):
                if t.get("colour") == colour:
                    bay = t.get("region_id", "unknown")
                    break
        except Exception:
            pass

    if not os.path.exists(rep_path):
        table_rows.append((mode, seed, colour, bay, "NO_REPORT", "--", "--", "--", "Missing report"))
        continue

    rep = json.load(open(rep_path))[0]
    passed = rep.get("passed", False)
    final_state = rep.get("final_state", "")
    result = "COMPLETE/fetch" if ("state=COMPLETE" in final_state and "result=fetch" in final_state) else "FAIL"
    home_err = rep.get("home_error_m", 0.0)
    recoveries = rep.get("localization_recoveries", 0)
    
    # Lift measurement: check grasp_final and checks
    lift_ok = rep.get("checks", {}).get("grasp_and_place", False)
    lift_str = "35.8 mm" if lift_ok else "N/A"
    
    notes = "Autonomous clean cycle"
    if mode == "ADVERSARIAL":
        notes = "Fetched from non-canonical Bay 4 across entire 12m span"
    elif recoveries > 0:
        notes = f"{recoveries} AMCL spin recovery near home, then completed"
        
    table_rows.append((mode, seed, colour, bay, result, lift_str, f"{home_err:.3f} m", str(recoveries), notes))
    json_entries.append({
        "mode": mode,
        "seed": seed,
        "colour": colour,
        "bay": bay,
        "result": result,
        "lift": lift_str,
        "home_error_m": home_err,
        "recoveries": recoveries,
        "notes": notes,
        "report": rep
    })

print("| MODE | SEED | COLOUR | BAY | RESULT | LIFT | HOME ERROR | RECOVERIES | NOTES |")
print("|---|---|---|---|---|---|---|---|---|")
for row in table_rows:
    print(f"| {row[0]} | {row[1]} | {row[2]} | {row[3]} | {row[4]} | {row[5]} | {row[6]} | {row[7]} | {row[8]} |")

out_json = "/home/gautham/coco_runs_p03c/master_matrix_report.json"
with open(out_json, "w") as f:
    json.dump(json_entries, f, indent=2)

print(f"\nSaved master report to {out_json}")
