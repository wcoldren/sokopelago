import { defineWorkersConfig } from "@cloudflare/vitest-pool-workers/config";

// Runs the Worker tests inside workerd (Miniflare) with a real local D1 binding, so the
// SQL the Worker issues is exercised for real. The bindings here mirror wrangler.toml's,
// with a test-only ALLOWED_ORIGINS so the CORS allow-list can be asserted.
export default defineWorkersConfig({
  test: {
    poolOptions: {
      workers: {
        miniflare: {
          compatibilityDate: "2025-01-01",
          d1Databases: ["DB"],
          bindings: { ALLOWED_ORIGINS: "https://example.com" },
        },
      },
    },
  },
});
