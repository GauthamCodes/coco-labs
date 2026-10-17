// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
import {it,expect} from 'vitest';
import * as THREE from 'three';
import {clearCameraPosition,WORLD_LAYER} from '../src/arena/render/scene3d';
it('the follow camera stops before a warehouse wall and releases into open space',()=>{
 const wall=new THREE.Mesh(new THREE.BoxGeometry(.2,4,4),new THREE.MeshBasicMaterial({side:THREE.DoubleSide}));wall.position.set(2,0,2);wall.layers.set(WORLD_LAYER);wall.updateMatrixWorld(true);
 const target=new THREE.Vector3(0,0,1),desired=new THREE.Vector3(5,0,3);
 const clipped=clearCameraPosition(target,desired,wall);
 expect(clipped.x).toBeLessThan(1.9);expect(clipped.x).toBeGreaterThan(1.5);
 expect(clipped.z).toBeGreaterThan(1);
 wall.position.y=10;wall.updateMatrixWorld(true);
 expect(clearCameraPosition(target,desired,wall).toArray()).toEqual(desired.toArray());
});
