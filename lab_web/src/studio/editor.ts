// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
/**
 * R2.3: the Algorithm Studio's editor -- CodeMirror 6 (MIT; docs/v2/DESIGN_ASSETS.json), loaded
 * only when the Studio opens. Python syntax, line numbers, error markers from the guard and from
 * tracebacks, and completion for coco_lab.api's types, ctx and the message fields.
 */
import { autocompletion, type CompletionContext, type CompletionResult } from '@codemirror/autocomplete';
import { defaultKeymap, history, historyKeymap, indentWithTab } from '@codemirror/commands';
import { globalCompletion, localCompletionSource, python, pythonLanguage } from '@codemirror/lang-python';
import { bracketMatching, HighlightStyle, indentOnInput, syntaxHighlighting } from '@codemirror/language';
import { lintGutter, setDiagnostics, type Diagnostic } from '@codemirror/lint';
import { EditorState } from '@codemirror/state';
import { drawSelection, EditorView, highlightActiveLine, highlightActiveLineGutter, keymap, lineNumbers } from '@codemirror/view';
import { tags as t } from '@lezer/highlight';

/** coco_lab.api's public names (coco_lab/coco_lab/api.py __all__) with one line each. */
const API: [string, string][] = [
  ['Pose2D', 'geometry_msgs/Pose2D(x, y, theta): a planar pose, map frame'],
  ['Twist', 'geometry_msgs/Twist; Twist.of(v, w) drives linear.x and angular.z'],
  ['PoseWithCovariance', 'geometry_msgs/PoseWithCovariance; .of(x, y, theta, var_x, var_y, var_theta, cov_xy)'],
  ['Pose', 'geometry_msgs/Pose(position, orientation); Pose.from_2d(x, y, theta)'],
  ['Point', 'geometry_msgs/Point(x, y, z)'], ['Vector3', 'geometry_msgs/Vector3(x, y, z)'],
  ['Quaternion', 'geometry_msgs/Quaternion(x, y, z, w)'], ['Header', 'std_msgs/Header(stamp, frame_id)'], ['Time', 'builtin_interfaces/Time'],
  ['Costmap', 'nav2_msgs/Costmap: raw costs 0..255; cost(mx, my), world_to_map, map_to_world'],
  ['OccupancyGrid', 'nav_msgs/OccupancyGrid: -1 unknown, 0 free, 100 occupied'],
  ['LaserScan', 'sensor_msgs/LaserScan: ranges, angles(), range_min, range_max'],
  ['Odometry', 'nav_msgs/Odometry: pose.pose, twist.twist (odom frame)'],
  ['RobotState', 'pose (Pose2D, believed), twist, goal, stamp'],
  ['NoValidControl', 'raise from control() when nothing is safe'], ['InvalidPath', 'raise from control() when the path cannot be followed'],
  ['BudgetExceeded', 'raised by ctx.step() past the step budget'],
  ['yaw_of', 'yaw_of(quaternion) -> radians'], ['quaternion_from_yaw', 'quaternion_from_yaw(yaw) -> Quaternion'],
  ['INSCRIBED_INFLATED_OBSTACLE', '253: the robot centre there touches an obstacle'], ['LETHAL_OBSTACLE', '254'],
  ['NO_INFORMATION', '255: unknown'], ['FREE_SPACE', '0'],
];
const MEMBERS: [string, string][] = [
  ['ctx.rng', 'the seeded generator: random, uniform, gauss -- a normal draw, randint, choice, shuffle, sample'],
  ['ctx.robot', 'radius, max_linear, max_angular, max_linear_accel, max_angular_accel, lidar_mount'],
  ['ctx.params', 'your parameters (user.<name> in an experiment)'], ['ctx.config', 'the family’s settings (inflation, connectivity, ...)'],
  ['ctx.memory', 'a dict kept between the calls of one run'], ['ctx.time', 'sim time (s)'], ['ctx.dt', 'the tick (s)'],
  ['ctx.step()', 'count work against the step budget'], ['ctx.initial_pose', 'where a localiser starts'],
  ['ctx.emit(\'expand\', x=, y=)', 'a planner expanded a cell'], ['ctx.emit(\'push\', x=, y=)', 'a cell joined the open list'],
  ['ctx.emit(\'candidate\', points=, cost=, valid=)', 'a trajectory a controller considered'],
  ['ctx.emit(\'lookahead\', x=, y=)', 'the point a controller chases'],
  ['ctx.emit(\'particles\', x=, y=, theta=, weight=)', 'a localiser’s particle cloud'],
  ['ctx.emit(\'note\', text=)', 'a line in the console'],
  ['costmap.cost(mx, my)', 'raw cost 0..255'], ['costmap.world_to_map(x, y)', '(mx, my) or None'], ['costmap.map_to_world(mx, my)', 'the cell centre (x, y)'],
  ['scan.ranges', 'ranges (m)'], ['scan.angles()', 'every beam angle (rad)'], ['state.pose', 'Pose2D, map frame'], ['state.twist', 'the current velocity'],
];

function apiCompletions(cx: CompletionContext): CompletionResult | null {
  const word = cx.matchBefore(/[\w.()']*$/);
  if (!word || (word.from === word.to && !cx.explicit)) return null;
  const text = word.text;
  const options = [...API.map(([label, detail]) => ({ label, detail, type: 'class' })),
    ...MEMBERS.map(([label, detail]) => ({ label, detail, type: 'property', apply: label }))]
    .filter((o) => o.label.startsWith(text.split('(')[0]) || text === '');
  return { from: word.from, options, validFor: /^[\w.]*$/ };
}

const night = HighlightStyle.define([
  { tag: t.keyword, color: 'var(--accent, #ffb547)' }, { tag: [t.string, t.special(t.string)], color: '#9ad7a0' },
  { tag: t.comment, color: 'var(--muted, #8a97a6)', fontStyle: 'italic' }, { tag: [t.number, t.bool, t.null], color: '#ff9e7a' },
  { tag: [t.function(t.variableName), t.function(t.propertyName)], color: '#7cc7ff' }, { tag: t.definition(t.variableName), color: '#e8eef5' },
  { tag: t.className, color: '#f2c879' }, { tag: t.operator, color: '#c7d1dc' },
]);

export interface StudioEditor {
  view: EditorView;
  text(): string;
  setText(s: string): void;
  mark(diags: { line: number; message: string; severity?: 'error' | 'warning' }[]): void;
  goto(line: number): void;
  destroy(): void;
}

export function createEditor(parent: HTMLElement, doc: string, onChange: (s: string) => void, readOnly = false): StudioEditor {
  const view = new EditorView({
    parent,
    state: EditorState.create({
      doc,
      extensions: [
        lineNumbers(), highlightActiveLineGutter(), history(), drawSelection(), indentOnInput(), bracketMatching(),
        highlightActiveLine(), python(), syntaxHighlighting(night), lintGutter(),
        pythonLanguage.data.of({ autocomplete: localCompletionSource }), pythonLanguage.data.of({ autocomplete: globalCompletion }),
        autocompletion({ override: [apiCompletions, localCompletionSource, globalCompletion] }),
        keymap.of([...defaultKeymap, ...historyKeymap, indentWithTab]),
        EditorState.tabSize.of(4), EditorState.readOnly.of(readOnly),
        EditorView.updateListener.of((u) => { if (u.docChanged) onChange(u.state.doc.toString()); }),
        EditorView.contentAttributes.of({ 'aria-label': 'Algorithm code (Python)', spellcheck: 'false', autocapitalize: 'off', autocorrect: 'off' }),
        EditorView.theme({
          '&': { height: '100%', fontSize: '13px', background: 'var(--panel, #121a22)', color: 'var(--fg, #e8eef5)' },
          '.cm-scroller': { fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Consolas, monospace', lineHeight: '1.5' },
          '.cm-gutters': { background: 'var(--panel2, #0e151c)', color: 'var(--muted, #8a97a6)', border: 'none' },
          '.cm-activeLine': { background: 'rgba(255,255,255,0.04)' }, '.cm-activeLineGutter': { background: 'rgba(255,255,255,0.06)' },
          '&.cm-focused .cm-cursor': { borderLeftColor: 'var(--accent, #ffb547)' },
          '.cm-selectionBackground, &.cm-focused .cm-selectionBackground': { background: 'rgba(124,199,255,0.25)' },
        }, { dark: true }),
      ],
    }),
  });
  return {
    view,
    text: () => view.state.doc.toString(),
    setText: (s) => view.dispatch({ changes: { from: 0, to: view.state.doc.length, insert: s } }),
    mark: (diags) => {
      const out: Diagnostic[] = [];
      for (const d of diags) {
        const n = Math.min(Math.max(1, d.line || 1), view.state.doc.lines);
        const line = view.state.doc.line(n);
        out.push({ from: line.from, to: line.to, severity: d.severity ?? 'error', message: d.message });
      }
      view.dispatch(setDiagnostics(view.state, out));
    },
    goto: (n) => {
      const line = view.state.doc.line(Math.min(Math.max(1, n), view.state.doc.lines));
      view.dispatch({ selection: { anchor: line.from }, scrollIntoView: true });
      view.focus();
    },
    destroy: () => view.destroy(),
  };
}
