import { describe, expect, it } from "vitest";

import { dataUrlFromModule } from "../src/engine/manifest";

// Regression for the 0.8.2 fix: the POTD page is served one level deep at /sokopelago/potd/, so a
// route-relative `./data/curated.json` resolved to /sokopelago/potd/data/curated.json -> 404. The
// build now anchors the manifest URL to the bundle's own URL (under <app-root>/assets/), so data
// resolves at the app root from ANY page route. These pin that behaviour.
describe("dataUrlFromModule (root-anchored corpus data URL)", () => {
  const ROOT = "https://wcoldren.github.io/sokopelago/data/curated.json";

  it("resolves to the app-root /data from the POTD bundle (the bug)", () => {
    const url = dataUrlFromModule(
      "curated",
      "https://wcoldren.github.io/sokopelago/assets/potd-BCyzf9Y-.js",
    );
    expect(url).toBe(ROOT);
    expect(url).not.toContain("/potd/data/");
  });

  it("resolves to the same app-root /data from the main bundle", () => {
    const url = dataUrlFromModule(
      "curated",
      "https://wcoldren.github.io/sokopelago/assets/main-jpqF9mJj.js",
    );
    expect(url).toBe(ROOT);
  });

  it("works for a site served at the domain root (local / itch) too", () => {
    expect(dataUrlFromModule("microban", "https://example.test/assets/main-abc.js")).toBe(
      "https://example.test/data/microban.json",
    );
  });
});
