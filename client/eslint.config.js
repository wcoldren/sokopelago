import js from "@eslint/js";
import tseslint from "typescript-eslint";
import prettier from "eslint-config-prettier";

// Flat config. Type-checked rules (recommendedTypeChecked) use the TS project for
// real type-aware linting; eslint-config-prettier disables stylistic rules so the
// formatter (Prettier) owns layout.
export default tseslint.config(
  { ignores: ["dist/**", "coverage/**", "node_modules/**", "eslint.config.js"] },
  js.configs.recommended,
  ...tseslint.configs.recommendedTypeChecked,
  {
    languageOptions: {
      parserOptions: {
        projectService: true,
        tsconfigRootDir: import.meta.dirname,
      },
    },
  },
  prettier,
);
