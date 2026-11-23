import { defineConfig } from 'vite';

export default defineConfig({
  base: './',
  server: {
    host: '127.0.0.1',
    port: 5173,
  },
  build: {
    target: 'es2022',
    // three core alone is ~690 kB minified; everything else is split below that
    chunkSizeWarningLimit: 800,
    rollupOptions: {
      output: {
        manualChunks(id) {
          // three.js core in its own long-cacheable chunk (app code changes don't invalidate it).
          // Only the core build: examples (post-processing etc.) must stay with their lazy importers.
          if (id.includes('/node_modules/three/build/')) return 'three';
          // Lazy (dynamic import from CollisionSystem) – named for readable build output
          if (id.includes('/node_modules/three-mesh-bvh/')) return 'three-mesh-bvh';
          return undefined;
        },
      },
    },
  },
});
