import { describe, expect, it } from "vitest";

import {
  RATING_SCHEMA,
  buildRatingEvent,
  validateRatingEvent,
  type RatingInput,
} from "../src/potd/rating";

const goodInput: RatingInput = {
  date: "2026-06-21",
  corpus: "microban",
  levelN: 12,
  handle: "boxpusher",
  visitorId: "v-abc",
  sessionId: "s-abc",
  solved: true,
  attempts: 2,
  moves: 40,
  pushes: 18,
  timeMs: 53000,
  usedHint: false,
  fun: 4,
  difficulty: 3,
  clientVersion: "0.8.0",
};

describe("buildRatingEvent", () => {
  it("stamps the schema and round-trips through validation", () => {
    const ev = buildRatingEvent(goodInput);
    expect(ev.schema).toBe(RATING_SCHEMA);
    expect(ev.levelN).toBe(12);
    expect(validateRatingEvent(ev)).toBe(true);
  });
});

describe("validateRatingEvent", () => {
  it("accepts a well-formed event (including an unsolved give-up)", () => {
    expect(validateRatingEvent(buildRatingEvent(goodInput))).toBe(true);
    expect(
      validateRatingEvent(buildRatingEvent({ ...goodInput, solved: false, moves: 0, pushes: 0 })),
    ).toBe(true);
  });

  it("rejects non-objects and a missing/wrong schema", () => {
    expect(validateRatingEvent(null)).toBe(false);
    expect(validateRatingEvent("nope")).toBe(false);
    expect(validateRatingEvent({ ...buildRatingEvent(goodInput), schema: "other" })).toBe(false);
  });

  it("rejects a malformed date", () => {
    expect(validateRatingEvent({ ...buildRatingEvent(goodInput), date: "2026-6-21" })).toBe(false);
    expect(validateRatingEvent({ ...buildRatingEvent(goodInput), date: "June 21" })).toBe(false);
  });

  it("rejects out-of-range fun/difficulty and non-integer ratings", () => {
    for (const bad of [0, 6, 3.5, -1, "4"]) {
      expect(validateRatingEvent({ ...buildRatingEvent(goodInput), fun: bad })).toBe(false);
      expect(validateRatingEvent({ ...buildRatingEvent(goodInput), difficulty: bad })).toBe(false);
    }
  });

  it("rejects bad levelN, negative metrics, empty handle/visitorId, and non-boolean flags", () => {
    expect(validateRatingEvent({ ...buildRatingEvent(goodInput), levelN: 0 })).toBe(false);
    expect(validateRatingEvent({ ...buildRatingEvent(goodInput), levelN: 1.5 })).toBe(false);
    expect(validateRatingEvent({ ...buildRatingEvent(goodInput), moves: -1 })).toBe(false);
    expect(validateRatingEvent({ ...buildRatingEvent(goodInput), timeMs: Infinity })).toBe(false);
    expect(validateRatingEvent({ ...buildRatingEvent(goodInput), handle: "" })).toBe(false);
    expect(validateRatingEvent({ ...buildRatingEvent(goodInput), visitorId: "" })).toBe(false);
    expect(validateRatingEvent({ ...buildRatingEvent(goodInput), solved: "yes" })).toBe(false);
    expect(validateRatingEvent({ ...buildRatingEvent(goodInput), usedHint: 1 })).toBe(false);
  });

  it("is tagged schema v2 and carries the visitorId", () => {
    const ev = buildRatingEvent(goodInput);
    expect(ev.schema).toBe("sokopelago-potd-rating/2");
    expect(ev.visitorId).toBe("v-abc");
  });
});
