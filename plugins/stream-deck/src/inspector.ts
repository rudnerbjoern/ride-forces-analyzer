import { CONTROL_LABELS, controlSettings } from "./controls.js";

const select = (name: string): HTMLSelectElement => document.getElementById(name) as HTMLSelectElement;
let socket: WebSocket | undefined;
let context = "";
let invalidSettings = false;
let connectionAvailable = false;
let unsavedChanges = false;

/** Show validation and connection problems without implying that local choices were saved. */
function updateStatus(): void {
	const messages: string[] = [];
	if (invalidSettings)
		messages.push("Saved settings are invalid. Defaults are shown; change a selection to save valid settings.");
	if (!connectionAvailable)
		messages.push("Settings connection unavailable. Changes cannot be saved. Reopen this inspector to reconnect.");
	else if (unsavedChanges) messages.push("Changes were not saved. Change a selection again to save.");
	const status = document.getElementById("settings-status")!;
	status.textContent = messages.join(" ");
	status.hidden = messages.length === 0;
}

for (const [value, label] of Object.entries(CONTROL_LABELS)) {
	select("operation").add(new Option(label, value));
}

const setupHelp = document.getElementById("setup-help") as HTMLAnchorElement;
setupHelp.addEventListener("click", (event) => {
	event.preventDefault();
	if (!connectionAvailable || socket?.readyState !== WebSocket.OPEN) return;
	try {
		socket.send(JSON.stringify({ event: "openUrl", payload: { url: setupHelp.href } }));
	} catch {
		connectionAvailable = false;
		updateStatus();
	}
});

/**
 * Restore inspector selections and show only rows relevant to the operation.
 * @param settings Settings to validate before displaying saved choices or defaults.
 */
function display(settings: Record<string, unknown>): void {
	const validated = controlSettings(settings);
	invalidSettings = validated === undefined;
	const admitted = validated ?? controlSettings({})!;
	for (const [name, value] of Object.entries(admitted)) select(name).value = String(value);
	const operation = select("operation").value;
	const visible = {
		direction: ["library.move", "playback.speed.step", "smoothing.step", "view.zoom"].includes(operation),
		steps: operation === "selection.step" || operation === "position.step" || operation === "marker.preview",
		boundary: operation === "selection.step",
		curve: operation === "curve.set",
		marker: operation.startsWith("marker."),
	};
	for (const [name, show] of Object.entries(visible)) document.getElementById(`${name}-row`)!.hidden = !show;
	updateStatus();
}

for (const element of document.querySelectorAll("select")) {
	element.addEventListener("change", () => {
		const settings = {
			operation: select("operation").value,
			direction: Number(select("direction").value),
			steps: Number(select("steps").value),
			curve: select("curve").value,
			marker: select("marker").value,
			boundary: select("boundary").value,
		};
		display(settings);
		unsavedChanges = true;
		if (!invalidSettings && connectionAvailable && socket?.readyState === WebSocket.OPEN) {
			try {
				socket.send(JSON.stringify({ event: "setSettings", context, payload: settings }));
				unsavedChanges = false;
			} catch {
				/* Keep the inline unsaved message when sending fails. */
			}
		}
		updateStatus();
	});
}

/** Stream Deck calls this global entry point when opening the property inspector. */
Object.assign(window, {
	connectElgatoStreamDeckSocket(
		port: number,
		uuid: string,
		registerEvent: string,
		_info: string,
		actionInfo: string,
	): void {
		const info = JSON.parse(actionInfo) as {
			/**
			 *
			 */
			context: string;
			/**
			 *
			 */
			payload: {
				/**
				 *
				 */
				settings: Record<string, unknown>;
			};
		};
		context = info.context;
		unsavedChanges = false;
		connectionAvailable = false;
		display(info.payload.settings);
		socket = new WebSocket(`ws://127.0.0.1:${port}`);
		socket.addEventListener("open", () => {
			socket?.send(JSON.stringify({ event: registerEvent, uuid }));
			connectionAvailable = true;
			updateStatus();
		});
		for (const event of ["close", "error"])
			socket.addEventListener(event, () => {
				connectionAvailable = false;
				updateStatus();
			});
		socket.addEventListener("message", (event) => {
			const message = JSON.parse(String(event.data)) as {
				/**
				 *
				 */
				event: string;
				/**
				 *
				 */
				payload: {
					/**
					 *
					 */
					settings: Record<string, unknown>;
				};
			};
			if (message.event === "didReceiveSettings") {
				unsavedChanges = false;
				display(message.payload.settings);
			}
		});
	},
});
display({});
