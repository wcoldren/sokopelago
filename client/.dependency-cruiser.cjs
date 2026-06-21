// Import-boundary enforcement (wired into the `client-lint` CI job via `npm run depcruise`).
//
// POTD is an OFFLINE page: client/src/potd.ts, everything under client/src/potd/**, and the
// shared client/src/engine/** must NEVER import the AP-connected code (src/ap/**) or the main
// play loop (src/main.ts). That independence is what makes the CI path-filter honest — the POTD
// page ships without pulling in ap/**. This rule fails the build if the boundary is crossed.
module.exports = {
  forbidden: [
    {
      name: "potd-engine-no-ap-or-main",
      severity: "error",
      comment:
        "engine/** and potd (potd.ts + potd/**) must not depend on ap/** or main.ts (offline boundary).",
      from: { path: "^src/(potd\\.ts$|potd/|engine/)" },
      to: { path: "^src/(ap/|main\\.ts$)" },
    },
  ],
  options: {
    doNotFollow: { path: "node_modules" },
    tsConfig: { fileName: "tsconfig.json" },
    // Follow type-only imports too, so a sneaky `import type` across the boundary still fails.
    tsPreCompilationDeps: true,
  },
};
