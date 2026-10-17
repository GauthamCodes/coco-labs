// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
import { useArenaScene } from './sceneCore';
import { ArenaSceneView } from './ArenaSceneView';

/** Compare's scene shell; M5.3 retains the existing presentation. */
export default function CompareScene() {
  const model = useArenaScene();
  return <ArenaSceneView model={model} />;
}
