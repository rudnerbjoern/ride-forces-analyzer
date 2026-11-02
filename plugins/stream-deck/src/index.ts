import streamDeck from "@elgato/streamdeck";

import { startPlugin } from "./plugin.js";
import { ControlAction } from "./action.js";
import { ControlClient } from "./client.js";

const client = new ControlClient();
streamDeck.actions.registerAction(new ControlAction(client));
await startPlugin(streamDeck);
streamDeck.logger.info("Analyzer control plugin connected.");
client.start();
const shutdown = (): never => { client.stop(); process.exit(0); };
process.once("SIGTERM", shutdown);
process.once("SIGINT", shutdown);
