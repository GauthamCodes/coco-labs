#!/usr/bin/env python3
"""Generate the navigation world and map from config/navigation_world.json.

Map coordinates retain the mission's world-to-map translation. Ramps are
sliced at the flat-ground laser height so AMCL matches real scan boundaries.
Side guards prevent flat-ground routes cutting across the low ramp edges.
"""
import argparse
import json
import math
from pathlib import Path
import re
import xml.etree.ElementTree as ET


def generate(package):
    """Write deterministic SDF and PGM/YAML artifacts in the package."""
    cfg = json.loads((package / 'config/navigation_world.json').read_text())
    # Keep the frozen world's simulator systems and lighting, not its geometry.
    source = re.sub(r'<!--.*?-->', '',
                    (package / 'worlds/coco_world.world').read_text(), flags=re.S)
    sdf = ET.fromstring(source)
    world = sdf.find('world')
    for model in list(world.findall('model')):
        if model.get('name') != 'ground_plane':
            world.remove(model)
        else:
            for size in model.findall('.//plane/size'):
                size.text = '60 60'
    rectangles = []
    for box in cfg['boxes']:
        x, y, z = box['pose']
        sx, sy, sz = box['size']
        rectangles.append((x-sx/2, x+sx/2, y-sy/2, y+sy/2))
        model = ET.SubElement(world, 'model', name=box['name'])
        ET.SubElement(model, 'static').text = 'true'
        ET.SubElement(model, 'pose').text = f'{x} {y} {z} 0 0 0'
        link = ET.SubElement(model, 'link', name='link')
        for kind in ('collision', 'visual'):
            element = ET.SubElement(link, kind, name=kind)
            geometry = ET.SubElement(element, 'geometry')
            shape = ET.SubElement(geometry, 'box')
            ET.SubElement(shape, 'size').text = f'{sx} {sy} {sz}'
            if kind == 'visual':
                material = ET.SubElement(element, 'material')
                for prop in ('ambient', 'diffuse'):
                    ET.SubElement(material, prop).text = '0.55 0.55 0.57 1'
    ET.indent(sdf, space='  ')
    ET.ElementTree(sdf).write(package/'worlds/coco_navigation.world',
                            encoding='utf-8', xml_declaration=True)
    from coco_config.robot import (CHASSIS_GROUND_CLEARANCE,
                                   LIDAR_MOUNT_XYZ, RAMP_ANGLE_DEG)
    scan_height = CHASSIS_GROUND_CLEARANCE + LIDAR_MOUNT_XYZ[2]
    inset = scan_height / math.tan(math.radians(RAMP_ANGLE_DEG))
    bay = cfg['ramp_bays']
    for y in bay['centres_y']:
        rectangles.append((bay['foot_x']+inset,
                           bay['foot_x']+2*bay['run']+bay['platform_length']-inset,
                           y-bay['width']/2, y+bay['width']/2))
    xmin, xmax, ymin, ymax = cfg['bounds']
    res = cfg['resolution']
    # Include the outer wall faces and a surrounding unknown margin.
    ox, oy = xmin-.5, ymin-.5
    width, height = round((xmax-xmin+1)/res), round((ymax-ymin+1)/res)
    pixels = bytearray(width*height)
    for row in range(height):
        y = oy+(height-row-.5)*res
        for col in range(width):
            x = ox+(col+.5)*res
            value = 254 if xmin < x < xmax and ymin < y < ymax else 205
            # Conservatively rasterize cells intersecting a collision rectangle.
            if any(a-res/2 < x < b+res/2 and c-res/2 < y < d+res/2
                   for a,b,c,d in rectangles):
                value = 0
            pixels[row*width+col] = value
    (package/'maps/coco_navigation.pgm').write_bytes(
        f'P5\n{width} {height}\n255\n'.encode()+pixels)
    dx, dy = cfg['world_to_map']
    (package/'maps/coco_navigation.yaml').write_text(
        f'image: coco_navigation.pgm\nmode: trinary\nresolution: {res}\n'
        f'origin: [{ox+dx}, {oy+dy}, 0]\nnegate: 0\n'
        'occupied_thresh: 0.65\nfree_thresh: 0.196\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package', type=Path,
                        default=Path(__file__).resolve().parents[1])
    generate(parser.parse_args().package)
