#!/usr/bin/env python3
# Copyright 2026 Gautham Anil
# SPDX-License-Identifier: Apache-2.0
"""
R3.7: the paper's figures, from committed data.

    python docs/paper/scripts/figures.py [--check]

Each figure writes its data (generated/fig_<name>.json) and its drawing (figures/<name>.pdf).
``--check`` compares the DATA only (rendered bytes differ between matplotlib versions); the
drawing is remade from the data at every build.
"""
import argparse
import json
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[3]
PAPER = REPO / 'docs' / 'paper'
TIER_COLOUR = {'easy': '#4C9F70', 'medium': '#D9A441', 'hard': '#C8553D'}


def fig_tiers():
    """Features of the planning suites' scenarios, by tier (from the frozen suite files)."""
    data = {}
    for sid in ('depot-nav-100', 'depot-long-50', 'depot-narrow-30', 'depot-clutter-50'):
        s = json.loads((REPO / 'coco_lab' / 'coco_lab' / 'benchmarks' / f'{sid}.v1.json')
                       .read_text())
        data[sid] = [{'tier': x['tier'], 'path_length_m': x['features']['path_length_m'],
                      'min_clearance_m': x['features']['min_clearance_m'],
                      'turns': x['features']['turns']} for x in s['scenarios']]
    return data


def draw_tiers(data, out):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, len(data), figsize=(7.0, 1.9), sharey=True)
    for ax, (sid, rows) in zip(axes, data.items()):
        for t, c in TIER_COLOUR.items():
            pts = [r for r in rows if r['tier'] == t]
            ax.scatter([r['path_length_m'] for r in pts], [r['turns'] for r in pts], s=6, c=c,
                       label=t, linewidths=0)
        ax.set_title(sid, fontsize=7)
        ax.set_xlabel('reference path (m)', fontsize=6)
        ax.tick_params(labelsize=6)
    axes[0].set_ylabel('bends', fontsize=6)
    axes[-1].legend(fontsize=5, frameon=False, loc='upper left')
    fig.tight_layout(pad=0.3)
    fig.savefig(out, metadata={'CreationDate': None, 'ModDate': None})
    plt.close(fig)


PLANNER_LABEL = {'stock': 'stock Nav2 (Smac 2D)', 'coco_user_astar_starter': 'A* starter (ROS 2 node)',
                 'coco_user_theta_star': 'Lazy Theta* (ROS 2 node)'}


def fig_corner_cost():
    """Share of received plans with a pose at cost >= 253 (local costmap), per drive (STACK)."""
    d = json.loads((REPO / 'docs' / 'v2' / 'r3' / 'data' / 'a1' / 'costs_summary.json').read_text())
    out = {}
    for name in ('stock', 'coco_user_astar_starter', 'coco_user_theta_star'):
        p = d['planners'][name]
        out[name] = {'reached': f"{p['reached']}/{p['goals']}",
                     'share': {sid: s['share_of_plans_local_ge253'] for sid, s in p['scenarios'].items()
                               if s['share_of_plans_local_ge253'] is not None}}
    return out


def draw_corner_cost(data, out):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    sids = sorted({s for v in data.values() for s in v['share']})
    fig, ax = plt.subplots(figsize=(3.4, 1.9))
    width = 0.26
    colours = {'stock': '#8A8F98', 'coco_user_astar_starter': '#4C9F70', 'coco_user_theta_star': '#C8553D'}
    for i, (name, v) in enumerate(data.items()):
        xs = [k + (i - 1) * width for k, s in enumerate(sids) if s in v['share']]
        ax.bar(xs, [100 * v['share'][s] for s in sids if s in v['share']], width,
               label=f"{PLANNER_LABEL[name]}, reached {v['reached']}", color=colours[name])
        for k, s in enumerate(sids):   # no plan received at all (e.g. 208): say so, never a 0 bar
            if s not in v['share']:
                ax.text(k + (i - 1) * width, 1, 'no plan', rotation=90, fontsize=4.5,
                        ha='center', va='bottom', color=colours[name])
    ax.set_xticks(range(len(sids)))
    ax.set_xticklabels(sids, fontsize=6)
    ax.set_ylabel('plans in cost >= 253 (%)', fontsize=6)
    ax.tick_params(labelsize=6)
    ax.legend(fontsize=5, frameon=False, loc='upper left')
    fig.tight_layout(pad=0.3)
    fig.savefig(out, metadata={'CreationDate': None, 'ModDate': None})
    plt.close(fig)


FIGURES = {'tiers': (fig_tiers, draw_tiers), 'corner_cost': (fig_corner_cost, draw_corner_cost)}


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('--check', action='store_true')
    a = ap.parse_args()
    bad = 0
    for name, (make, draw) in FIGURES.items():
        data = make()
        text = json.dumps(data, sort_keys=True, indent=0) + '\n'
        p = PAPER / 'generated' / f'fig_{name}.json'
        if a.check:
            if not p.is_file() or p.read_text() != text:
                print('DIFFERS', p.relative_to(REPO))
                bad += 1
            continue
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
        (PAPER / 'figures').mkdir(exist_ok=True)
        draw(data, PAPER / 'figures' / f'{name}.pdf')
    print(f'{len(FIGURES)} figure(s) {"checked" if a.check else "written"}')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
