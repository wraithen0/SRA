/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_SRA_API_BASE?: string;
  readonly VITE_SRA_MOCK?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
