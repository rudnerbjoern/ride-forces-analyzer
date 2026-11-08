import { Uint8ArrayReader, Uint8ArrayWriter, ZipReader } from "@zip.js/zip.js";
import assert from "node:assert/strict";
import { execFile, spawn } from "node:child_process";
import { once } from "node:events";
import { cp, mkdir, mkdtemp, readdir, readFile, rm, writeFile } from "node:fs/promises";
import { createRequire } from "node:module";
import path from "node:path";
import test from "node:test";
import { setTimeout as delay } from "node:timers/promises";
import { fileURLToPath } from "node:url";
import { promisify } from "node:util";

import { pluginOutput as source } from "../scripts/artifact-path.mjs";
import { CONTROL_VERSION, TRANSPORT_VERSION } from "./helpers/versions.mjs";

const require = createRequire(import.meta.url);
const sdk = createRequire(require.resolve("@elgato/streamdeck"));
const { WebSocketServer } = sdk("ws");
const uuid = "io.github.rudnerbjoern.ride-forces-analyzer";
const pluginVersion = JSON.parse(await readFile(new URL("../package.json", import.meta.url), "utf8")).version;
const examples = JSON.parse(
	await readFile(new URL("../../../tests/fixtures/stream_deck_protocol.json", import.meta.url), "utf8"),
);

/**
 * Wait for a plugin event with bounded polling and useful failure diagnostics.
 * @param {function(): boolean} predicate Condition indicating that the expected event has occurred.
 * @param {function(): string} diagnostics Callback describing the observed state if polling times out.
 */
async function waitUntil(predicate, diagnostics = () => "") {
	const deadline = Date.now() + 8000;
	while (!predicate()) {
		assert.ok(Date.now() < deadline, `Plugin event timed out: ${diagnostics()}`);
		await delay(10);
	}
}
/**
 * Start a local ephemeral WebSocket host for SDK integration tests.
 * @returns {Promise<object>} Listening WebSocket server.
 */
async function server() {
	const result = new WebSocketServer({ host: "127.0.0.1", port: 0 });
	await once(result, "listening");
	return result;
}
/**
 * Terminate test peers and await WebSocket server shutdown.
 * @param {object} host Local WebSocket server whose clients must be closed.
 */
async function close(host) {
	for (const socket of host.clients) socket.terminate();
	await new Promise((resolve) => host.close(resolve));
}

test("official offline packing preserves the validated runtime, licenses and three profiles", async () => {
	const pack = fileURLToPath(new URL("../scripts/pack-plugin.mjs", import.meta.url));
	const directory = await mkdtemp(fileURLToPath(new URL("../../../.tmp/stream-deck-package-test-", import.meta.url)));
	try {
		const { stdout, stderr } = await promisify(execFile)(process.execPath, [pack, "--output", directory]);
		assert.match(stdout + stderr, /Successfully packaged plugin/);
		const archive = path.join(directory, "Ride-Forces-Analyzer.streamDeckPlugin");
		assert.deepEqual(await readdir(directory), ["Ride-Forces-Analyzer.streamDeckPlugin"]);
		const original = await readFile(archive);
		await assert.rejects(promisify(execFile)(process.execPath, [pack, "--output", directory]), (error) =>
			error.stderr.includes("Plugin archive already exists"),
		);
		assert.deepEqual(await readFile(archive), original);
		await promisify(execFile)(process.execPath, [pack, "--output", directory, "--force"]);
		const reader = new ZipReader(new Uint8ArrayReader(await readFile(archive)));
		try {
			const entries = (await reader.getEntries()).filter((entry) => !entry.directory);
			const files = (await readdir(source, { recursive: true, withFileTypes: true }))
				.filter((entry) => entry.isFile())
				.map((entry) => path.relative(source, path.join(entry.parentPath, entry.name)).replaceAll("\\", "/"));
			assert.deepEqual(
				entries.map((entry) => entry.filename).sort(),
				files.map((name) => `${uuid}.sdPlugin/${name}`).sort(),
			);
			for (const entry of entries) {
				assert.deepEqual(
					Buffer.from(await entry.getData(new Uint8ArrayWriter())),
					await readFile(path.join(source, entry.filename.slice(`${uuid}.sdPlugin/`.length))),
					entry.filename,
				);
			}
			for (const name of [
				"bin/plugin.js",
				"LICENSE",
				"THIRD_PARTY_NOTICES.txt",
				"profiles/plus.streamDeckProfile",
				"profiles/neo.streamDeckProfile",
				"profiles/mobile.streamDeckProfile",
			]) {
				assert.ok(files.includes(name), `Missing distributable content: ${name}`);
			}
		} finally {
			await reader.close();
		}
	} finally {
		await rm(directory, { recursive: true, force: true });
	}
	const notices = await readFile(path.join(source, "THIRD_PARTY_NOTICES.txt"), "utf8");
	assert.match(notices, /@elgato\/streamdeck 3\.0\.4/);
	assert.match(notices, /Permission is hereby granted/);
	assert.match(await readFile(path.join(source, "LICENSE"), "utf8"), /GNU GENERAL PUBLIC LICENSE/);
	const manifest = JSON.parse(await readFile(path.join(source, "manifest.json"), "utf8"));
	assert.equal(manifest.Actions[0].DisableAutomaticStates, true);
	assert.equal(manifest.Software.MinimumVersion, "7.6");
	assert.deepEqual(manifest.OS, [
		{ Platform: "windows", MinimumVersion: "10" },
		{ Platform: "mac", MinimumVersion: "15" },
	]);
	assert.equal(manifest.CodePath, "bin/plugin.js");
	assert.equal(manifest.CodePathWin, undefined);
	assert.equal(manifest.CodePathMac, undefined);
	assert.equal(manifest.Version, `${pluginVersion}.0`);
});

test("built plugin registers with the SDK host, controls the app and recovers without replay", async () => {
	const directory = await mkdtemp(fileURLToPath(new URL("../../../.tmp/stream-deck-artifact-", import.meta.url)));
	const plugin = path.join(directory, `${uuid}.sdPlugin`);
	const data = path.join(directory, "app-data");
	const discovery = path.join(data, "Ride Forces Analyzer", "stream-deck.json");
	await mkdir(path.dirname(discovery), { recursive: true });
	await cp(source, plugin, { recursive: true, filter: (filename) => !filename.includes(`${path.sep}logs`) });
	const host = await server();
	let backend = await server();
	const hostMessages = [];
	const commands = [];
	let hostSocket, appSocket;
	let snapshot = structuredClone(examples.messages[0]);
	let token = "a".repeat(64);
	const attachBackend = (instance) =>
		instance.on("connection", (socket) => {
			socket.once("message", (value) => {
				assert.deepEqual(JSON.parse(String(value)), { version: TRANSPORT_VERSION, token });
				appSocket = socket;
				socket.send(JSON.stringify({ transport: "ready", version: TRANSPORT_VERSION }));
				socket.send(JSON.stringify(snapshot));
				socket.on("message", (value) => commands.push(JSON.parse(String(value))));
			});
		});
	attachBackend(backend);
	await writeFile(discovery, JSON.stringify({ version: TRANSPORT_VERSION, port: backend.address().port, token }));
	host.on("connection", (socket) => {
		hostSocket = socket;
		socket.on("message", (value) => hostMessages.push(JSON.parse(String(value))));
	});
	let output = "";
	const info = {
		application: { version: "7.6.0", platform: "windows", language: "en", font: "Arial", platformVersion: "10" },
		plugin: { uuid, version: `${pluginVersion}.0` },
		devices: [
			{ id: "test-device", name: "Test Neo", type: 9, size: { columns: 4, rows: 2 } },
			{ id: "test-plus", name: "Test Plus", type: 7, size: { columns: 4, rows: 2 } },
			{ id: "test-plus-2", name: "Second Plus", type: 7, size: { columns: 4, rows: 2 } },
		],
		devicePixelRatio: 1,
		colors: {
			buttonMouseOverBackgroundColor: "#000",
			buttonPressedBackgroundColor: "#000",
			buttonPressedBorderColor: "#000",
			buttonPressedTextColor: "#fff",
			highlightColor: "#fff",
		},
	};
	const child = spawn(
		process.execPath,
		[
			"bin/plugin.js",
			"-port",
			String(host.address().port),
			"-pluginUUID",
			uuid,
			"-registerEvent",
			"registerPlugin",
			"-info",
			JSON.stringify(info),
		],
		{ cwd: plugin, env: { ...process.env, LOCALAPPDATA: data }, stdio: ["ignore", "pipe", "pipe"] },
	);
	child.stdout.on("data", (value) => {
		output += value;
	});
	child.stderr.on("data", (value) => {
		output += value;
	});
	const event = {
		action: `${uuid}.control`,
		context: "test-key",
		device: "test-device",
		payload: {
			controller: "Keypad",
			settings: { operation: "curve.set", curve: "combined" },
			coordinates: { column: 0, row: 0 },
			isInMultiAction: false,
			state: 0,
		},
	};
	const send = (type) => hostSocket.send(JSON.stringify({ ...event, event: type }));
	const title = () =>
		hostMessages.filter((value) => value.event === "setTitle" && value.context === "test-key").at(-1)?.payload.title ??
		"";
	const active = () =>
		hostMessages.filter((value) => value.event === "setState" && value.context === "test-key").at(-1)?.payload.state;
	const diagnostic = () =>
		`${output}\n${JSON.stringify(
			hostMessages.slice(-4).map(({ event, context, payload }) => ({
				event,
				context,
				title: payload?.title,
				state: payload?.state,
				fields: Object.keys(payload ?? {}),
			})),
		)}`;
	try {
		await waitUntil(() => hostMessages.some((value) => value.event === "registerPlugin") && appSocket, diagnostic);
		assert.equal(hostMessages.find((value) => value.event === "registerPlugin").uuid, uuid);
		send("willAppear");
		await waitUntil(() => /Combined\nOff/.test(title()), diagnostic);
		send("keyDown");
		await waitUntil(() => commands.length === 1 && title().includes("Pending"), diagnostic);
		assert.deepEqual(commands[0].action, { name: "curve.set", curve: "combined", enabled: true });
		assert.deepEqual(commands[0].target, snapshot.target);
		assert.equal(active(), 0);
		appSocket.send(
			JSON.stringify({
				version: CONTROL_VERSION,
				type: "response",
				id: commands[0].id,
				target: commands[0].target,
				status: "ok",
			}),
		);
		snapshot.sequence++;
		snapshot.curves[3].active = true;
		appSocket.send(JSON.stringify(snapshot));
		await waitUntil(() => active() === 1 && /Combined\nOn/.test(title()), diagnostic);
		await close(backend);
		await waitUntil(() => title().includes("Offline") && active() === 0, diagnostic);
		backend = await server();
		token = "b".repeat(64);
		snapshot = {
			...structuredClone(examples.messages[0]),
			session_id: "restarted",
			sequence: 0,
			target: { ...snapshot.target, generation: snapshot.target.generation + 1 },
		};
		attachBackend(backend);
		await writeFile(discovery, JSON.stringify({ version: TRANSPORT_VERSION, port: backend.address().port, token }));
		await waitUntil(() => /Combined\nOff/.test(title()), diagnostic);
		assert.equal(commands.length, 1);
		send("keyDown");
		await waitUntil(() => commands.length === 2, diagnostic);
		assert.deepEqual(commands[1].target, snapshot.target);
		assert.notEqual(commands[1].id, commands[0].id);
		const homeEvent = {
			...event,
			action: `${uuid}.home`,
			context: "test-home",
			payload: { ...event.payload, settings: {} },
		};
		hostSocket.send(JSON.stringify({ ...homeEvent, event: "willAppear" }));
		hostSocket.send(JSON.stringify({ ...homeEvent, event: "keyDown" }));
		await waitUntil(() => hostMessages.some((value) => value.event === "switchToProfile"), diagnostic);
		const navigation = hostMessages.find((value) => value.event === "switchToProfile");
		assert.equal(navigation.device, "test-device");
		assert.deepEqual(navigation.payload, { profile: "profiles/neo", page: 0 });
		assert.equal(commands.length, 2, "Home must not apply previews or send application commands");
		const navigate = (event, device, page, target) =>
			hostSocket.send(
				JSON.stringify({
					event,
					action: `${uuid}.plus-navigation`,
					context: `${device}-nav-${page}-${target}`,
					device,
					payload: {
						controller: "Keypad",
						coordinates: { column: 1, row: 0 },
						settings: { page, target },
						isInMultiAction: false,
						state: 0,
					},
				}),
			);
		const switches = () =>
			hostMessages.filter((value) => value.event === "switchToProfile" && value.payload.profile === "profiles/plus");
		navigate("willAppear", "test-plus", 0, "playback");
		await waitUntil(
			() =>
				hostMessages.some(
					(value) =>
						value.event === "setTitle" &&
						value.context === "test-plus-nav-0-playback" &&
						value.payload.title === "Playback\nPaused",
				),
			diagnostic,
		);
		assert.ok(
			hostMessages.some(
				(value) =>
					value.event === "setImage" &&
					value.context === "test-plus-nav-0-playback" &&
					!Buffer.from(value.payload.image.split(",")[1], "base64").toString().includes("disconnected"),
			),
		);
		navigate("keyDown", "test-plus", 0, "playback");
		await waitUntil(() => switches().length === 1, diagnostic);
		assert.deepEqual(switches()[0].payload, { profile: "profiles/plus", page: 1 });
		navigate("willDisappear", "test-plus", 0, "playback");
		navigate("willAppear", "test-plus", 2, "playback");
		await waitUntil(
			() =>
				hostMessages.some(
					(value) =>
						value.event === "setState" && value.context === "test-plus-nav-2-playback" && value.payload.state === 1,
				),
			diagnostic,
		);
		navigate("keyDown", "test-plus", 2, "playback");
		navigate("willAppear", "test-plus", 0, "playback");
		navigate("keyDown", "test-plus", 0, "playback");
		await waitUntil(() => switches().length === 2, diagnostic);
		assert.equal(switches()[1].payload.page, 2, "Remember the subgroup confirmed by the SDK host");
		navigate("willAppear", "test-plus-2", 0, "playback");
		navigate("keyDown", "test-plus-2", 0, "playback");
		await waitUntil(() => switches().length === 3, diagnostic);
		assert.equal(switches()[2].device, "test-plus-2");
		assert.equal(switches()[2].payload.page, 1);
		assert.equal(commands.length, 2, "Page navigation must never send Analyzer commands");
		const dialEvent = {
			action: `${uuid}.dial`,
			context: "test-dial",
			device: "test-plus",
			payload: { controller: "Encoder", coordinates: { column: 0, row: 0 }, settings: { control: "library" } },
		};
		const sendDial = (type, extra = {}) =>
			hostSocket.send(JSON.stringify({ ...dialEvent, event: type, payload: { ...dialEvent.payload, ...extra } }));
		const dialFeedback = () =>
			hostMessages.filter((value) => value.event === "setFeedback" && value.context === "test-dial").at(-1)?.payload;
		sendDial("willAppear");
		await waitUntil(() => dialFeedback()?.value === "Example ride", diagnostic);
		assert.ok(
			hostMessages.some(
				(value) =>
					value.event === "setFeedbackLayout" &&
					value.context === "test-dial" &&
					value.payload.layout === "layouts/plus.json",
			),
		);
		sendDial("dialRotate", { ticks: 3, pressed: false });
		await waitUntil(() => commands.length === 5 && dialFeedback()?.status.value.includes("Pending"), diagnostic);
		assert.deepEqual(
			commands.slice(-3).map((value) => value.action),
			Array(3).fill({ name: "library.move", direction: 1 }),
		);
		for (const command of commands.slice(-3))
			appSocket.send(
				JSON.stringify({
					version: CONTROL_VERSION,
					type: "response",
					id: command.id,
					target: command.target,
					status: "ok",
				}),
			);
		await waitUntil(() => dialFeedback()?.status.value === "Ready", diagnostic);
		sendDial("dialDown");
		await waitUntil(() => commands.length === 6, diagnostic);
		assert.deepEqual(commands[5].action, { name: "library.open.same" });
		const infoEvent = {
			action: `${uuid}.infobar`,
			context: "test-info",
			device: "test-device",
			payload: {
				controller: "Neo",
				coordinates: { column: 1, row: 0 },
				settings: { section: "markers", marker: "gravity" },
			},
		};
		hostSocket.send(JSON.stringify({ ...infoEvent, event: "willAppear" }));
		const barFeedback = () =>
			hostMessages.filter((value) => value.event === "setFeedback" && value.context === "test-info").at(-1)?.payload;
		await waitUntil(() => barFeedback()?.title.startsWith("Gravity"), diagnostic);
		assert.match(barFeedback().status, /Applied #50/);
		assert.match(barFeedback().title, /Preview/);
		assert.match(barFeedback().icon, /^data:image\/svg\+xml;base64,/);
		assert.ok(
			hostMessages.some(
				(value) =>
					value.event === "setFeedbackLayout" &&
					value.context === "test-info" &&
					value.payload.layout === "layouts/neo.json",
			),
		);
		const modeEvent = { ...homeEvent, action: `${uuid}.step-mode`, context: "test-mode", device: "test-plus" };
		hostSocket.send(JSON.stringify({ ...modeEvent, event: "willAppear" }));
		hostSocket.send(JSON.stringify({ ...modeEvent, event: "keyDown" }));
		await waitUntil(
			() =>
				hostMessages.some(
					(value) =>
						value.event === "setTitle" && value.context === "test-mode" && value.payload.title.includes("Medium"),
				),
			diagnostic,
		);
		assert.equal(commands.length, 6, "InfoBar and Fine/Coarse never send app commands");
		appSocket.send(JSON.stringify({ token, recording: "private-recording-payload-GPS", version: -1 }));
		await waitUntil(() => title().includes("Version err"), diagnostic);
		snapshot.sequence++;
		appSocket.send(JSON.stringify(snapshot));
		await waitUntil(() => !title().includes("Version err"), diagnostic);
		const sdkLog = await readFile(path.join(plugin, "logs", `${uuid}.0.log`), "utf8");
		assert.match(sdkLog, /Analyzer protocol rejected/);
		assert.match(sdkLog, /server\.message\.invalid/);
		assert.match(sdkLog, /Analyzer connection/);
		assert.ok(!sdkLog.includes("a".repeat(64)) && !sdkLog.includes(token));
		assert.ok(!sdkLog.includes("private-recording-payload-GPS"));
		await close(backend);
		await waitUntil(() => barFeedback()?.status === "Offline" && dialFeedback()?.value === "—", diagnostic);
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
