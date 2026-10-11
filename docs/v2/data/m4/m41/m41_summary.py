"""M4.1: summarise the feasibility measurements (logs/m41/*.json) into one table + JSON."""
import glob, json, os, statistics, sys
D = '/home/gautham/coco_lab_m4_ws/logs/m41'
rows = []
for p in sorted(glob.glob(f'{D}/*.json')):
    if '.battery_' in p:
        continue
    d = json.load(open(p))
    c = d['conditions']
    rows.append({'run': os.path.basename(p)[:-5], 'camera': d['camera'], 'gpu': d['gpu'], 'renderer': d.get('renderer'),
                 'emulated': d['emulated'], 'phone_viewport': d.get('phone_viewport'), 'cpu_throttle': d['cpu_throttle'],
                 'net': d.get('net'), 'scene': d['scene'], 'fps_median': d.get('fps_median'), 'fps_min': d.get('fps_min'),
                 'p95_frame_ms_median': statistics.median(d['frame_ms_p95_per_second']) if d.get('frame_ms_p95_per_second') else None,
                 'p95_frame_ms_max': max(d['frame_ms_p95_per_second']) if d.get('frame_ms_p95_per_second') else None,
                 'triangles': d.get('triangles'), 'marks_ms': d.get('marks_ms'), 'console_errors': len(d['console_errors']),
                 'ac_start': c['start']['ac_power'], 'ac_end': c['end']['ac_power'], 'profile': c['start']['power_profile']})
retried = sorted(os.path.basename(p) for p in glob.glob(f'{D}/*.battery_*.json'))
out = {'what': 'M4.1 feasibility: the 3D Arena (first conversion) frame rate and 3D cold start', 'runs': rows,
       'discarded_battery_runs': retried}
json.dump(out, open(sys.argv[1], 'w'), indent=1)
for r in rows:
    m = r['marks_ms'] or {}
    print(f"{r['run']:40s} fps {r['fps_median']}/{r['fps_min']} p95 {r['p95_frame_ms_median']}..{r['p95_frame_ms_max']} ms tris {r['triangles']}"
          + (f" | 4G: first comp {m.get('first_computation_shown')} 3D {m.get('world3d_ready')} arena {m.get('arena_ready')}" if r['net'] == '4g' else ''))
print('discarded (AC dropped):', retried)
