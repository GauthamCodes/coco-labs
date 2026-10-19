// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
import { useArenaScene } from './sceneCore';
import { PlayHUD } from '../play/PlayHUD';

/** Play's scene shell; M5.3 retains the existing presentation. */
export default function PlayScene() {
  const model = useArenaScene(true);
  return <PlayHUD model={model} />;
}
