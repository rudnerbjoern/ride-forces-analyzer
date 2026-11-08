import type streamDeck from "@elgato/streamdeck";

/**
 * Connect the plugin through the supplied Stream Deck SDK host.
 * @param sdk SDK host exposing the native connection method.
 */
export async function startPlugin(sdk: Pick<typeof streamDeck, "connect">): Promise<void> {
	await sdk.connect();
}
