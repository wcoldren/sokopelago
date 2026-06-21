import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

// Import-boundary guard (complements the dependency-cruiser lint rule): the offline play
// engine and the POTD page must never depend on AP-connected code or the main play loop.
// That independence is what makes the CI path-filter honest — POTD ships without ap/**.

const srcDir = fileURLToPath(new URL("../src", import.meta.url));

/** All .ts files under `dir` (recursive). */
function tsFiles(dir: string): string[] {
  const out: string[] = [];
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const p = join(dir, entry.name);
    if (entry.isDirectory()) out.push(...tsFiles(p));
    else if (entry.name.endsWith(".ts")) out.push(p);
  }
  return out;
}

/** The files subject to the boundary: the shared engine and everything POTD. */
function guardedFiles(): string[] {
  return [
    ...tsFiles(join(srcDir, "engine")),
    join(srcDir, "potd.ts"),
    ...tsFiles(join(srcDir, "potd")),
  ];
}

/** Module specifiers imported/re-exported by `source` (from "…" / import("…")). */
function importSpecifiers(source: string): string[] {
  const specs: string[] = [];
  const re = /(?:import|export)[^'"]*?from\s*["']([^"']+)["']|import\(\s*["']([^"']+)["']\s*\)/g;
  let m: RegExpExecArray | null;
  while ((m = re.exec(source)) !== null) specs.push(m[1] ?? m[2]);
  return specs;
}

const FORBIDDEN = /(^|\/)ap\/|(^|\/)main(\.ts)?$/;

describe("engine/potd import boundary", () => {
  it("no guarded file imports from ap/** or main", () => {
    const violations: string[] = [];
    for (const file of guardedFiles()) {
      for (const spec of importSpecifiers(readFileSync(file, "utf8"))) {
        if (FORBIDDEN.test(spec)) violations.push(`${file} -> ${spec}`);
      }
    }
    expect(violations).toEqual([]);
  });

  it("the FORBIDDEN matcher actually catches cross-boundary specifiers", () => {
    // Guards the guard: if these stop matching, the scan above is silently useless.
    expect(FORBIDDEN.test("./ap/session")).toBe(true);
    expect(FORBIDDEN.test("../ap/slotData")).toBe(true);
    expect(FORBIDDEN.test("./main")).toBe(true);
    expect(FORBIDDEN.test("../main.ts")).toBe(true);
    expect(FORBIDDEN.test("./engine/board")).toBe(false);
    expect(FORBIDDEN.test("./potd/select")).toBe(false);
  });
});
