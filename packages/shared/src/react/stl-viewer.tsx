"use client";

import { useEffect, useRef, useState } from "react";

/**
 * Visualizador 3D de STL (three.js), com girar/zoom. Carrega o three sob demanda para não
 * pesar nas outras telas do painel.
 */
export function StlViewer({ url, color = "#14B8A6", className }: { url: string; color?: string; className?: string }) {
  const mountRef = useRef<HTMLDivElement>(null);
  // material guardado: trocar a cor não recarrega o modelo
  const materialRef = useRef<{ color: { set: (c: string) => void } } | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const mount = mountRef.current;
    if (!mount) return;
    let disposed = false;
    let cleanup = () => {};

    (async () => {
      const THREE = await import("three");
      const { STLLoader } = await import("three/examples/jsm/loaders/STLLoader.js");
      const { OrbitControls } = await import("three/examples/jsm/controls/OrbitControls.js");
      if (disposed) return;

      const width = mount.clientWidth;
      const height = mount.clientHeight;
      const scene = new THREE.Scene();
      const camera = new THREE.PerspectiveCamera(40, width / height, 0.1, 5000);
      const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
      renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
      renderer.setSize(width, height);
      mount.appendChild(renderer.domElement);

      scene.add(new THREE.HemisphereLight(0xffffff, 0x444444, 2.2));
      const sun = new THREE.DirectionalLight(0xffffff, 2);
      sun.position.set(1, 2, 3);
      scene.add(sun);

      const geometry = await new STLLoader().loadAsync(url).catch(() => null);
      if (!geometry) {
        if (!disposed) setError("Não foi possível carregar o modelo 3D.");
        return;
      }
      if (disposed) return;
      geometry.computeVertexNormals();
      geometry.center();
      geometry.rotateX(-Math.PI / 2); // Z do fatiador para cima na tela

      const material = new THREE.MeshStandardMaterial({ color, roughness: 0.55, metalness: 0.05 });
      materialRef.current = material;
      const mesh = new THREE.Mesh(geometry, material);
      scene.add(mesh);

      geometry.computeBoundingSphere();
      const radius = geometry.boundingSphere?.radius ?? 50;
      camera.position.set(radius * 1.6, radius * 1.2, radius * 2);
      const controls = new OrbitControls(camera, renderer.domElement);
      controls.enableDamping = true;
      controls.autoRotate = true;
      controls.autoRotateSpeed = 1.5;

      let frame = 0;
      const loop = () => {
        controls.update();
        renderer.render(scene, camera);
        frame = requestAnimationFrame(loop);
      };
      loop();

      cleanup = () => {
        cancelAnimationFrame(frame);
        controls.dispose();
        geometry.dispose();
        renderer.dispose();
        renderer.domElement.remove();
      };
    })();

    return () => {
      disposed = true;
      materialRef.current = null;
      cleanup();
    };
    // a cor inicial entra na criação; mudanças de cor vão pelo efeito abaixo
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [url]);

  useEffect(() => {
    materialRef.current?.color.set(color);
  }, [color]);

  return (
    <div ref={mountRef} className={className ?? "relative h-80 w-full overflow-hidden rounded-xl border border-border bg-bg"}>
      {error && <p className="absolute inset-0 flex items-center justify-center text-sm text-muted">{error}</p>}
    </div>
  );
}
