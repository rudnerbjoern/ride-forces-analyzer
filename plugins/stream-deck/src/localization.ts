// cspell:words Nouv filt Expl Vorsch Grav Ausw
/** Short device captions shared by the runtime, inspector and bundled profiles. */
export const LANGUAGES = ["en", "de", "fr"] as const;
/** Supported presentation locales, independent of application command identifiers. */
export type Language = (typeof LANGUAGES)[number];

/** German and French translations; English source text is the default. */
export const TRANSLATIONS: Readonly<Record<string, readonly [string, string]>> = {
	Library: ["Bibliothek", "Biblio."],
	Explorer: ["Explorer", "Explorer"],
	Playback: ["Playback", "Playback"],
	Curves: ["Kurven", "Courbes"],
	Markers: ["Marker", "Repères"],
	Marker: ["Marker", "Repère"],
	Navigate: ["Navigation", "Navigation"],
	Selection: ["Auswahl", "Sélection"],
	Position: ["Position", "Position"],
	View: ["Ansicht", "Vue"],
	Smoothing: ["Glättung", "Lissage"],
	Smooth: ["Glätten", "Lisser"],
	Speed: ["Tempo", "Vitesse"],
	"Speed reset": ["Tempo Reset", "Reset vit."],
	"Reset playback speed": ["Tempo zurücksetzen", "Réinitialiser la vitesse"],
	"Playback speed": ["Playback-Tempo", "Vitesse de lecture"],
	"Quick controls": ["Schnellzugriff", "Accès rapide"],
	Open: ["Öffnen", "Ouvrir"],
	"New window": ["Neues Fen.", "Nouv. fen."],
	New: ["Neues", "Nouvelle"],
	window: ["Fenster", "fenêtre"],
	Import: ["Import", "Import"],
	"Import…": ["Import…", "Importer…"],
	"Reset filters": ["FilterReset", "Reset filt."],
	Reset: ["Reset", "Reset"],
	filters: ["Filter", "filtres"],
	"Reset view": ["Ans. Reset", "Reset vue"],
	Previous: ["Zurück", "Précédent"],
	Next: ["Weiter", "Suivant"],
	Choose: ["Wählen", "Choisir"],
	Empty: ["Leer", "Vide"],
	"No choice": ["Keine Wahl", "Aucun choix"],
	"No selection": ["Keine Wahl", "Aucun choix"],
	"Empty Library": ["Liste leer", "Liste vide"],
	"Empty list": ["Liste leer", "Liste vide"],
	"No recording": ["Keine Daten", "Sans données"],
	"No data": ["Keine Daten", "Sans donnée"],
	"No Explorer": ["Kein Expl.", "Sans Expl."],
	Background: ["Hintergrund", "Hors focus"],
	Editing: ["Texteingabe", "Saisie"],
	"Dialog open": ["Dialog", "Dialogue"],
	Unavailable: ["Gesperrt", "Bloqué"],
	Busy: ["Beschäftigt", "Occupé"],
	"No preview": ["Ohne Vorsch", "Sans aperçu"],
	"Invalid marker": ["Marker!", "Repère!"],
	Incompatible: ["Version!", "Version!"],
	"Version err": ["Version!", "Version!"],
	"Connecting…": ["Verbinden…", "Connexion…"],
	Offline: ["Offline", "Hors ligne"],
	Ready: ["Bereit", "Prêt"],
	Active: ["Aktiv", "Actif"],
	Inactive: ["Inaktiv", "Inactif"],
	Disconnected: ["Offline", "Hors ligne"],
	Pending: ["Warten…", "En cours…"],
	Failed: ["Fehler", "Échec"],
	Preview: ["Vorschau", "Aperçu"],
	Applied: ["Gesetzt", "Fixé"],
	Apply: ["Setzen", "Fixer"],
	Discard: ["Verwerfen", "Annuler"],
	Unset: ["Nicht ges.", "Non défini"],
	Start: ["Start", "Départ"],
	End: ["Ende", "Fin"],
	Gravity: ["Grav.", "Gravité"],
	Incline: ["Neigung", "Pente"],
	"Start marker": ["Start-Marker", "Repère de départ"],
	"Gravity marker": ["Schwerkraft-Marker", "Repère de gravité"],
	"Incline marker": ["Neigungs-Marker", "Repère de pente"],
	"End marker": ["End-Marker", "Repère de fin"],
	"Data mode": ["Datenmodus", "Mode"],
	Calibrated: ["Kalibriert", "Calibré"],
	Raw: ["Roh", "Brut"],
	Combined: ["Gesamt", "Norme"],
	Curve: ["Kurve", "Courbe"],
	Vertical: ["Vertikal", "Vertical"],
	Lateral: ["Quer", "Latéral"],
	Longitudinal: ["Längs", "Longitudinal"],
	"Long.": ["Längs", "Long."],
	On: ["Ein", "On"],
	Off: ["Aus", "Off"],
	Playing: ["Play", "Play"],
	Paused: ["Pause", "Pause"],
	Fine: ["Fein", "Fin"],
	Medium: ["Mittel", "Moyen"],
	Coarse: ["Grob", "Large"],
	sample: ["Sample", "sample"],
	samples: ["Samples", "samples"],
	entries: ["Einträge", "entrées"],
	preview: ["Vorschau", "aperçu"],
	previews: ["Vorschauen", "aperçus"],
	"PRESS ONLY": ["Nur Druck", "Appui seul"],
	"Reference unset": ["Referenz fehlt", "Réf. absente"],
	"Set in Analyzer": ["Im Analyzer setzen", "Définir dans Analyzer"],
	"Press: Filter · Touch: All": ["Druck: Filtern · Touch: Alle", "Appui: Filtrer · Touch: Tous"],
	"Press: Apply · Touch: Discard": ["Druck: Setzen · Touch: Verwerfen", "Appui: Fixer · Touch: Annuler"],
	"Turn: select bound": ["Drehen: Grenze", "Tourner: borne"],
	Press: ["Druck", "Appui"],
	Touch: ["Touch", "Touch"],
	All: ["Alle", "Tous"],
	Filter: ["Filtern", "Filtrer"],
	Span: ["Spanne", "Durée"],
	"Raw mode": ["Rohmodus", "Mode brut"],
	"toggle combined": ["Gesamt On/Off", "Norme On/Off"],
	"play/pause": ["Play/Pause", "Play/Pause"],
	"zoom selection": ["Auswahl-Zoom", "Zoom sélection"],
	"reset view": ["Ansicht Reset", "Reset vue"],
	"reset smoothing": ["Glättung Reset", "Reset lissage"],
	open: ["Öffnen", "Ouvrir"],
	play: ["Play", "Play"],
	pause: ["Pause", "Pause"],
	"Raw source values": ["Rohdaten", "Données brutes"],
	"Select Calibrated": ["Kalibriert wählen", "Choisir Calibré"],
	"Open unavailable": ["Öffnen gesperrt", "Ouverture bloquée"],
	"Library unavailable": ["Bibliothek gesperrt", "Bibliothèque bloquée"],
	"Reference.missing": ["Referenz fehlt", "Réf. absente"],
	"All parks": ["Alle Parks", "Tous les parcs"],
	"All statuses": ["Alle Status", "Tous les états"],
	Imported: ["Importiert", "Importé"],
	"Markers verified": ["Marker geprüft", "Repères validés"],
	"Overlays created": ["Overlays fertig", "Overlays créés"],
	"Video ready": ["Video fertig", "Vidéo prête"],
	Uploaded: ["Hochgeladen", "Envoyé"],
	Completed: ["Abgeschlossen", "Terminé"],
	"No visible curves": ["Keine Kurven sichtbar", "Aucune courbe visible"],
	"Calibrated curves": ["Kalibrierte Kurven", "Courbes calibrées"],
	"Raw curves": ["Rohkurven", "Courbes brutes"],
	Back: ["Zurück", "Retour"],
	Home: ["Home", "Home"],
	"Start app": ["App starten", "Lancer app"],
	Website: ["Website", "Site web"],
	"Step size": ["Schrittweite", "Pas"],
	"Analyzer control": ["Analyzer-Steuerung", "Commande Analyzer"],
	"Analyzer dial": ["Analyzer-Drehregler", "Molette Analyzer"],
	"Plus navigation": ["Plus-Navigation", "Navigation Plus"],
	"Analyzer InfoBar": ["Analyzer InfoBar", "InfoBar Analyzer"],
	Action: ["Aktion", "Action"],
	Direction: ["Richtung", "Direction"],
	Step: ["Schritt", "Pas"],
	"Previous / decrease": ["Zurück / verringern", "Précédent / réduire"],
	"Next / increase": ["Weiter / erhöhen", "Suivant / augmenter"],
	"First axis": ["Erste Achse", "Premier axe"],
	"Second axis": ["Zweite Achse", "Deuxième axe"],
	"Third axis": ["Dritte Achse", "Troisième axe"],
	"Calibrated mode": ["Kalibrierter Modus", "Mode calibré"],
	"Setup and troubleshooting": ["Einrichtung und Fehlerbehebung", "Installation et dépannage"],
	Park: ["Park", "Parc"],
	Status: ["Status", "État"],
	"Zoom selection": ["Auswahl-Zoom", "Zoom sélection"],
	"Sel.": ["Ausw.", "Sél."],
	"Library: open selection in new window": ["Bibliothek: neues Fenster", "Bibliothèque : nouvelle fenêtre"],
	"Library: reset filters": ["Bibliothek: Filter Reset", "Bibliothèque : reset filtres"],
	"Library: select entry": ["Bibliothek: Eintrag wählen", "Bibliothèque : choisir une entrée"],
	"Library: open selection": ["Bibliothek: Auswahl öffnen", "Bibliothèque : ouvrir la sélection"],
	"Library: import…": ["Bibliothek: Import…", "Bibliothèque : importer…"],
	"Selection: adjust boundary": ["Auswahl: Grenze verschieben", "Sélection : déplacer la borne"],
	"Step position": ["Position verschieben", "Déplacer la position"],
	"Zoom to selection": ["Auswahl-Zoom", "Zoom sur la sélection"],
	"Reset smoothing": ["Glättung zurücksetzen", "Réinitialiser le lissage"],
	"Curve / calibrated mode": ["Kurve / kalibrierter Modus", "Courbe / mode calibré"],
	"Marker: preview": ["Marker: Vorschau", "Repère : aperçu"],
	"Marker: apply": ["Marker: setzen", "Repère : fixer"],
	"Marker: discard": ["Marker: verwerfen", "Repère : annuler"],
	"− coarse (20 samples)": ["− grob (20 Samples)", "− large (20 samples)"],
	"− medium (10 samples)": ["− mittel (10 Samples)", "− moyen (10 samples)"],
	"− fine (1 sample)": ["− fein (1 Sample)", "− fin (1 sample)"],
	"+ fine (1 sample)": ["+ fein (1 Sample)", "+ fin (1 sample)"],
	"+ medium (10 samples)": ["+ mittel (10 Samples)", "+ moyen (10 samples)"],
	"+ coarse (20 samples)": ["+ grob (20 Samples)", "+ large (20 samples)"],
	"Control the active Ride Forces Analyzer Explorer and show confirmed application state.": [
		"Den aktiven Ride Forces Analyzer Explorer steuern und den bestätigten Anwendungszustand anzeigen.",
		"Contrôlez l’Explorer actif de Ride Forces Analyzer et affichez l’état confirmé de l’application.",
	],
	"Choose a Library, Explorer or marker command. Feedback follows the active Analyzer window.": [
		"Einen Bibliotheks-, Explorer- oder Marker-Befehl wählen. Anzeigen folgen dem aktiven Analyzer-Fenster.",
		"Choisissez une commande de bibliothèque, d’Explorer ou de repère. L’affichage suit la fenêtre Analyzer active.",
	],
	"Return to the first page of the bundled Plus or Neo profile.": [
		"Zur ersten Seite des mitgelieferten Plus- oder Neo-Profils zurückkehren.",
		"Revenir à la première page du profil Plus ou Neo fourni.",
	],
	"Switch the fixed Plus menu or its remembered subgroup without an Analyzer command.": [
		"Das feste Plus-Menü oder seine zuletzt genutzte Untergruppe wechseln, ohne einen Analyzer-Befehl auszuführen.",
		"Changer le menu fixe Plus ou son dernier sous-groupe sans commande Analyzer.",
	],
	"Library, position, view, smoothing, speed or marker dial from the bundled Plus profile.": [
		"Drehregler für Bibliothek, Position, Ansicht, Glättung, Tempo oder Marker aus dem mitgelieferten Plus-Profil.",
		"Molette de bibliothèque, position, vue, lissage, vitesse ou repère du profil Plus fourni.",
	],
	"Cycle position, selection and marker dials through 1, 10 and 20 samples per notch.": [
		"Position, Auswahl und Marker zwischen 1, 10 und 20 Samples pro Rastschritt umschalten.",
		"Choisir 1, 10 ou 20 samples par cran pour la position, la sélection et les repères.",
	],
	"Show contextual Analyzer state on the Neo InfoBar.": [
		"Den aktuellen Analyzer-Kontext auf der Neo InfoBar anzeigen.",
		"Afficher le contexte Analyzer sur l’InfoBar Neo.",
	],
	Adjust: ["Anpassen", "Régler"],
	"Run assigned action": ["Zugewiesene Aktion ausführen", "Exécuter l’action attribuée"],
	"Discard marker preview": ["Marker-Vorschau verwerfen", "Annuler l’aperçu du repère"],
	"Saved settings are invalid. Defaults are shown; change a selection to save valid settings.": [
		"Gespeicherte Einstellungen sind ungültig. Standardwerte werden angezeigt. Ändere eine Auswahl, um gültige Einstellungen zu speichern.",
		"Les réglages enregistrés sont invalides. Les valeurs par défaut sont affichées. Modifiez un choix pour enregistrer des réglages valides.",
	],
	"Settings connection unavailable. Changes cannot be saved. Reopen this inspector to reconnect.": [
		"Keine Verbindung für Einstellungen. Änderungen können nicht gespeichert werden. Öffne diese Ansicht erneut, um die Verbindung herzustellen.",
		"Connexion aux réglages indisponible. Les modifications ne peuvent pas être enregistrées. Rouvrez ce panneau pour rétablir la connexion.",
	],
	"Changes were not saved. Change a selection again to save.": [
		"Änderungen wurden nicht gespeichert. Ändere erneut eine Auswahl, um zu speichern.",
		"Les modifications n’ont pas été enregistrées. Modifiez de nouveau un choix pour enregistrer.",
	],
	"Enable Stream Deck in Analyzer settings. Commands affect the active Explorer while Analyzer has focus. Keys show confirmed state; unavailable commands are blocked.":
		[
			"Aktiviere Stream Deck in den Analyzer-Einstellungen. Befehle steuern den aktiven Explorer, während Analyzer im Vordergrund ist. Tasten zeigen den bestätigten Zustand; nicht verfügbare Befehle sind gesperrt.",
			"Activez Stream Deck dans les réglages Analyzer. Les commandes ciblent l’Explorer actif lorsque Analyzer est au premier plan. Les touches affichent l’état confirmé ; les commandes indisponibles sont bloquées.",
		],
	"Marker steps create a preview. Add separate Apply and Discard keys for that marker.": [
		"Marker-Schritte erzeugen eine Vorschau. Ergänze für diesen Marker eigene Tasten zum Setzen und Verwerfen.",
		"Les pas de repère créent un aperçu. Ajoutez des touches distinctes pour fixer ou annuler ce repère.",
	],
};

let language: Language = "en";

/**
 * Select the Stream Deck UI language, using English for unsupported locales.
 * @param value Native language code, optionally including a region.
 */
export function setLanguage(value: string): void {
	const base = value.toLowerCase().split(/[-_]/)[0];
	language = base === "de" || base === "fr" ? base : "en";
}

/**
 * Read the active presentation language without depending on the native host.
 * @returns Selected supported language.
 */
export function getLanguage(): Language {
	return language;
}

/**
 * Translate a known presentation phrase; opaque application values stay unchanged.
 * @param source English presentation phrase to look up.
 * @param locale Desired language, defaulting to the Stream Deck language.
 * @returns Translated phrase or the original text when no translation exists.
 */
export function translate(source: string, locale: Language = language): string {
	return locale === "en" ? source : (TRANSLATIONS[source]?.[locale === "de" ? 0 : 1] ?? source);
}

/**
 * Translate composed device text while retaining numeric and position values.
 * @param source Composed presentation text, never an opaque recording or park name.
 * @param locale Desired language, defaulting to the Stream Deck language.
 * @returns Translated caption retaining its separators and confirmed numeric values.
 */
export function displayText(source: string, locale: Language = language): string {
	if (locale === "en") return source;
	const exact = translate(source, locale);
	if (exact !== source) return exact;
	for (const separator of ["\n", " · ", " / "])
		if (source.includes(separator))
			return source
				.split(separator)
				.map((part) => displayText(part, locale))
				.join(separator);
	const prefix = /^(Press|Touch|Active): (.*)$/.exec(source);
	if (prefix) return `${translate(prefix[1]!, locale)}: ${displayText(prefix[2]!, locale)}`;
	const applied = /^(Applied|Span) (.*)$/.exec(source);
	if (applied) return `${translate(applied[1]!, locale)} ${applied[2]}`;
	const quantity = /^(\d+) (sample|samples|entries|preview|previews)$/.exec(source);
	if (quantity) return `${quantity[1]} ${translate(quantity[2]!, locale)}`;
	const parameter = /^(Speed|Smooth|Selection|Sel\.|Start|Gravity|Incline|End|Curve) (.*)$/.exec(source);
	if (parameter) {
		const tail = parameter[2] === "start" ? "Start" : parameter[2] === "end" ? "End" : parameter[2]!;
		return `${translate(parameter[1]!, locale)} ${translate(tail, locale)}`;
	}
	return source;
}

/**
 * Select the declared bundled profile matching the current Stream Deck language.
 * @param device Bundled device profile family.
 * @param locale Desired language, defaulting to the Stream Deck language.
 * @returns Relative profile name declared in the generated manifest.
 */
export function profilePath(device: "mobile" | "neo" | "plus", locale: Language = language): string {
	return `profiles/${device}${locale === "en" ? "" : `-${locale}`}`;
}
