import { defineConfig } from "vitest/config";
import { viteStaticCopy } from "vite-plugin-static-copy";

// The canonical level corpus lives at the repo root (../levels), shared by the
// client now and the apworld later. Copy it into the served output at /levels/
// so the browser can fetch /levels/microban.xsb in both dev and build.
export default defineConfig({
  plugins: [
    viteStaticCopy({
      targets: [{ src: "../levels/*.xsb", dest: "levels" }],
    }),
  ],
  test: {
    environment: "node",
    include: ["test/**/*.test.ts"],
  },
});
