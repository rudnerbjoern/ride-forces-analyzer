import assert from "node:assert/strict";
import { execFile, spawn } from "node:child_process";
import { once } from "node:events";
import { cp, mkdtemp, mkdir, readFile, rm, writeFile } from "node:fs/promises";
import { createRequire } from "node:module";
import path from "node:path";
import test from "node:test";
import { setTimeout as delay } from "node:timers/promises";
import { fileURLToPath } from "node:url";
import { promisify } from "node:util";

const require = createRequire(import.meta.url);
const sdk = createRequire(require.resolve("@elgato/streamdeck"));
const { WebSocketServer } = sdk("ws");
const uuid = "io.github.rudnerbjoern.ride-forces-analyzer";
const source = fileURLToPath(new URL(`../${uuid}.sdPlugin/`, import.meta.url));
const examples = JSON.parse(await readFile(new URL("fixtures/protocol.json", import.meta.url), "utf8"));

async function waitUntil(predicate, diagnostics = () => "") {
  const deadline = Date.now() + 8000;
  while (!predicate()) {
    assert.ok(Date.now() < deadline, `Plugin event timed out: ${diagnostics()}`);
    await delay(10);
  }
}
async function server() {
  const result = new WebSocketServer({ host: "127.0.0.1", port: 0 });
  await once(result, "listening");
  return result;
}
async function close(host) {
  for (const socket of host.clients) socket.terminate();
  await new Promise(resolve => host.close(resolve));
}

test("the assembled plugin passes official offline validation and includes runtime licenses", async () => {
  const cli = path.join(path.dirname(require.resolve("@elgato/cli/package.json")), "bin/streamdeck.mjs");
  const { stdout, stderr } = await promisify(execFile)(process.execPath,
    [cli, "validate", source, "--no-update-check"]);
  assert.match(stdout + stderr, /Validation successful/);
  const notices = await readFile(path.join(source, "THIRD_PARTY_NOTICES.txt"), "utf8");
  assert.match(notices, /@elgato\/streamdeck 3\.0\.4/);
  assert.match(notices, /Permission is hereby granted/);
  assert.match(await readFile(path.join(source, "LICENSE"), "utf8"), /GNU GENERAL PUBLIC LICENSE/);
  const manifest = JSON.parse(await readFile(path.join(source, "manifest.json"), "utf8"));
  assert.equal(manifest.Actions[0].DisableAutomaticStates, true);
  assert.equal(manifest.Software.MinimumVersion, "7.6");
});

test("built plugin registers with the SDK host, controls the app and recovers without replay", async () => {
  const directory = await mkdtemp(fileURLToPath(new URL("../../../.tmp/stream-deck-artifact-", import.meta.url)));
  const plugin = path.join(directory, `${uuid}.sdPlugin`);
  const data = path.join(directory, "app-data");
  const discovery = path.join(data, "Ride Forces Analyzer", "stream-deck.json");
  await mkdir(path.dirname(discovery), { recursive: true });
  await cp(source, plugin, { recursive: true, filter: filename => !filename.includes(`${path.sep}logs`) });
  const host = await server();
  let backend = await server();
  const hostMessages = [];
  const commands = [];
  let hostSocket, appSocket;
  let snapshot = structuredClone(examples.messages[0]);
  let token = "a".repeat(64);
  const attachBackend = instance => instance.on("connection", socket => {
    socket.once("message", value => {
      assert.deepEqual(JSON.parse(String(value)), { version: 1, token });
      appSocket = socket;
      socket.send('{"transport":"ready","version":1}');
      socket.send(JSON.stringify(snapshot));
      socket.on("message", value => commands.push(JSON.parse(String(value))));
    });
  });
  attachBackend(backend);
  await writeFile(discovery, JSON.stringify({ version: 1, port: backend.address().port, token }));
  host.on("connection", socket => {
    hostSocket = socket;
    socket.on("message", value => hostMessages.push(JSON.parse(String(value))));
  });
  let output = "";
  const info = { application: { version: "7.6.0", platform: "windows", language: "en", font: "Arial", platformVersion: "10" },
    plugin: { uuid, version: "0.1.0.0" }, devices: [{ id: "test-device", name: "Test Neo", type: 7,
      size: { columns: 4, rows: 2 } }], devicePixelRatio: 1,
    colors: { buttonMouseOverBackgroundColor: "#000", buttonPressedBackgroundColor: "#000", buttonPressedBorderColor: "#000", buttonPressedTextColor: "#fff", highlightColor: "#fff" } };
  const child = spawn(process.execPath, ["bin/plugin.js", "-port", String(host.address().port),
    "-pluginUUID", uuid, "-registerEvent", "registerPlugin", "-info", JSON.stringify(info)],
  { cwd: plugin, env: { ...process.env, LOCALAPPDATA: data }, stdio: ["ignore", "pipe", "pipe"] });
  child.stdout.on("data", value => { output += value; });
  child.stderr.on("data", value => { output += value; });
  const event = { action: `${uuid}.control`, context: "test-key", device: "test-device",
    payload: { controller: "Keypad", settings: { operation: "curve.set", curve: "combined" },
      coordinates: { column: 0, row: 0 }, isInMultiAction: false, state: 0 } };
  const send = type => hostSocket.send(JSON.stringify({ ...event, event: type }));
  const title = () => hostMessages.filter(value => value.event === "setTitle").at(-1)?.payload.title ?? "";
  const active = () => hostMessages.filter(value => value.event === "setState").at(-1)?.payload.state;
  const diagnostic = () => `${output}\n${JSON.stringify(hostMessages.slice(-4))}`;
  try {
    await waitUntil(() => hostMessages.some(value => value.event === "registerPlugin") && appSocket, diagnostic);
    assert.equal(hostMessages.find(value => value.event === "registerPlugin").uuid, uuid);
    send("willAppear");
    await waitUntil(() => /Combined\nOff/.test(title()), diagnostic);
    send("keyDown");
    await waitUntil(() => commands.length === 1 && title().includes("Pending"), diagnostic);
    assert.deepEqual(commands[0].action, { name: "curve.set", curve: "combined", enabled: true });
    assert.deepEqual(commands[0].target, snapshot.target);
    assert.equal(active(), 0);
    appSocket.send(JSON.stringify({ version: 1, type: "response", id: commands[0].id, target: commands[0].target, status: "ok" }));
    snapshot.sequence++;
    snapshot.curves[3].active = true;
    appSocket.send(JSON.stringify(snapshot));
    await waitUntil(() => active() === 1 && /Combined\nOn/.test(title()), diagnostic);
    await close(backend);
    await waitUntil(() => title().includes("Offline") && active() === 0, diagnostic);
    backend = await server();
    token = "b".repeat(64);
    snapshot = { ...structuredClone(examples.messages[0]), session_id: "restarted", sequence: 0,
      target: { ...snapshot.target, generation: snapshot.target.generation + 1 } };
    attachBackend(backend);
    await writeFile(discovery, JSON.stringify({ version: 1, port: backend.address().port, token }));
    await waitUntil(() => /Combined\nOff/.test(title()), diagnostic);
    assert.equal(commands.length, 1);
    send("keyDown");
    await waitUntil(() => commands.length === 2, diagnostic);
    assert.deepEqual(commands[1].target, snapshot.target);
    assert.notEqual(commands[1].id, commands[0].id);
    send("willDisappear");
  } finally {
    if (child.exitCode === null && child.signalCode === null) {
      child.kill();
      await once(child, "exit");
    }
    await close(backend);
    await close(host);
    await rm(directory, { recursive: true, force: true });
  }
});
