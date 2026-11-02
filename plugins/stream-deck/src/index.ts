import streamDeck from "@elgato/streamdeck";

import { startPlugin } from "./plugin.js";
import { ControlAction } from "./action.js";
import { ControlClient } from "./client.js";
import { HomeAction } from "./home.js";

const client = new ControlClient();
streamDeck.actions.registerAction(new ControlAction(client));
streamDeck.actions.registerAction(new HomeAction());
await startPlugin(streamDeck);
streamDeck.logger.info("Analyzer control plugin connected.");
client.start();
const shutdown = (): never => { client.stop(); process.exit(0); };
process.once("SIGTERM", shutdown);
process.once("SIGINT", shutdown);
