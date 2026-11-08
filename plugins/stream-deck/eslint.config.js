import { config } from "@elgato/eslint-config";
import { defineConfig } from "eslint/config";

export default defineConfig({
	basePath: import.meta.dirname,
	files: ["**/*.{js,mjs,cjs,jsx,ts,mts,cts,tsx}"],
	extends: [config.recommended],
});
