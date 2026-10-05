-- Phase 4 (Lab 3): a DIAGNOSTIC, not a comparison arm.
-- coco_2d.lua (global SLAM on) with the wheel odometry OFF. With odometry
-- on, global SLAM wrecked Cartographer's map on both recorded tours while
-- local SLAM alone mapped them well (measured, docs/RESULTS.md "COCO Lab
-- Phase 4"). If this run's map is good, the odometry's part in the global
-- optimisation is implicated; if it is as bad, it is not.
include "coco_2d.lua"
options.use_odometry = false
return options
