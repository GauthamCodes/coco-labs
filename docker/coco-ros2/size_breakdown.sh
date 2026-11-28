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
print(json.dumps({'schema': 'coco_ros2.size_breakdown', 'version': 1, 'du_root_bytes': int(sys.argv[1]),
                  'dpkg_total_bytes': sum(b for b, _ in pk), 'packages': len(pk),
                  'families_bytes': dict(sorted(fam.items(), key=lambda kv: -kv[1])),
                  'family_members_top': {f: m[:12] for f, m in members.items()},
                  'top_packages': [[n, b] for b, n in pk[:60]],
                  'dirs_bytes': dirs, 'static_libs_bytes': int(static or 0)}, indent=1))
PY
