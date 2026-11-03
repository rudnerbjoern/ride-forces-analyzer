import assert from "node:assert/strict";
import { once } from "node:events";
import { mkdtemp, rm, writeFile } from "node:fs/promises";
import { createRequire } from "node:module";
import path from "node:path";
import test from "node:test";
import { setTimeout as delay } from "node:timers/promises";
import { fileURLToPath } from "node:url";

import { AnalyzerTransport, endpointPath } from "../dist/transport.js";

const require = createRequire(import.meta.url);
const sdk = createRequire(require.resolve("@elgato/streamdeck"));
const { WebSocketServer } = sdk("ws");

async function waitUntil(condition) {
  const deadline = Date.now() + 6000;
  while (!condition()) {
    assert.ok(Date.now() < deadline, "Transport condition timed out");
    await delay(10);
  }
}

test("discovery paths match native Windows and macOS data locations", () => {
  assert.equal(endpointPath("win32", { LOCALAPPDATA: "C:\\Local" }, "C:\\User"),
    "C:\\Local\\Ride Forces Analyzer\\stream-deck.json");
  assert.equal(endpointPath("win32", {}, "C:\\User"),
    "C:\\User\\AppData\\Local\\Ride Forces Analyzer\\stream-deck.json");
  assert.equal(endpointPath("darwin", {}, "/Users/example"),
    "/Users/example/Library/Application Support/Ride Forces Analyzer/stream-deck.json");
  assert.throws(() => endpointPath("unsupported"), /Windows or macOS/);
});

test("client authenticates, exchanges state and rediscovers after endpoint replacement", async () => {
  const directory = await mkdtemp(fileURLToPath(new URL("../../../.tmp/stream-deck-node-", import.meta.url)));
  const filename = path.join(directory, "endpoint.json");
  const connections = [];
  const messages = [];
  const commands = [];
  const client = new AnalyzerTransport(filename, message => messages.push(message),
    connected => connections.push(connected));
  let server;
  async function start(token, state) {
    const host = new WebSocketServer({ host: "127.0.0.1", port: 0 });
    await once(host, "listening");
    host.on("connection", socket => {
      socket.once("message", hello => {
        assert.deepEqual(JSON.parse(hello.toString()), { version: 1, token });
        socket.send('{"transport":"ready","version":1}');
        socket.send(state);
        socket.on("message", message => commands.push(message.toString()));
      });
    });
    await writeFile(filename, JSON.stringify({ version: 1, token, port: host.address().port }));
    return host;
  }
  async function close(host) {
    for (const peer of host.clients) peer.terminate();
    await new Promise(resolve => host.close(resolve));
  }
  try {
    assert.equal(client.send("not queued"), false);
    client.start();
    client.start();
    await delay(20);
    assert.equal(client.connected, false);
    await writeFile(filename, '{"version":2,"port":1,"token":"invalid"}');
    await delay(1100);
    assert.equal(client.connected, false);
    server = await start("a".repeat(64), "initial state");
    await waitUntil(() => messages.length === 1);
    assert.equal(client.connected, true);
    assert.equal(client.send("command"), true);
    await waitUntil(() => commands.length === 1);
    assert.deepEqual(messages, ["initial state"]);
    await close(server);
    server = undefined;
    await waitUntil(() => !client.connected);
    assert.equal(client.send("not replayed"), false);
    await delay(1100);
    assert.equal(client.connected, false);
    server = await start("b".repeat(64), "replacement state");
    await waitUntil(() => messages.length === 2);
    assert.deepEqual(messages, ["initial state", "replacement state"]);
    assert.deepEqual(commands, ["command"]);
    client.stop();
    assert.deepEqual(connections, [true, false, true, false]);
    assert.equal(client.send("stopped"), false);
  } finally {
    client.stop();
    if (server) await close(server);
    await rm(directory, { recursive: true, force: true });
  }
});
