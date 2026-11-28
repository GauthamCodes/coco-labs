#!/bin/sh
# R6.A1: where coco-ros2's bytes are, measured inside the built image (CI runs it with --entrypoint sh).
# Prints JSON: installed size per Debian package (dpkg's Installed-Size, KiB), grouped into families, and
# du of the directories a runtime-only image does not need (headers, static libraries, docs, man pages).
set -eu
du_b() { du -sxb "$@" 2>/dev/null | awk '{s += $1} END {print s + 0}'; }
python3 - "$(du_b /)" <<'PY'
import json, re, subprocess, sys
rows = subprocess.run(['dpkg-query', '-W', '-f', '${Installed-Size}\t${Package}\n'], capture_output=True,
                      text=True, check=True).stdout.split('\n')
pk = sorted(((int(s) * 1024, n) for s, n in (r.split('\t') for r in rows if r.strip()) if s.isdigit()), reverse=True)
FAMILIES = [('gazebo', r'^(libgz|gz-|ros-jazzy-(ros-gz|gz-|ros-gz))'), ('qt', r'^(libqt|qml|qt)'),
            ('ogre', r'ogre'), ('nav2', r'^ros-jazzy-(nav2|navigation2|opennav|smac|dwb|nav-2d|costmap)'),
            ('dart_bullet_physics', r'(dart|bullet|libode|libfcl|libccd)'), ('boost', r'^libboost'),
            ('llvm_mesa_gl', r'(llvm|mesa|libgl|libdrm|libegl|libgbm|libvulkan|libgles)'),
            ('python', r'^(python3|libpython)'), ('ros_other', r'^ros-jazzy-'),
            ('opencv_pcl_vtk', r'(opencv|libpcl|vtk)'), ('x11_xvfb', r'(xvfb|libx|x11|xserver|xkb)'),
            ('gcc_build_tools', r'^(gcc|g\+\+|cpp|libgcc-.*-dev|libstdc\+\+-.*-dev|build-essential|make|cmake|git|binutils|libc6-dev|linux-libc-dev|dpkg-dev|python3-colcon|python3-rosdep|python3-vcstool)')]
fam = {f: 0 for f, _ in FAMILIES}; fam['other'] = 0
members = {f: [] for f in fam}
for b, n in pk:
    for f, rx in FAMILIES:
        if re.search(rx, n):
            fam[f] += b; members[f].append(n); break
    else:
        fam['other'] += b; members['other'].append(n)
def du(*paths):
    out = subprocess.run(['sh', '-c', 'du -sxbc ' + ' '.join(paths) + ' 2>/dev/null | tail -1'], capture_output=True, text=True).stdout
    return int(out.split()[0]) if out.strip() else 0
dirs = {p: du(p) for p in ['/opt/ros/jazzy', '/opt/ros/jazzy/include', '/opt/ros/jazzy/lib', '/opt/ros/jazzy/share',
                           '/usr/include', '/usr/share/doc', '/usr/share/man', '/usr/share/locale',
                           '/usr/lib/x86_64-linux-gnu', '/usr/lib/python3', '/usr/local/lib/python3.12',
                           '/usr/lib/gcc', '/usr/share/gz', '/usr/lib/x86_64-linux-gnu/qt5',
                           '/opt/coco', '/opt/coco_ws', '/var/lib/apt', '/var/cache']}
static = subprocess.run(['sh', '-c', "find / -xdev -name '*.a' -type f -printf '%s\\n' 2>/dev/null | awk '{s+=$1} END {print s+0}'"],
                        capture_output=True, text=True).stdout.strip()
# why a heavy package is here: a reverse-dependency chain to a package the Dockerfile installs by name
dep_rows = subprocess.run(['dpkg-query', '-W', '-f', '${Package}\t${Depends}, ${Pre-Depends}, ${Recommends}\n'],
                          capture_output=True, text=True, check=True).stdout.split('\n')
installed = {n for _, n in pk}
rdeps = {}
for r in dep_rows:
    if '\t' not in r:
        continue
    name, deps = r.split('\t', 1)
    for alt in deps.split(','):
        for d in alt.split('|'):
            d = re.sub(r'\(.*?\)|:any|\[.*?\]', '', d).strip()
            if d in installed:
                rdeps.setdefault(d, set()).add(name)
ROOTS = {'ros-jazzy-ros-gz-sim', 'ros-jazzy-ros-gz-bridge', 'ros-jazzy-gz-ros2-control', 'ros-jazzy-controller-manager',
         'ros-jazzy-ros2controlcli', 'ros-jazzy-diff-drive-controller', 'ros-jazzy-joint-state-broadcaster',
         'ros-jazzy-joint-trajectory-controller', 'ros-jazzy-robot-state-publisher', 'ros-jazzy-xacro',
         'ros-jazzy-navigation2', 'ros-jazzy-nav2-bringup', 'ros-jazzy-rmw-cyclonedds-cpp', 'ros-jazzy-foxglove-bridge',
         'xvfb', 'libgl1-mesa-dri', 'libglx-mesa0', 'tini', 'ros-jazzy-std-srvs', 'ros-jazzy-trajectory-msgs',
         'python3-numpy', 'ros-jazzy-ros-core'}


def why(pkg):
    from collections import deque
    prev, q = {pkg: None}, deque([pkg])
    while q:
        cur = q.popleft()
        if cur in ROOTS and cur != pkg:
            chain = [cur]
            while prev[chain[-1]] is not None:
                chain.append(prev[chain[-1]])
            return chain
        for r in sorted(rdeps.get(cur, ())):
            if r not in prev:
                prev[r] = cur
                q.append(r)
    return None


WHY = [n for n in ('libllvm17t64', 'libllvm18', 'libllvm20', 'libamd-comgr2', 'libamdhip64-5', 'libvtk9.1t64',
                   'libboost1.83-dev', 'libopencv-contrib-dev', 'gfortran-13-x86-64-linux-gnu', 'gcc-13-x86-64-linux-gnu',
                   'cmake', 'g' + 'it', 'libpcl-dev', 'libgdal34t64', 'libavcodec-dev', 'libceres-dev', 'libicu-dev',
                   'ros-jazzy-nav2-minimal-tb4-description') if n in installed]
print(json.dumps({'schema': 'coco_ros2.size_breakdown', 'version': 1, 'du_root_bytes': int(sys.argv[1]),
                  'dpkg_total_bytes': sum(b for b, _ in pk), 'packages': len(pk),
                  'families_bytes': dict(sorted(fam.items(), key=lambda kv: -kv[1])),
                  'family_members_top': {f: m[:12] for f, m in members.items()},
                  'top_packages': [[n, b] for b, n in pk[:60]],
                  'dirs_bytes': dirs, 'static_libs_bytes': int(static or 0),
                  'why_installed': {n: why(n) for n in WHY}}, indent=1))
PY
