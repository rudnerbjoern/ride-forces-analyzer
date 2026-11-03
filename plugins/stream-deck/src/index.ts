import streamDeck from "@elgato/streamdeck";

import { startPlugin } from "./plugin.js";
import { ControlAction } from "./action.js";
import { ControlClient } from "./client.js";
import { HomeAction } from "./home.js";
import { DialControlAction } from "./dial-action.js";
import { StepMode } from "./device-controls.js";
import { StepModeAction } from "./mode-action.js";
import { InfoBarAction } from "./infobar-action.js";

const client = new ControlClient();
const mode = new StepMode();
streamDeck.actions.registerAction(new ControlAction(client));
streamDeck.actions.registerAction(new HomeAction());
streamDeck.actions.registerAction(new DialControlAction(client, mode));
streamDeck.actions.registerAction(new StepModeAction(mode));
streamDeck.actions.registerAction(new InfoBarAction(client));
await startPlugin(streamDeck);
streamDeck.logger.info("Analyzer control plugin connected.");
client.start();
const shutdown = (): never => { client.stop(); process.exit(0); };
process.once("SIGTERM", shutdown);
process.once("SIGINT", shutdown);
