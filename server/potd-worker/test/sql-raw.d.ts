// Ambient (script-context, no imports) declaration for Vite's `?raw` text imports, so the test
// can `import schemaSql from "../src/schema.sql?raw"`. Kept separate from worker-env.d.ts because
// a wildcard `declare module` is only global in a file with no top-level import/export.
declare module "*.sql?raw" {
  const content: string;
  export default content;
}
