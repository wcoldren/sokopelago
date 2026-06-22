/** Friendly display name for a bundled corpus — used by the solo corpus tabs. */
const ROMAN = ["", "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX"];
const LABELS: Record<string, string> = {
  microban: "Microban",
  microban2: "Microban II",
  microban3: "Microban III",
  pullban: "Pullban",
  autoban: "Autoban",
  xsokoban90: "XSokoban",
  curated: "Curated",
};

export function corpusLabel(name: string): string {
  if (name.startsWith("sasquatch")) {
    const n = Number(name.slice("sasquatch".length));
    return `Sasquatch ${ROMAN[n] ?? n}`;
  }
  return LABELS[name] ?? name;
}
