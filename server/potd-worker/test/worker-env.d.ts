import type { Env } from "../src/index";

declare module "cloudflare:test" {
  // The Miniflare bindings from vitest.config.ts surface on `env` from cloudflare:test.
  interface ProvidedEnv extends Env {}
}
