// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * The help overlay (M4.5; README §5.5, H): every action and its keys, each
 * remappable (click, then press the new key; Escape cancels), and the
 * settings the preferences module keeps: reduced motion, the motor sound,
 * the wheel-speed bars and tank mode.
 */

import { useEffect, useState } from 'react';

import { ACTIONS, keyLabel, type Action, type Bindings } from './controls';

export interface Settings { motion: boolean; sound: boolean; bars: boolean; tank: boolean }

export interface HelpProps {
  bindings: Bindings;
  settings: Settings;
  coarse: boolean;
  onRebind: (a: Action, code: string) => void;
  onReset: () => void;
  onSetting: (k: keyof Settings, v: boolean) => void;
  onClose: () => void;
}

const SETTING_LABEL: Record<keyof Settings, string> = {
  motion: 'Reduced motion (camera cuts instead of moves)',
  sound: 'Motor sound (pitched to the wheel speed)',
  bars: 'Wheel-speed bars',
  tank: 'Tank mode on a touch screen (a slider per side)',
};

export function Help(p: HelpProps) {
  const [waiting, setWaiting] = useState<Action | null>(null);
  useEffect(() => {
    if (!waiting) return undefined;
    // capture the next key before the page's own handler sees it
    const grab = (e: KeyboardEvent) => {
      e.preventDefault();
      e.stopImmediatePropagation();
      if (e.code !== 'Escape') p.onRebind(waiting, e.code);
      setWaiting(null);
    };
    window.addEventListener('keydown', grab, { capture: true });
    return () => window.removeEventListener('keydown', grab, { capture: true });
  }, [waiting, p]);
  return (
    <div className="help-overlay" role="dialog" aria-modal="true" aria-label="Controls and settings" data-testid="help">
      <div className="help-card">
        <div className="help-head">
          <h2>Controls</h2>
          <button type="button" className="seg-btn" onClick={p.onClose} data-testid="help-close">Close</button>
        </div>
        <table className="help-keys">
          <tbody>
            {ACTIONS.map((a) => (
              <tr key={a.id}>
                <td>{a.label}</td>
                <td>{p.bindings[a.id].map(keyLabel).join(' / ')}</td>
                <td>
                  <button type="button" className="seg-btn" data-testid={`rebind-${a.id}`} onClick={() => setWaiting(a.id)}
                    aria-pressed={waiting === a.id}>{waiting === a.id ? 'press a key…' : 'change'}</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <p>
          <button type="button" className="seg-btn" onClick={p.onReset} data-testid="rebind-reset">Default keys</button>
          {' '}The mouse orbits and zooms; a click on the floor sets an autonomous goal. The game menu also accepts a goal by keyboard. Tab on the focused arena switches autonomy and continues to the next control.
          {p.coarse && ' On a touch screen: the joystick drives, a tap on the floor sets a goal, two fingers orbit and zoom.'}
        </p>
        <h2>Settings</h2>
        {(Object.keys(SETTING_LABEL) as (keyof Settings)[]).map((k) => (
          <label key={k} className="layer-toggle help-setting">
            <input type="checkbox" checked={p.settings[k]} data-testid={`setting-${k}`}
              onChange={(e) => p.onSetting(k, e.target.checked)} />{SETTING_LABEL[k]}
          </label>
        ))}
        <p className="muted">Kept in this browser only (local storage); nothing is sent anywhere.</p>
      </div>
    </div>
  );
}
