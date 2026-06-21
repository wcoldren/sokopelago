/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Base URL of the POTD ratings backend (Cloudflare Worker). Different origin from the
   *  site, set at build time; unset in dev/preview, where ratings queue locally. */
  readonly VITE_POTD_API?: string;
}

/** App version, injected from package.json by a Vite `define` (see vite.config.ts). */
declare const __APP_VERSION__: string;
