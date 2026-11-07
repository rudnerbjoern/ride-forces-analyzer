import type { ControlClient } from "./client.js";
import { requestedAction, type ControlSettings } from "./controls.js";
import type { StateEvent, UnavailableReason } from "./protocol.js";

export type IconStatus = "active" | "inactive" | "preview" | "unavailable" | "pending" | "failed" | "disconnected";
export interface KeyFeedback {
    title: string;
    image: string;
    state: 0 | 1;
    status: IconStatus;
}

const arrow = '<path d="M76 19L28 54l48 35V71h36V37H76z" fill="url(#blue)" stroke="#bce9ff" stroke-width="2"/>';
const folder = '<path d="M18 31V20q0-6 6-6h32l14 13h42q7 0 7 7v54H18z" fill="#bb681e"/>'
    + '<path d="M16 37q0-6 7-6h94l-9 60H25z" fill="url(#gold)" stroke="#ffe7a0" stroke-width="2"/>';
const chart = '<rect x="17" y="12" width="106" height="79" rx="9" fill="url(#steel)"/>'
    + '<rect x="22" y="18" width="96" height="66" rx="5" fill="#122c48"/>'
    + '<path d="M24 39h92M24 61h92M47 20v62M70 20v62M93 20v62" stroke="#466d91" stroke-width="1" opacity=".6"/>';
const graph = '<path d="M28 72l20-30 21 18 23-31 18 20v29H28z" fill="url(#teal)" opacity=".6"/>'
    + '<path d="M28 72l20-30 21 18 23-31 18 20" fill="none" stroke="#8bf4d1" stroke-width="6" stroke-linejoin="round"/>';
const glass = '<path d="M84 73l34 27" stroke="#081221" stroke-width="19" stroke-linecap="round"/>'
    + '<path d="M84 69l34 27" stroke="url(#blue)" stroke-width="15" stroke-linecap="round"/>'
    + '<circle cx="60" cy="45" r="36" fill="url(#steel)"/>'
    + '<circle cx="60" cy="45" r="29" fill="url(#glass)" stroke="#9ee6ff" stroke-width="2"/>'
    + '<path d="M39 30q14-18 33-6" fill="none" stroke="#e3faff" stroke-width="4" stroke-linecap="round" opacity=".7"/>';
const flag = (end: boolean): string => '<ellipse cx="68" cy="94" rx="34" ry="5" fill="#060e1d" opacity=".7"/>'
    + '<rect x="34" y="16" width="8" height="78" rx="4" fill="url(#steel)"/>'
    + `<path d="M42 19q15-10 33 0t34 0v43q-16 10-34 0t-33 0z" fill="url(#${end ? "rose" : "teal"})"/>`
    + (end ? '<path d="M44 20h15v13H44zM75 22h15v13H75zM59 33h16v14H59zM90 34h16v14H90zM44 46h15v14H44zM75 48h15v14H75z" fill="#fff1f0" opacity=".85"/>'
        : '<path d="M48 22q11-4 22 1" fill="none" stroke="#b8ffe7" stroke-width="3" stroke-linecap="round"/>');

const artwork = {
    website: '<circle cx="70" cy="49" r="42" fill="url(#glass)" stroke="#bcecff" stroke-width="2"/>'
        + '<clipPath id="website-land"><circle cx="70" cy="49" r="40"/></clipPath><g clip-path="url(#website-land)">'
        + '<path d="M35 23l15-9 19 4 3 9-11 5-2 11-9 6-13-8-8-1zM53 48l15 3 9 12-6 8-2 12-8 9-5-17-8-13z" fill="url(#teal)"/>'
        + '<path d="M79 15l13 3 7 10 16 3 4 18-15 6-7-9-10 1-4-9-12-3 1-9zM79 43l14 4 6 12-8 16-9-3-6-15zM103 71l12 2 4 9-12 2-6-5z" fill="url(#gold)"/>'
        + '<path d="M29 49h82M70 8c-22 17-22 65 0 82M70 8c22 17 22 65 0 82" fill="none" stroke="#cbf6ff" stroke-width="1.5" opacity=".2"/></g>'
        + '<path d="M40 31q9-17 28-18" fill="none" stroke="#e0fcff" stroke-width="4" stroke-linecap="round" opacity=".75"/>',
    library: '<rect x="21" y="23" width="27" height="67" rx="5" fill="url(#blue)"/>'
        + '<rect x="52" y="15" width="27" height="75" rx="5" fill="url(#teal)"/>'
        + '<g transform="rotate(-12 99 88)"><rect x="84" y="22" width="26" height="68" rx="5" fill="url(#violet)"/>'
        + '<path d="M90 27h15M90 33h15M90 78h15" stroke="#eadbff" stroke-width="3"/></g>'
        + '<path d="M27 29h15M27 35h15M58 21h15M58 27h15M27 77h15M58 77h15" stroke="#d8fffc" stroke-width="3"/>'
        + '<path d="M22 91h89" stroke="#8eaccd" stroke-width="4" stroke-linecap="round"/>',
    previous: arrow + '<rect x="14" y="23" width="8" height="62" rx="3" fill="url(#steel)"/>',
    next: `<g transform="translate(140 0) scale(-1 1)">${arrow}<rect x="14" y="23" width="8" height="62" rx="3" fill="url(#steel)"/></g>`,
    new_window: '<rect x="19" y="30" width="77" height="64" rx="6" fill="url(#steel)" stroke="#d5f3ff" stroke-width="2"/>'
        + '<rect x="38" y="13" width="82" height="65" rx="6" fill="url(#blue)" stroke="#d5f3ff" stroke-width="2"/>'
        + '<path d="M39 29h80" stroke="#d5f3ff" stroke-width="3"/>'
        + '<path d="M62 64l30-24H77V32h29v29h-8V47L69 71z" fill="url(#teal)" stroke="#d5f3ff" stroke-width="1.5"/>',
    open: folder + '<path d="M63 86l27-28H75V46h39v39h-13V69L74 97z" fill="url(#blue)" stroke="#d5f3ff" stroke-width="2"/>',
    import: '<path d="M24 55h91l11 34q1 9-9 9H23q-10 0-9-9z" fill="url(#blue)"/>'
        + '<path d="M24 55l13-14h65l13 14H91l-8 14H56l-8-14z" fill="#183a59" stroke="#89c6ed" stroke-width="2"/>'
        + '<path d="M58 9h24v29h19L70 67 39 38h19z" fill="url(#teal)" stroke="#c5ffea" stroke-width="2"/>',
    playback: '<circle cx="70" cy="52" r="42" fill="#0a543e"/>'
        + '<circle cx="70" cy="48" r="40" fill="url(#teal)" stroke="#a6ffda" stroke-width="2"/>'
        + '<path d="M59 24l35 24-35 24z" fill="#f3fffb"/>',
    pause: '<circle cx="70" cy="52" r="42" fill="#123c7a"/>'
        + '<circle cx="70" cy="48" r="40" fill="url(#blue)" stroke="#b6e7ff" stroke-width="2"/>'
        + '<rect x="52" y="25" width="13" height="45" rx="3" fill="#f1fcff"/><rect x="76" y="25" width="13" height="45" rx="3" fill="#f1fcff"/>',
    speed: '<path d="M23 88a53 53 0 1 1 94 0z" fill="url(#steel)"/>'
        + '<path d="M33 80a43 43 0 1 1 74 0z" fill="#12263f"/>'
        + '<path d="M34 67a37 37 0 0 1 15-42" fill="none" stroke="#4ce5b0" stroke-width="9"/>'
        + '<path d="M52 22a37 37 0 0 1 34-1" fill="none" stroke="#ffcb64" stroke-width="9"/>'
        + '<path d="M91 23a37 37 0 0 1 17 43" fill="none" stroke="#ff7e91" stroke-width="9"/>'
        + '<path d="M63 69l40-39-26 49z" fill="#ff657c" stroke="#ffd2dc" stroke-width="1"/>'
        + '<circle cx="70" cy="73" r="9" fill="url(#steel)"/>',
    position: '<rect x="16" y="24" width="108" height="62" rx="9" fill="url(#blue)" stroke="#a0dfff" stroke-width="2"/>'
        + '<path d="M27 36v15M44 36v8M61 36v15M78 36v8M95 36v15M112 36v8" stroke="#e4f7ff" stroke-width="3"/>'
        + '<path d="M70 28l-12-14h24zM70 82l-12 14h24z" fill="#ffce6c"/><rect x="67" y="25" width="6" height="59" rx="3" fill="#ffce6c"/>',
    backward: arrow,
    forward: `<g transform="translate(140 0) scale(-1 1)">${arrow}</g>`,
    rewind: '<path d="M65 20L16 54l49 34V20zM120 20L71 54l49 34z" fill="url(#blue)" stroke="#c9eeff" stroke-width="2"/>',
    advance: '<path d="M20 20l49 34-49 34V20zM75 20l49 34-49 34z" fill="url(#blue)" stroke="#c9eeff" stroke-width="2"/>',
    view: glass + '<path d="M55 29h10v11h11v10H65v11H55V50H44V40h11z" fill="#e2faff"/>',
    zoom_out: glass + '<rect x="44" y="40" width="32" height="10" rx="2" fill="#e2faff"/>',
    reset: '<circle cx="70" cy="51" r="36" fill="#143556"/>'
        + '<path d="M38 26a39 39 0 1 1-5 45l14-7a24 24 0 1 0 6-28l16 8-43 8 3-44z" fill="url(#teal)" stroke="#b2ffe8" stroke-width="2"/>',
    selection: '<rect x="18" y="15" width="104" height="78" rx="10" fill="url(#steel)"/>'
        + '<rect x="30" y="27" width="80" height="54" rx="5" fill="#143655"/>'
        + '<path d="M44 47v-9h14M84 38h14v9M98 64v9H84M58 73H44v-9" fill="none" stroke="#8df2d5" stroke-width="5"/>'
        + '<path d="M66 41h8v10h10v8H74v10h-8V59H56v-8h10z" fill="#e4fffa"/>',
    smoothing: chart + '<path d="M27 65c15-56 24 40 43-3s25 37 43-15v31H27z" fill="url(#violet)" opacity=".6"/>'
        + '<path d="M27 65c15-56 24 40 43-3s25 37 43-15" fill="none" stroke="#d9c7ff" stroke-width="7" stroke-linecap="round"/>',
    explorer: '<rect x="16" y="9" width="108" height="83" rx="9" fill="url(#steel)"/>'
        + '<rect x="21" y="28" width="98" height="58" rx="4" fill="#122c48"/>'
        + '<circle cx="28" cy="18" r="3" fill="#ec6d82"/><circle cx="39" cy="18" r="3" fill="#edbd55"/><circle cx="50" cy="18" r="3" fill="#41bb8c"/>' + graph,
    markers: `<g transform="translate(-7 0) scale(.78)">${flag(false)}</g><g transform="translate(46 18) scale(.72)">${flag(true)}</g>`,
    home: '<path d="M27 49h86v44H27z" fill="url(#gold)" stroke="#ffe6ac" stroke-width="2"/>'
        + '<path d="M12 50L70 6l58 44-9 12-49-37-49 37z" fill="url(#blue)" stroke="#cceeff" stroke-width="2"/>'
        + '<path d="M60 61h23v32H60z" fill="#224565"/><rect x="37" y="60" width="14" height="15" rx="2" fill="#e9f8ff"/>',
    back: arrow,
    selection_start: chart + '<rect x="38" y="24" width="57" height="53" fill="#55d6ae" opacity=".25"/><rect x="30" y="21" width="12" height="60" rx="4" fill="url(#teal)"/>',
    selection_end: chart + '<rect x="38" y="24" width="57" height="53" fill="#ed7992" opacity=".25"/><rect x="93" y="21" width="12" height="60" rx="4" fill="url(#rose)"/>',
    curve: chart + graph,
    first: chart + graph + '<path d="M100 65l12 14m0-14-12 14" stroke="#d6faff" stroke-width="4"/>',
    second: chart + graph + '<path d="M99 64l7 8 7-8m-7 8v9" fill="none" stroke="#d6faff" stroke-width="4"/>',
    third: chart + graph + '<path d="M100 64h13l-13 16h13" fill="none" stroke="#d6faff" stroke-width="4"/>',
    combined: chart + '<path d="M28 65l20-33 24 40 21-34 18 15v25H28z" fill="url(#violet)" opacity=".65"/>'
        + '<path d="M28 65l20-33 24 40 21-34 18 15M28 44l24 29 25-40 33 36" fill="none" stroke="#c4abff" stroke-width="5"/>',
    calibrated: '<circle cx="70" cy="53" r="40" fill="url(#blue)" stroke="#a9e4ff" stroke-width="2"/>'
        + '<circle cx="70" cy="53" r="24" fill="#163e5a" stroke="#63edd4" stroke-width="7"/>'
        + '<path d="M65 9h10v29H65zM65 68h10v29H65zM26 48h29v10H26zM85 48h29v10H85z" fill="url(#steel)"/>'
        + '<circle cx="70" cy="53" r="7" fill="#fff0b3"/>',
    marker: flag(false), start: flag(false), end: flag(true),
    gravity: '<path d="M53 29V18a17 17 0 0 1 34 0v11h-9V18a8 8 0 0 0-16 0v11z" fill="url(#steel)"/>'
        + '<path d="M43 24h54l20 62q2 8-7 8H30q-9 0-7-8z" fill="url(#violet)" stroke="#e0ceff" stroke-width="2"/>'
        + '<text x="70" y="75" text-anchor="middle" font-family="sans-serif" font-size="48" font-weight="bold" fill="#faf5ff">g</text>',
    incline: '<path d="M23 91l92-77v77z" fill="url(#gold)" stroke="#ffecb4" stroke-width="2"/>'
        + '<path d="M58 76l41-34v34z" fill="#193951"/><path d="M33 87a19 19 0 0 0-4-11" fill="none" stroke="#a56a1a" stroke-width="4"/>'
        + '<path d="M56 78l4 5M70 67l4 5M84 55l4 5M98 43l4 5" stroke="#855516" stroke-width="3"/>',
    apply: '<circle cx="70" cy="55" r="41" fill="#0b5b43"/><circle cx="70" cy="50" r="40" fill="url(#teal)" stroke="#b1ffe0" stroke-width="2"/>'
        + '<path d="M42 49l16 16 39-39 10 10-49 49-26-26z" fill="#f2fff8"/>',
    discard: '<circle cx="70" cy="54" r="41" fill="#74521c"/><circle cx="70" cy="50" r="40" fill="url(#gold)" stroke="#ffedbf" stroke-width="2"/>'
        + '<path d="M48 28L27 48l21 20V55h32a12 12 0 0 1 0 24H65v12h15a24 24 0 0 0 0-48H48z" fill="#73471c"/>',
    fine: '<rect x="18" y="23" width="105" height="65" rx="9" fill="url(#steel)"/><rect x="24" y="30" width="93" height="51" rx="5" fill="#16344f"/>'
        + '<path d="M36 62h70" stroke="#93afc5" stroke-width="3"/><rect x="64" y="37" width="13" height="38" rx="4" fill="url(#blue)"/>',
    medium: '<rect x="18" y="23" width="105" height="65" rx="9" fill="url(#steel)"/><rect x="24" y="30" width="93" height="51" rx="5" fill="#16344f"/>'
        + '<rect x="50" y="43" width="13" height="32" rx="4" fill="url(#blue)"/><rect x="78" y="35" width="13" height="40" rx="4" fill="url(#teal)"/>',
    coarse: '<rect x="18" y="23" width="105" height="65" rx="9" fill="url(#steel)"/><rect x="24" y="30" width="93" height="51" rx="5" fill="#16344f"/>'
        + '<rect x="36" y="43" width="13" height="32" rx="4" fill="url(#blue)"/><rect x="64" y="35" width="13" height="40" rx="4" fill="url(#teal)"/>'
        + '<rect x="92" y="43" width="13" height="32" rx="4" fill="url(#violet)"/>',
};

const reasons: Record<UnavailableReason, string> = {
    no_active_window: "No Explorer", background: "Background", input_focus: "Editing",
    dialog_open: "Dialog open", no_recording: "No recording", no_selection: "No selection",
    empty_library: "Empty Library", unsupported: "Unavailable", busy: "Busy",
    no_preview: "No preview", invalid_marker: "Invalid marker",
};

/** Keep device explanations short enough for keys and the 200-pixel touch fields. */
export function unavailableLabel(reason: UnavailableReason): string { return reasons[reason]; }

/** Select a function-specific symbol independently of availability and toggle state. */
export function actionIcon(settings: ControlSettings | undefined, state?: StateEvent): string {
    switch (settings?.operation) {
        case "library.move": return settings.direction === -1 ? "previous" : "next";
        case "library.open": return "open";
        case "library.open_new_window": return "new_window";
        case "library.import": return "import";
        case "library.filter.reset": return "reset";
        case "playback.toggle": return state?.playback?.playing ? "pause" : "playback";
        case "playback.speed.step": return "speed";
        case "playback.speed.reset": case "smoothing.reset": case "view.reset": return "reset";
        case "selection.step": return settings.boundary === "end" ? "selection_end" : "selection_start";
        case "position.step": return (settings.steps ?? 1) < 0
            ? Math.abs(settings.steps ?? 1) === 10 ? "rewind" : "backward"
            : Math.abs(settings.steps ?? 1) === 10 ? "advance" : "forward";
        case "view.zoom": return settings.direction === -1 ? "zoom_out" : "view";
        case "view.selection": return "selection";
        case "smoothing.step": return "smoothing";
        case "curve.set": return settings.curve ?? "first";
        case "marker.apply": return "apply";
        case "marker.discard": return "discard";
        case "marker.preview": return settings.marker ?? "start";
        default: return "playback";
    }
}

/** Render shaded, filled function artwork with an independent state badge. */
export function keyImage(area: string, status: IconStatus | undefined, compact = false): string {
    const color = { active: "#52dc96", inactive: "#9db4d1", preview: "#d4acff", unavailable: "#f6bd4f",
        pending: "#62b5ff", failed: "#ff7777", disconnected: "#8290a6" }[status ?? "inactive"];
    const shape = artwork[area as keyof typeof artwork] ?? artwork.marker;
    const badge = status === "active" ? '<path d="M104 21l6 6 11-13"/>'
        : status === "preview" ? '<path d="M104 27l3-8 10-10 5 5-10 10-8 3"/>'
        : status === "unavailable" ? '<path d="M105 18v-4a7 7 0 0 1 14 0v4"/><rect x="103" y="18" width="18" height="15" rx="3" fill="#2a200d" stroke="none"/>'
        : status === "failed" ? '<path d="M105 13l14 14m0-14-14 14"/>'
        : status === "pending" ? '<path d="M112 10v11l7 5"/>'
        : status === "disconnected" ? '<path d="M104 12l16 16 M104 28l4-4 M116 16l4-4"/>'
        : '<circle cx="112" cy="20" r="5" fill="#d1e2f5" stroke="none"/>';
    const palette = { blue: ["#83d6ff", "#2672dd"], teal: ["#76ffd3", "#16a47c"], gold: ["#ffe69b", "#e4a033"],
        violet: ["#d6b1ff", "#7750cf"], steel: ["#eef7ff", "#829cb9"], rose: ["#ffb5bb", "#e35072"], glass: ["#629dcc", "#1b3d67"] };
    const gradients = Object.entries(palette).map(([id, colors]) => `<linearGradient id="${id}" x2=".25" y2="1">`
        + `<stop stop-color="${colors[0]}"/><stop offset="1" stop-color="${colors[1]}"/></linearGradient>`).join("");
    const opacity = status === "disconnected" ? .3 : status === "unavailable" ? .55 : 1;
    return `<svg xmlns="http://www.w3.org/2000/svg" width="144" height="144" viewBox="${compact ? "15 0 118 110" : "0 0 144 144"}">`
        + `<title>${area}: ${status ?? "menu"}</title><defs>${gradients}<linearGradient id="background" x2=".2" y2="1">`
        + '<stop stop-color="#284564"/><stop offset=".55" stop-color="#152b45"/><stop offset="1" stop-color="#101d30"/></linearGradient></defs>'
        + '<rect x=".5" y=".5" width="143" height="143" rx="16" fill="url(#background)" stroke="#527699" stroke-opacity=".35"/>'
        + `<ellipse cx="70" cy="90" rx="43" ry="5" fill="#030912" opacity=".4"/>`
        + `<g transform="translate(15 8) scale(.78)" opacity="${opacity}">${shape}</g>`
        + (status === undefined ? "" : `<circle cx="112" cy="22" r="19" fill="#070e1c" opacity=".6"/><circle cx="112" cy="20" r="17" fill="${color}" stroke="#ecf6ff" stroke-opacity=".65"/>`
            + `<g stroke="#142237" fill="none" stroke-width="3.5" stroke-linecap="round" stroke-linejoin="round">${badge}</g>`)
        + '</svg>';
}

/** Encode SVG artwork consistently for the native key and feedback image APIs. */
export function imageData(svg: string): string {
    return `data:image/svg+xml;base64,${Buffer.from(svg).toString("base64")}`;
}

/** Bound native key captions to two short lines; detailed values belong on the touch strip. */
function keyTitle(value: string): string {
    const short: Record<string, string> = { "No recording": "No data", "No selection": "No choice", "Empty Library": "Empty list", Incompatible: "Version err" };
    return value.split("\n").slice(0, 2).map(line => short[line] ?? line)
        .map(line => line.length > 11 ? `${line.slice(0, 10)}…` : line).join("\n");
}

/** Render values and toggles from app snapshots, never from a successful button press alone. */
export function keyFeedback(client: ControlClient, context: string, settings: ControlSettings | undefined): KeyFeedback {
    const name = settings?.operation ?? "playback.toggle";
    const icon = actionIcon(settings, client.state);
    const labels = {
        "library.move": "Library", "library.open": "Open", "library.open_new_window": "New window", "library.import": "Import",
        "library.filter.reset": "Reset filters",
        "playback.toggle": "Play/Pause", "playback.speed.step": "Speed", "playback.speed.reset": "Speed reset",
        "position.step": "Position", "selection.step": "Selection", "view.zoom": "Zoom", "view.reset": "Reset view",
        "view.selection": "Zoom", "smoothing.step": "Smoothing", "smoothing.reset": "Smoothing",
        "curve.set": "Curves", "marker.preview": "Marker", "marker.apply": "Apply", "marker.discard": "Discard",
    };
    const label = settings ? name === "library.move" ? settings.direction === -1 ? "Previous" : "Next" : labels[name] : "Choose";
    const snapshot = client.state;
    let title = name === "view.selection" ? "Zoom\nSelection" : label;
    let active = false;
    let playing = false;
    let status: IconStatus = "inactive";
    if (client.status !== "connected" || !snapshot) {
        const detail = client.status === "incompatible" ? "Incompatible" : client.status === "connecting" ? "Connecting…" : "Offline";
        return { title: keyTitle(`${label}\n${detail}`), image: keyImage(icon, "disconnected"), state: 0, status: "disconnected" };
    }
    if (name.startsWith("library.")) {
        const selected = snapshot.library?.selected;
        const index = selected ? `${selected.index + 1}/${snapshot.library?.count}`
            : snapshot.library?.count === 0 ? "Empty" : "No choice";
        title = name === "library.import" ? "Import…"
            : name === "library.open_new_window" ? "New\nwindow"
            : name === "library.filter.reset" ? "Reset\nfilters" : `${label}\n${index}`;
    } else if (name === "playback.toggle") {
        playing = snapshot.playback?.playing ?? false;
        active = playing;
        title = `${playing ? "Pause" : "Play"}\n${snapshot.playback?.speed ?? "—"}×`;
    } else if (name.startsWith("playback.speed")) {
        title = `${name.endsWith("reset") ? "Speed reset" : `Speed ${settings?.direction === -1 ? "−" : "+"}`}\n${snapshot.playback?.speed ?? "—"}×`;
    } else if (name === "selection.step") {
        const boundary = settings?.boundary ?? "start";
        title = `Sel. ${boundary}\n${snapshot.selection?.[boundary].label ?? "—"}`;
    } else if (name === "position.step") {
        title = `Pos. ${settings?.steps ?? 1}\n${snapshot.playback?.position?.label ?? "—"}`;
    } else if (name.startsWith("smoothing.")) {
        title = `${name.endsWith("reset") ? "Reset" : `Smooth ${settings?.direction === -1 ? "−" : "+"}`}\n${snapshot.view?.smoothing_window ?? "—"} samples`;
    } else if (name === "view.zoom") {
        title = `Zoom ${settings?.direction === -1 ? "−" : "+"}\n${snapshot.view?.start_seconds != null && snapshot.view.end_seconds != null ? (snapshot.view.end_seconds - snapshot.view.start_seconds).toFixed(1) : "—"} s`;
    } else if (name === "curve.set") {
        const curve = snapshot.curves.find(value => value.curve === (settings?.curve ?? "first"));
        const curveLabel = { first: "Curve 1", second: "Curve 2", third: "Curve 3", combined: "Combined", calibrated: "Data mode" }[settings?.curve ?? "first"];
        active = curve?.active ?? false;
        title = settings?.curve === "calibrated" ? `Data mode\n${curve ? active ? "Calibrated" : "Raw" : "—"}`
            : `${curve?.label === "Longitudinal" ? "Long." : curve?.label ?? curveLabel}\n${active ? "On" : "Off"}`;
    } else if (name.startsWith("marker.")) {
        const marker = snapshot.markers.find(value => value.marker === (settings?.marker ?? "start"));
        const value = marker?.preview ?? marker?.applied;
        const markerName = marker ? marker.marker.charAt(0).toUpperCase() + marker.marker.slice(1) : "Marker";
        const steps = settings?.steps ?? 1;
        title = name === "marker.preview" ? `${markerName} ${steps > 0 ? "+" : ""}${steps}\n${value?.label ?? "Unset"}`
            : `${markerName}\n${name === "marker.apply" ? "Apply" : "Discard"}`;
        if (marker?.status === "pending") status = "pending";
        if (marker?.status === "failed") status = "failed";
        if (marker?.status === "preview") status = "preview";
    }
    if (active) status = "active";
    if ((!settings || !requestedAction(settings, snapshot)) && status !== "pending" && status !== "failed") {
        status = "unavailable";
        const marker = snapshot.markers.find(value => value.marker === (settings?.marker ?? "start"));
        const availability = name === "curve.set"
            ? snapshot.curves.find(value => value.curve === (settings?.curve ?? "first"))?.availability
            : name.startsWith("marker.") ? marker?.availability[name === "marker.apply" ? "apply" : name === "marker.discard" ? "discard" : "preview"]
            : snapshot.controls[name];
        const reason = !snapshot.availability.available ? snapshot.availability.reason
            : availability?.available === false ? availability.reason : "unsupported";
        title = `${title.split("\n")[0]}\n${unavailableLabel(reason)}`;
    }
    if (client.pending(context)) status = "pending";
    if (client.error(context)) status = "failed";
    if (status === "pending") title = `${title.split("\n")[0]}\nPending`;
    if (status === "failed") title = `${title.split("\n")[0]}\nFailed`;
    return { title: keyTitle(title), image: keyImage(icon, status), state: active ? 1 : 0, status };
}
