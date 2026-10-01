"""pytest plugin: apply ONE deliberate break to coco_config before tests run.

COCO_BREAK=colours  -> coco_config.robot has no TARGET_COLOURS (loader falls back)
COCO_BREAK=depth    -> coco_config.robot has no CAMERA_DEPTH_CLIP (loader returns None)
COCO_BREAK=arm      -> ARM_LIMITS' shoulder joint renamed
"""
import os


def pytest_configure(config):
    which = os.environ.get('COCO_BREAK', '')
    if which == 'colours':
        from coco_config import robot
        del robot.TARGET_COLOURS
    elif which == 'depth':
        from coco_config import robot
        del robot.CAMERA_DEPTH_CLIP
    elif which == 'arm':
        from coco_config import joint_limits
        limits = dict(joint_limits.ARM_LIMITS)
        limits['m_link1_shoulder'] = limits.pop('m_link1_Revolute-6')
        joint_limits.ARM_LIMITS = limits
    if which:
        print(f'\n[coco_breakers] applied: {which}')
