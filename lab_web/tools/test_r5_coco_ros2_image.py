# Copyright 2026 Gautham Anil
# SPDX-License-Identifier: Apache-2.0
"""
R5.1: the coco-ros2 image (docker/coco-ros2/), checked without Docker.

What a build cannot be trusted to catch, or would only catch after an hour in CI: the image stays the
slim headless one (no desktop, MoveIt or torch); every file it copies exists; its levels are the
files COCO's recorded STACK runs used (generated here exactly as the image generates them, and
compared with the committed checksums); its bring-up waits for the same Nav2 nodes as
tools/m6/m6f8_run.sh; its bridge cannot publish around cmd_vel_arbiter; the probe and the scripts
parse. The image itself is built, started and measured by .github/workflows/coco-ros2-image.yml.
"""
import hashlib
import importlib.util
import json
import os
import re
import shlex
import socket
import subprocess
import sys

import pytest
import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
D = os.path.join(REPO, 'docker', 'coco-ros2')
DOCKERFILE = open(os.path.join(D, 'Dockerfile'), encoding='utf-8').read()
REGISTRY = json.load(open(os.path.join(D, 'levels.json'), encoding='utf-8'))
WORKFLOW = yaml.safe_load(open(os.path.join(REPO, '.github', 'workflows', 'coco-ros2-image.yml'),
                               encoding='utf-8'))


def sha256(path):
    with open(path, 'rb') as f:
        return hashlib.sha256(f.read()).hexdigest()


def dockerfile_instructions():
    """(instruction, arguments) per logical line, continuations joined, comments dropped."""
    out, cur = [], ''
    for line in DOCKERFILE.splitlines():
        if line.lstrip().startswith('#') and not cur:
            continue
        cur += line.rstrip('\\').strip() + ' ' if line.rstrip().endswith('\\') else line.strip()
        if not line.rstrip().endswith('\\'):
            if cur.strip():
                word, _, rest = cur.strip().partition(' ')
                out.append((word.upper(), rest.strip()))
            cur = ''
    return out


def apt_packages():
    run = next(a for i, a in dockerfile_instructions() if i == 'RUN' and 'apt-get install' in a)
    words = run.split('apt-get install', 1)[1].split('&&', 1)[0].split()
    return {w for w in words if not w.startswith('-')}


# -- the image stays the slim, headless one -------------------------------------------------------

def test_the_runtime_is_ros_base_never_the_desktop():
    assert re.search(r'^ARG ROS_IMAGE=ros:jazzy-ros-base', DOCKERFILE, re.M)
    assert 'desktop' not in ' '.join(a for i, a in dockerfile_instructions() if i in ('FROM', 'ARG'))
    banned = ('moveit', 'torch', 'stable-baselines', 'web-video-server', 'rviz2', 'ros-jazzy-desktop')
    assert not [p for p in apt_packages() if any(b in p for b in banned)], apt_packages()


def test_it_installs_what_the_bring_up_needs():
    need = {'ros-jazzy-ros-gz-sim', 'ros-jazzy-ros-gz-bridge', 'ros-jazzy-gz-ros2-control',
            'ros-jazzy-ros2controlcli', 'ros-jazzy-diff-drive-controller',
            'ros-jazzy-joint-state-broadcaster', 'ros-jazzy-joint-trajectory-controller',
            'ros-jazzy-navigation2', 'ros-jazzy-nav2-bringup', 'ros-jazzy-rmw-cyclonedds-cpp',
            'ros-jazzy-foxglove-bridge', 'ros-jazzy-xacro', 'xvfb', 'tini'}
    assert need <= apt_packages(), need - apt_packages()


def test_every_copied_source_exists_and_is_not_dockerignored():
    ignored = [l.strip().rstrip('/') for l in open(os.path.join(REPO, '.dockerignore'))
               if l.strip() and not l.startswith('#')]
    sources = []
    for i, a in dockerfile_instructions():
        if i == 'COPY' and not a.startswith('--from'):
            sources += a.split()[:-1]
    assert sources
    for s in sources:
        assert os.path.exists(os.path.join(REPO, s)), s
        assert not any(s == g.lstrip('/') or s.startswith(g.lstrip('/') + '/') for g in ignored), s


def test_two_ports_published_and_the_entrypoint_is_coco_ros2_under_tini():
    # 8765: the read-only foxglove_bridge; 8766: the coco.v1 control gateway (R5.2, 2026-11-26)
    ins = dockerfile_instructions()
    assert [a for i, a in ins if i == 'EXPOSE'] == ['8765 8766']
    assert ('ENTRYPOINT', '["/usr/bin/tini", "--", "/opt/coco/bin/coco-ros2"]') in ins
    assert ('CMD', '["--level", "depot"]') in ins
    assert any(i == 'HEALTHCHECK' and '/tmp/coco/ready.json' in a for i, a in ins)


def test_the_dds_and_gz_settings_are_setup_env_sh_ones():
    env = open(os.path.join(REPO, 'setup_env.sh'), encoding='utf-8').read()
    assert 'export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp' in env
    assert 'RMW_IMPLEMENTATION=rmw_cyclonedds_cpp' in DOCKERFILE
    uri = re.search(r"export CYCLONEDDS_URI='([^']+)'", env).group(1)
    assert uri.replace('"', "'") in DOCKERFILE
    assert 'GZ_IP=127.0.0.1' in DOCKERFILE and 'export GZ_IP=127.0.0.1' in env


# -- the levels are the recorded STACK runs' files ------------------------------------------------

def test_the_registry_names_depot_and_every_source_exists():
    aliases = [l['alias'] for l in REGISTRY['levels']]
    assert len(aliases) == len(set(aliases)) and 'depot' in aliases
    depot = next(l for l in REGISTRY['levels'] if l['alias'] == 'depot')
    assert depot['id'] == 'coco_depot_v1' and depot['derivation'] == 5
    for level in REGISTRY['levels']:
        assert os.path.exists(os.path.join(REPO, level['spec'])), level
        for src in level.get('verify', {}).values():
            assert os.path.exists(os.path.join(REPO, src)), src
            assert src in DOCKERFILE or os.path.dirname(src) + '/' in DOCKERFILE, \
                f'the image build must copy {src} to verify against it'


def test_the_recorded_specs_are_the_specs_of_today():
    for level in REGISTRY['levels']:
        rec = level.get('verify', {}).get('record')
        if rec:
            want = json.load(open(os.path.join(REPO, rec)))['spec_sha256']
            assert sha256(os.path.join(REPO, level['spec'])) == want, (level['alias'], rec)


@pytest.fixture(scope='module')
def built_levels(tmp_path_factory):
    """docker/coco-ros2/gen_levels.py, run as the image's build runs it (loaded by path: the
    directory also holds a check.py, which must not shadow anything on sys.path)."""
    out = tmp_path_factory.mktemp('levels')
    spec = importlib.util.spec_from_file_location('coco_ros2_gen_levels', os.path.join(D, 'gen_levels.py'))
    gen_levels = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gen_levels)
    rc = gen_levels.main([REPO, str(out)])
    return rc, out, json.load(open(out / 'index.json'))


def test_the_image_generates_every_level_identical_to_the_records(built_levels):
    rc, out, index = built_levels
    assert rc == 0 and index['all_verified'] is True
    for alias, e in index['levels'].items():
        if e['kind'] == 'world_spec':
            assert e['verification']['result'] == 'identical', (alias, e['verification'])
            assert os.path.exists(e['world']) and os.path.exists(e['map']) and os.path.exists(e['params'])
            # the SDF names its meshes relative to itself: they are laid out beside it
            for rel in e['sha256']:
                if rel.startswith('gazebo/meshes/'):
                    assert os.path.exists(os.path.join(os.path.dirname(e['world']), rel[len('gazebo/'):]))
    assert index['levels']['depot']['verification']['compared'] == len(json.load(open(
        os.path.join(REPO, 'docs/v2/g2/data/g29/coco_depot_v1_outputs_d5.json')))['outputs'])


def test_the_depot_starts_where_the_world_spec_says_with_the_recorded_calibration(built_levels):
    _, _, index = built_levels
    depot = index['levels']['depot']
    spec = yaml.safe_load(open(os.path.join(REPO, 'worlds', 'coco_depot_v1.yaml')))
    assert depot['start'] == {k: float(spec['start'][k]) for k in ('x', 'y', 'theta')}
    # the value G2.9's STACK runs loaded (the runner's `ros2 param get`, committed)
    log = open(os.path.join(REPO, 'docs/v2/g2/data/g29/round_gate/smoke/calibration.txt')).read()
    assert depot['wheel_separation_multiplier'] == float(re.search(r'Double value is: ([0-9.]+)', log).group(1))
    arena = index['levels']['arena']
    assert arena['kind'] == 'stock' and arena['world'] is None and arena['teleport'] is False


def test_level_env_gives_the_entrypoint_quoted_assignments(built_levels):
    _, out, index = built_levels
    r = subprocess.run([sys.executable, os.path.join(D, 'level_env.py'), str(out / 'index.json'),
                        'depot'], capture_output=True, text=True, check=True)
    env = dict(shlex.split(line)[0].split('=', 1) for line in r.stdout.splitlines())
    assert env['LEVEL_ID'] == 'coco_depot_v1' and env['LEVEL_TELEPORT'] == 'true'
    assert float(env['START_X']) == 23.0 and float(env['START_QW']) == 1.0
    assert env['LEVEL_WORLD'] == index['levels']['depot']['world']
    bad = subprocess.run([sys.executable, os.path.join(D, 'level_env.py'), str(out / 'index.json'),
                          'nowhere'], capture_output=True, text=True)
    assert bad.returncode == 2 and 'depot' in bad.stderr


# -- the bring-up is m6f8_run.sh's; nothing gets around the arbiter -------------------------------

def _nav_nodes(text):
    block = re.search(r'NAV_NODES=\(([^)]*)\)', text).group(1)
    return block.split()


def test_nav2_active_means_the_same_nodes_as_the_recorded_runs():
    m6f8 = _nav_nodes(open(os.path.join(REPO, 'tools', 'm6', 'm6f8_run.sh')).read())
    assert _nav_nodes(open(os.path.join(D, 'entrypoint.sh')).read()) == m6f8
    check = open(os.path.join(D, 'check.py')).read()
    listed = re.search(r'NAV_NODES = \[(.*?)\]', check, re.S).group(1)
    assert re.findall(r"'([^']+)'", listed) == m6f8


def test_the_entrypoint_launches_the_arbiter_and_nav2_through_it():
    text = open(os.path.join(D, 'entrypoint.sh')).read()
    assert 'custom_teleop arbiter.launch.py initial_mode:=nav use_sim_time:=true' in text
    assert text.count('nav.launch.py arbiter:=true use_sim_time:=true') == 2
    assert 'gui:=false' in text and '--fast' not in text.replace('never --fast', '')
    assert subprocess.run(['bash', '-n', os.path.join(D, 'entrypoint.sh')]).returncode == 0
    assert subprocess.run(['bash', '-n', os.path.join(REPO, 'tools', 'r5', 'preflight_pull.sh')]).returncode == 0


def test_the_bridge_cannot_publish_around_the_arbiter():
    p = yaml.safe_load(open(os.path.join(D, 'foxglove_bridge.yaml')))['/**']['ros__parameters']
    assert p['port'] == 8765
    # read-only: foxglove_bridge 3.6.3 does not apply client_topic_whitelist (R5_STATUS, 2026-11-26),
    # so no client publishing at all, and no parameters/services (reconfiguring a node)
    assert p['capabilities'] == ['connectionGraph']
    allowed = [re.compile(x) for x in p['client_topic_whitelist']]
    arbiter = open(os.path.join(REPO, 'custom_teleop', 'custom_teleop', 'cmd_vel_arbiter.py')).read()
    wheels = re.search(r"declare_parameter\('output_topic', '([^']+)'\)", arbiter).group(1)
    for t in (wheels, '/cmd_vel', '/cmd_vel_teleop', '/cmd_vel_nav', '/goal_pose'):
        assert not any(r.search(t) for r in allowed), t
    probe = open(os.path.join(D, 'ws_probe.mjs')).read()
    assert "if (caps.includes('clientPublish'))" not in probe          # the advertise is always tried
    assert 'wheel_topic_gains_no_publisher === true' in probe


def test_the_python_scripts_compile():
    for f in ('gen_levels.py', 'level_env.py', 'check.py', 'odom_relay.py'):
        compile(open(os.path.join(D, f)).read(), f, 'exec')


def test_the_probe_parses_and_fails_cleanly_with_no_bridge(tmp_path):
    probe = os.path.join(D, 'ws_probe.mjs')
    assert subprocess.run(['node', '--check', probe]).returncode == 0
    s = socket.socket()
    s.bind(('127.0.0.1', 0))
    port = s.getsockname()[1]
    s.close()                                     # nothing listens there now
    out = tmp_path / 'probe.json'
    r = subprocess.run(['node', probe, f'ws://127.0.0.1:{port}', str(out), '--seconds', '1'],
                       capture_output=True, text=True, timeout=60)
    rec = json.load(open(out))
    assert r.returncode == 1 and rec['pass'] is False and rec['errors']


# -- the workflow pushes only what passed, within the measured disk --------------------------------

def test_the_workflow_pushes_only_after_every_check():
    steps = WORKFLOW['jobs']['image']['steps']
    names = [s.get('name', s.get('uses', '')) for s in steps]
    order = {n: k for k, n in enumerate(names)}
    push = next(k for k, s in enumerate(steps) if s.get('id') == 'push')
    for need in ('Build', 'Measure the image against the budget (before it is started or pushed)',
                 'R5.1 acceptance inside the container',
                 'The bridge from outside the container (ws://127.0.0.1:8765)'):
        assert order[need] < push, need
    assert 'always()' not in str(steps[push].get('if', ''))
    assert int(WORKFLOW['jobs']['image']['env']['MAX_IMAGE_BYTES']) < 7_552_487_424
    assert WORKFLOW['permissions'] == {'contents': 'read', 'packages': 'write'}


def test_the_gateway_is_cocos_own_coco_v1_server_in_remote_mode():
    # R5.2 (Gautham, 2026-11-26): control goes through a gateway restricted by construction; it is
    # coco_web's platform_server, whose publishers are its allowlist (never the wheels)
    text = open(os.path.join(D, 'entrypoint.sh')).read()
    assert 'ros2 run coco_web platform_server' in text and '-p remote:=true' in text
    # remote mode requires code access (platform_server refuses an open remote session): a CSPRNG code
    assert '-p access:=code' in text and '-p access:=open' not in text and 'session_code' in text
    assert '-p session_idle_s:=1800.0' in text     # a visitor's own container: 30 min, not the 60 s demo default
    assert 'origins:=${GW_ORIGINS}' in text and 'https://gauthamcodes.github.io' in text
    srv = open(os.path.join(REPO, 'coco_web', 'coco_web', 'platform_server.py')).read()
    pubs = re.findall(r"create_publisher\(\s*\w+,\s*([^,]+),", srv)
    assert pubs and not any('diff_drive_controller' in t or t.strip() in ("'/cmd_vel'",) for t in pubs), pubs
    probe = open(os.path.join(D, 'gw_probe.mjs')).read()
    for k in ('drive_without_code_refused', 'claim_with_code', 'wheels_only_arbiter', 'teleop_input_is_the_gateway', 'stop_latches_and_holds',
              'goal_reaches_nav2', 'foreign_origin_refused'):
        assert k in probe, k
    wf = open(os.path.join(REPO, '.github', 'workflows', 'coco-ros2-image.yml')).read()
    assert wf.index('gw_probe.mjs') < wf.index('- name: Push to ghcr.io')
