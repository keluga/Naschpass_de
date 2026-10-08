import { StoryProps } from "../scenes/types";

// Fakten aus Post #05 (Quellen: en.wikipedia.org/wiki/Twix)
export const raider: StoryProps = {
  handle: "NASCHPASS",
  retro: true,
  scenes: [
    { type: "yearRoll", frames: 90, headline: "Zurück ins Jahr", from: 2026, to: 1990, sub: "Da gab es noch diesen Riegel:" },
    { type: "bigWord", frames: 75, word: "RAIDER", sub: "Kennst du ihn noch?", bar: true },
    { type: "swap", frames: 90, label: "1991:", oldWord: "RAIDER", newWord: "TWIX", sub: "Aus Raider wurde Twix." },
    { type: "statement", frames: 60, lines: ["Gleicher Riegel.", "Neuer Name."], accent: 1 },
    { type: "statement", frames: 75, lines: ["Im Norden", "hielt Raider durch:", "bis 2000."], accent: 2 },
    { type: "question", frames: 105, lead: "Sagst du heute noch", word: "RAIDER?", options: ["RAIDER", "TWIX"], cta: "Schreib's in die Kommentare." },
  ],
};
