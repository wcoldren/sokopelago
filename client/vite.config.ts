import { defineConfig } from "vitest/config";
import { viteStaticCopy } from "vite-plugin-static-copy";
import { createRequire } from "node:module";

// App version, baked in via `define` so the client can stamp it on POTD rating events
// (read from package.json so there's one source of truth — no manual sync).
const pkg = createRequire(import.meta.url)("./package.json") as { version: string };

// The client renders from bundled per-corpus manifests: tools/build_corpus.py bakes the
// board geometry into apworld/sokopelago/data/<corpus>.json (alongside the solver's
// par/difficulty/solution fields), so the browser fetches /data/<corpus>.json (the seed
// picks the corpus). The canonical authoring sources stay levels/*.xsb (the build input).
export default defineConfig({
  // Relative base so the built site works wherever it's served: "/" locally, under a
  // project-site subpath on GitHub Pages (user.github.io/sokopelago/), and inside an
  // itch.io zip. Asset URLs and import.meta.env.BASE_URL resolve against the document.
  base: "./",
  // Two static pages from one build: the main play loop (index.html) and the offline
  // Puzzle of the Day (potd.html). Redeploys stay idempotent — POTD is just another page.
  build: {
    rollupOptions: {
      input: { main: "index.html", potd: "potd.html" },
    },
  },
  define: {
    __APP_VERSION__: JSON.stringify(pkg.version),
  },
  plugins: [
    viteStaticCopy({
      targets: [{ src: "../apworld/sokopelago/data/*.json", dest: "data" }],
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
