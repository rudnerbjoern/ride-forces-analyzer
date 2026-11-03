import type streamDeck from "@elgato/streamdeck";

/** Connect the plugin using the supplied Stream Deck SDK host. */
export async function startPlugin(sdk: Pick<typeof streamDeck, "connect">): Promise<void> {
    await sdk.connect();
}
