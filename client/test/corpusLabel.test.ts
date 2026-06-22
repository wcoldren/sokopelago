import { describe, expect, it } from "vitest";

import { corpusLabel } from "../src/corpusLabel";

describe("corpusLabel", () => {
  it("labels the bundled corpora (tabs)", () => {
    expect(corpusLabel("microban")).toBe("Microban");
    expect(corpusLabel("microban2")).toBe("Microban II");
    expect(corpusLabel("microban3")).toBe("Microban III");
    expect(corpusLabel("pullban")).toBe("Pullban");
    expect(corpusLabel("autoban")).toBe("Autoban");
    expect(corpusLabel("curated")).toBe("Curated");
    expect(corpusLabel("xsokoban90")).toBe("XSokoban");
  });

  it("renders Sasquatch numbers as roman numerals", () => {
    expect(corpusLabel("sasquatch1")).toBe("Sasquatch I");
    expect(corpusLabel("sasquatch3")).toBe("Sasquatch III");
    expect(corpusLabel("sasquatch9")).toBe("Sasquatch IX");
  });

  it("falls back to the raw name for unknown corpora", () => {
    expect(corpusLabel("mystery")).toBe("mystery");
  });
});
