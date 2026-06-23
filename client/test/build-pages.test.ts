import { existsSync, readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

// Guards the two-page build: both HTML entry points and the share image must exist and be wired
// into vite's rollup input, so `vite build` keeps emitting dist/index.html, dist/potd/index.html
// and dist/og-card.png (the absolute og:image target). Source-level so it needs no prior build.

const clientDir = fileURLToPath(new URL("..", import.meta.url));
const read = (rel: string): string => readFileSync(new URL(`../${rel}`, import.meta.url), "utf8");

describe("two-page build inputs", () => {
  it("both HTML entry points exist (index + the relocated /potd/)", () => {
    expect(existsSync(`${clientDir}/index.html`)).toBe(true);
    expect(existsSync(`${clientDir}/potd/index.html`)).toBe(true);
    // The old flat path must be gone, so /potd/ is the single source of truth.
    expect(existsSync(`${clientDir}/potd.html`)).toBe(false);
  });

  it("vite config wires both pages as rollup inputs", () => {
    const cfg = read("vite.config.ts");
    expect(cfg).toMatch(/main:\s*["']index\.html["']/);
    expect(cfg).toMatch(/potd:\s*["']potd\/index\.html["']/);
  });

  it("the Open Graph share image is present for Vite to emit to the dist root", () => {
    expect(existsSync(`${clientDir}/public/og-card.png`)).toBe(true);
  });

  it("both pages reference the share image by an absolute URL (crawlers don't resolve base)", () => {
    for (const page of ["index.html", "potd/index.html"]) {
      expect(read(page)).toContain('content="https://wcoldren.github.io/sokopelago/og-card.png"');
    }
  });
});
