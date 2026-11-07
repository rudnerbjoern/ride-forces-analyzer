import type { ControlClient } from "./client.js";
import { dialFeedback } from "./device-feedback.js";
import { isPressOnly, type DialSettings, type StepSize } from "./device-controls.js";
import type { IconStatus } from "./feedback.js";

const colors: Record<IconStatus, string> = { active: "#52dc96", inactive: "#a6c5e1", preview: "#d4acff",
    pending: "#62b5ff", failed: "#ff7777", unavailable: "#f6bd4f", disconnected: "#8290a6" };
const transparent = '<svg xmlns="http://www.w3.org/2000/svg" width="26" height="26"/>';

/** Render a standalone native-size status symbol, never a badge on function artwork. */
export function statusImage(status: IconStatus): string {
    const shape = status === "active" ? '<path d="m5 13 5 5L22 6"/>'
        : status === "preview" ? '<path d="m5 20 2-7L18 2l6 6-11 11Z M16 4l6 6"/>'
        : status === "pending" ? '<circle cx="13" cy="13" r="10"/><path d="M13 5v8l6 4"/>'
        : status === "failed" ? '<path d="m5 5 16 16M21 5 5 21"/>'
        : status === "unavailable" ? '<path d="M7 11V7a6 6 0 0 1 12 0v4"/><rect x="4" y="11" width="18" height="13" rx="2"/>'
        : status === "disconnected" ? '<path d="m4 4 18 18M5 18l5-5m6-6 5-5M2 21l4 3M21 2l3 4"/>'
        : '<circle cx="13" cy="13" r="5" fill="currentColor" stroke="none"/>';
    return `<svg xmlns="http://www.w3.org/2000/svg" width="26" height="26" viewBox="0 0 26 26"><title>${status}</title>`
        + `<g color="${colors[status]}" stroke="${colors[status]}" stroke-width="2.5" fill="none" stroke-linecap="round" stroke-linejoin="round">${shape}</g></svg>`;
}

/** Present the existing confirmed feedback on the Plus five-line native layout. */
export function plusFeedback(client: ControlClient, context: string, settings: DialSettings | undefined,
    samples: StepSize, proposal?: string | null) {
    const control = settings?.control;
    const menu = settings?.menu ?? (control === "library" || control === "filter" || control === "display" ? "library"
        : control === "marker" ? "markers" : control === "smoothing" || control === "combined" ? "curves" : "playback");
    const column = settings?.column ?? (control === "filter" ? settings?.filter === "park" ? 2 : 3 : control === "display" ? 1 : 0);
    const background = `layouts/backgrounds/${menu}-${column}.svg`;
    const base = dialFeedback(client, context, settings, samples, proposal, false);
    const { visual: initial, status: oldStatus, ...text } = base;
    let visual = initial;
    let status = oldStatus.replace(/ · (?:Fine|Medium|Coarse) · \d+ samples?/, "").replace(/ · Press: Filter/, "");
    let hint = control === "filter" ? "Press: Filter · Touch: All" : control === "marker" ? "Press: Apply · Touch: Discard"
        : control === "library" ? "Press: Open" : control === "selection" ? "Turn: select bound" : base.detail;
    let detail = control === "marker" || control === "filter" || control === "selection" ? base.detail : "";
    if (control === "library") detail = client.state?.library?.selected
        ? `${client.state.library.selected.index + 1}/${client.state.library.count}` : "";
    if (control === "filter") text.title = settings?.filter === "park" ? "Park" : "Status";
    if (isPressOnly(control)) {
        status = status === "PRESS ONLY" ? "PRESS ONLY" : status.replace(" · PRESS ONLY", "");
    }
    const marker = control === "marker" ? client.state?.markers.find(value => value.marker === settings?.marker) : undefined;
    if (marker && marker.applied === null && marker.preview === null && client.status === "connected" && client.state?.availability.available) {
        status = "Reference unset"; visual = "unavailable"; detail = "Set in Analyzer"; hint = "";
    }
    if (visual === "unavailable" && status.includes(" · ")) status = status.split(" · ").at(-1)!;
    if (visual === "disconnected") { detail = ""; hint = ""; }
    if (control === "display") {
        return { layout: "layouts/plus-compact.json", background, icon: transparent, title: "", value: "", status: { value: "", color: colors.inactive },
            band: transparent, statusIcon: transparent, detail: "", hint: "" };
    }
    const oneLine = (value: string): string => value.replace(/[\r\n\t\u2028\u2029]/g, " ");
    return { ...text, layout: detail ? "layouts/plus.json" : "layouts/plus-compact.json",
        title: oneLine(text.title), value: oneLine(text.value), background, detail: oneLine(detail), hint,
        status: { value: status, color: colors[visual] },
        statusIcon: statusImage(visual),
        band: `<svg xmlns="http://www.w3.org/2000/svg" width="200" height="26"><rect width="200" height="26" fill="${colors[visual]}" fill-opacity=".13"/></svg>` };
}
