-- Phase 4 (Lab 3): coco_2d.lua with global SLAM (loop closure) OFF.
-- Cartographer's documented switch: POSE_GRAPH.optimize_every_n_nodes = 0.
include "coco_2d.lua"
POSE_GRAPH.optimize_every_n_nodes = 0
return options
