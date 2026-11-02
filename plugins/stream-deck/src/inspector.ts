import { CONTROL_LABELS, controlSettings } from "./controls.js";

const select = (name: string): HTMLSelectElement => document.getElementById(name) as HTMLSelectElement;
let socket: WebSocket | undefined;
let context = "";

for (const [value, label] of Object.entries(CONTROL_LABELS)) {
    select("operation").add(new Option(label, value));
}

function display(settings: Record<string, unknown>): void {
    const admitted = controlSettings(settings) ?? controlSettings({});
    if (!admitted) return;
    for (const [name, value] of Object.entries(admitted)) select(name).value = String(value);
    const operation = select("operation").value;
    const visible = {
        direction: ["library.move", "playback.speed.step", "smoothing.step", "view.zoom"].includes(operation),
        steps: operation === "position.step" || operation === "marker.preview",
        curve: operation === "curve.set", marker: operation.startsWith("marker."),
    };
    for (const [name, show] of Object.entries(visible)) document.getElementById(`${name}-row`)!.hidden = !show;
}

for (const element of document.querySelectorAll("select")) {
    element.addEventListener("change", () => {
        const settings = { operation: select("operation").value, direction: Number(select("direction").value),
            steps: Number(select("steps").value), curve: select("curve").value, marker: select("marker").value };
        display(settings);
        if (socket?.readyState === WebSocket.OPEN) socket.send(JSON.stringify({ event: "setSettings", context, payload: settings }));
    });
}

/** Stream Deck calls this global entry point when opening the property inspector. */
Object.assign(window, {
    connectElgatoStreamDeckSocket(port: number, uuid: string, registerEvent: string, _info: string, actionInfo: string): void {
        const info = JSON.parse(actionInfo) as { context: string; payload: { settings: Record<string, unknown> } };
        context = info.context;
        display(info.payload.settings);
        socket = new WebSocket(`ws://127.0.0.1:${port}`);
        socket.addEventListener("open", () => socket?.send(JSON.stringify({ event: registerEvent, uuid })));
        socket.addEventListener("message", event => {
            const message = JSON.parse(String(event.data)) as { event: string; payload: { settings: Record<string, unknown> } };
            if (message.event === "didReceiveSettings") display(message.payload.settings);
        });
    },
});
display({});
