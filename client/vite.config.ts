import { defineConfig } from "vitest/config";
import { viteStaticCopy } from "vite-plugin-static-copy";

// The canonical level corpus lives at the repo root (../levels), shared by the
// client now and the apworld later. Copy it into the served output at /levels/
// so the browser can fetch /levels/microban.xsb in both dev and build. The enriched
// manifest (par/difficulty/solution from tools/solve_corpus.py) is served at
// /data/microban.json so the client can read solutions for hints.
export default defineConfig({
  plugins: [
    viteStaticCopy({
      targets: [
        { src: "../levels/*.xsb", dest: "levels" },
        { src: "../apworld/sokopelago/data/microban.json", dest: "data" },
      ],
    }),
  ],
  test: {
    environment: "node",
    include: ["test/**/*.test.ts"],
    coverage: {
      provider: "v8",
      reporter: ["text", "lcov"],
      include: ["src/**"],
    },
  },
});
