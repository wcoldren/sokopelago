import { defineConfig } from "vitest/config";
import { viteStaticCopy } from "vite-plugin-static-copy";

// The client renders from a single bundled manifest: tools/build_corpus.py bakes the
// board geometry into apworld/sokopelago/data/microban.json (alongside the solver's
// par/difficulty/solution fields), so the browser fetches only /data/microban.json.
// The canonical authoring source stays levels/microban.xsb (the build input).
export default defineConfig({
  plugins: [
    viteStaticCopy({
      targets: [{ src: "../apworld/sokopelago/data/microban.json", dest: "data" }],
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
