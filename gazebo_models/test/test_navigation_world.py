"""Geometry/map agreement and footprint-clear connectivity for every mission bay."""
import importlib.util
import json
from pathlib import Path
import shutil
import xml.etree.ElementTree as ET

from coco_config.robot import TARGETS, RAMP_WIDTH, RAMP_RUN, RAMP_FOOT_X, DESCENT_RAMP_RUN
import numpy as np
from PIL import Image
from scipy.ndimage import distance_transform_edt, label
import yaml

PACKAGE = Path(__file__).resolve().parents[1]


def test_generated_artifacts_are_reproducible(tmp_path):
    for folder in ('config', 'worlds', 'maps'):
        (tmp_path / folder).mkdir()
    for path in ('config/navigation_world.json', 'worlds/coco_world.world'):
        shutil.copyfile(PACKAGE/path, tmp_path/path)
    spec = importlib.util.spec_from_file_location(
        'generator', PACKAGE/'scripts/gen_navigation_world.py')
    generator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(generator)
    generator.generate(tmp_path)
    for path in ('worlds/coco_navigation.world', 'maps/coco_navigation.pgm',
                 'maps/coco_navigation.yaml'):
        assert (tmp_path/path).read_bytes() == (PACKAGE/path).read_bytes()


def test_static_collisions_and_map_boundaries_agree():
    cfg = json.loads((PACKAGE/'config/navigation_world.json').read_text())
    models = ET.parse(PACKAGE/'worlds/coco_navigation.world').findall('world/model')
    boxes = {m.get('name'): m for m in models if m.get('name') != 'ground_plane'}
    assert set(boxes) == {b['name'] for b in cfg['boxes']}
    for box in cfg['boxes']:
        model = boxes[box['name']]
        assert list(map(float, model.findtext('pose').split()))[:3] == box['pose']
        assert list(map(float, model.findtext('.//collision/geometry/box/size').split())) == box['size']
    bay = cfg['ramp_bays']
    assert bay['descent_run'] == DESCENT_RAMP_RUN
    assert bay['centres_y'] == [t.lane_y for t in TARGETS]
    assert (bay['foot_x'], bay['run'], bay['width']) == (RAMP_FOOT_X, RAMP_RUN, RAMP_WIDTH)


def test_all_bays_and_rooms_connect_with_robot_clearance():
    meta = yaml.safe_load((PACKAGE/'maps/coco_navigation.yaml').read_text())
    grid = np.array(Image.open(PACKAGE/'maps'/meta['image']))
    assert grid.shape == (380, 500)
    assert meta['resolution'] == .05
    # 0.30 m centre clearance exceeds the unchanged local inscribed radius.
    clear = distance_transform_edt(grid == 254)*meta['resolution'] > .30
    components, _ = label(clear)
    def component(x, y):
        col = int((x+2-meta['origin'][0])/.05)
        row = grid.shape[0]-1-int((y-meta['origin'][1])/.05)
        return components[row, col]
    home = component(-2, 0)
    assert home
    for target in TARGETS:
        assert component(.5, target.lane_y) == home
        assert component(6.8, target.lane_y) == home
    for point in [(-6,0), (-6,7), (-6,-7), (14,0), (12,5), (14,-7)]:
        assert component(*point) == home


def test_ramp_interiors_are_unknown_not_false_occupied_surfaces():
    meta = yaml.safe_load((PACKAGE/'maps/coco_navigation.yaml').read_text())
    grid = np.array(Image.open(PACKAGE/'maps'/meta['image']))
    for target in TARGETS:
        col = int((4.05+2-meta['origin'][0])/.05)
        row = grid.shape[0]-1-int((target.lane_y-meta['origin'][1])/.05)
        assert grid[row, col] == 205


def test_downhill_runout_is_flat_and_connects_to_return_gate():
    meta = yaml.safe_load((PACKAGE/'maps/coco_navigation.yaml').read_text())
    grid = np.array(Image.open(PACKAGE/'maps'/meta['image']))
    # The physical wedge now ends at X=6.0, leaving at least 0.5 m of
    # flat travel even when the existing exit goal accepts its tolerance.
    from coco_config.robot import RAMP_SUMMIT_X, PLATFORM_LEN
    foot = RAMP_SUMMIT_X + PLATFORM_LEN + DESCENT_RAMP_RUN
    assert foot == 6.0
    for target in TARGETS:
        row = grid.shape[0]-1-int((target.lane_y-meta['origin'][1])/.05)
        for x in np.arange(foot, 6.81, .05):
            col = int((x+2-meta['origin'][0])/.05)
            assert grid[row, col] == 254
