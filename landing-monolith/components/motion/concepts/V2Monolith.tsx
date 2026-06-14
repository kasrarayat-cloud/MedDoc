'use client';

import { useEffect, useRef } from 'react';
import * as THREE from 'three';
import { Headline, HeroCopy, useReducedMotion } from '../shared';

// v2 — the obsidian prism as a REAL 3D object (Three.js): a faceted hexagonal
// prism with edge-lit gold/turquoise glow, internal data streams, pointer-orbit
// rotation and a slow auto-float. Reduced motion → one static frame, no loop.
export function V2Monolith() {
  const reduce = useReducedMotion();
  const mountRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const mount = mountRef.current;
    if (!mount) return;

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(42, 1, 0.1, 100);
    camera.position.set(0, 0, 8.4);

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    mount.appendChild(renderer.domElement);

    const group = new THREE.Group();
    scene.add(group);

    // faceted obsidian prism (hexagonal)
    const geo = new THREE.CylinderGeometry(1.7, 1.7, 4.2, 6, 1);
    const mat = new THREE.MeshStandardMaterial({ color: 0x0a0d13, metalness: 0.6, roughness: 0.32, flatShading: true });
    const prism = new THREE.Mesh(geo, mat);
    group.add(prism);

    // glowing gold/turquoise edges
    const edges = new THREE.LineSegments(
      new THREE.EdgesGeometry(geo),
      new THREE.LineBasicMaterial({ color: 0x3fd8c8, transparent: true, opacity: 0.85 })
    );
    group.add(edges);

    // internal data streams — thin glowing lines inside the prism
    const streams: THREE.Line[] = [];
    for (let i = 0; i < 7; i++) {
      const x = (Math.random() - 0.5) * 1.7;
      const z = (Math.random() - 0.5) * 1.7;
      const pts = [new THREE.Vector3(x, -2.0, z), new THREE.Vector3(x + (Math.random() - 0.5) * 0.5, 2.0, z + (Math.random() - 0.5) * 0.5)];
      const g = new THREE.BufferGeometry().setFromPoints(pts);
      const m = new THREE.LineBasicMaterial({ color: i % 2 ? 0xe8b85c : 0x3fd8c8, transparent: true, opacity: 0.5 });
      const line = new THREE.Line(g, m);
      streams.push(line);
      group.add(line);
    }

    // lights catching the edges
    scene.add(new THREE.AmbientLight(0x223040, 0.7));
    const gold = new THREE.PointLight(0xe8b85c, 90, 30); gold.position.set(5, 4, 5); scene.add(gold);
    const turq = new THREE.PointLight(0x3fd8c8, 80, 30); turq.position.set(-5, -3, 4); scene.add(turq);

    const resize = () => {
      const w = mount.clientWidth, h = mount.clientHeight;
      renderer.setSize(w, h, false);
      camera.aspect = w / h; camera.updateProjectionMatrix();
    };
    resize();
    const ro = new ResizeObserver(resize); ro.observe(mount);

    // pointer-orbit
    const target = { x: 0.2, y: 0 };
    const cur = { x: 0.2, y: 0 };
    const onMove = (e: PointerEvent) => {
      const r = mount.getBoundingClientRect();
      target.x = ((e.clientX - r.left) / r.width - 0.5) * 1.2;
      target.y = ((e.clientY - r.top) / r.height - 0.5) * 0.8;
    };
    if (!reduce) mount.addEventListener('pointermove', onMove);

    let raf = 0;
    const clock = new THREE.Clock();
    const render = () => {
      const t = clock.getElapsedTime();
      cur.x += (target.x - cur.x) * 0.06;
      cur.y += (target.y - cur.y) * 0.06;
      group.rotation.y = cur.x * 1.4 + (reduce ? 0.5 : t * 0.18);
      group.rotation.x = cur.y * 0.9;
      group.position.y = reduce ? 0 : Math.sin(t * 0.7) * 0.12;
      streams.forEach((s, i) => {
        (s.material as THREE.LineBasicMaterial).opacity = reduce ? 0.5 : 0.25 + 0.35 * (0.5 + 0.5 * Math.sin(t * 1.6 + i));
      });
      renderer.render(scene, camera);
      if (!reduce) raf = requestAnimationFrame(render);
    };
    render(); // at least one frame (static under reduced motion)

    // If the browser drops the GL context (tab backgrounding, GPU reset — common
    // on low-end mobile), stop the loop instead of spamming render() at a dead
    // context.
    const onContextLost = (e: Event) => { e.preventDefault(); cancelAnimationFrame(raf); };
    renderer.domElement.addEventListener('webglcontextlost', onContextLost as EventListener);

    return () => {
      cancelAnimationFrame(raf);
      ro.disconnect();
      renderer.domElement.removeEventListener('webglcontextlost', onContextLost as EventListener);
      mount.removeEventListener('pointermove', onMove);
      geo.dispose(); mat.dispose(); edges.geometry.dispose();
      (edges.material as THREE.Material).dispose();
      streams.forEach((s) => { s.geometry.dispose(); (s.material as THREE.Material).dispose(); });
      renderer.dispose();
      if (renderer.domElement.parentNode) renderer.domElement.parentNode.removeChild(renderer.domElement);
    };
  }, [reduce]);

  return (
    <section className={`ml-hero v2 ${reduce ? 'reduce' : ''}`} aria-label="Concept 2 — WebGL monolith">
      <div ref={mountRef} className="v2-canvas" aria-hidden />
      <div className="v2-vignette" aria-hidden />
      <div className="ml-stage v2-stage">
        <div className="ml-copy v2-copy">
          <p className="ml-eyebrow">Ambient clinical documentation</p>
          <Headline />
          <HeroCopy />
        </div>
      </div>
    </section>
  );
}

export default V2Monolith;
