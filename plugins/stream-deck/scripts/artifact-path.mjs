import { fileURLToPath } from "node:url";

/** Build outside the source folder, which may already be linked to installed Stream Deck software. */
export const pluginOutput = fileURLToPath(
	new URL("../../../.tmp/stream-deck/io.github.rudnerbjoern.ride-forces-analyzer.sdPlugin/", import.meta.url),
);

/** Keep the explicitly installed copy independent of disposable build/test output. */
export const pluginInstallation = fileURLToPath(
	new URL("../../../.tmp/stream-deck-installed/io.github.rudnerbjoern.ride-forces-analyzer.sdPlugin/", import.meta.url),
);
