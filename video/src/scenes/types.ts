export type Scene =
  | { type: "yearRoll"; frames: number; headline: string; from: number; to: number; sub?: string }
  | { type: "bigWord"; frames: number; word: string; sub?: string; bar?: boolean }
  | { type: "swap"; frames: number; label: string; oldWord: string; newWord: string; sub: string }
  | { type: "statement"; frames: number; lines: string[]; accent?: number }
  | { type: "question"; frames: number; lead: string; word: string; options: [string, string]; cta: string };

export type StoryProps = {
  handle: string;
  retro: boolean;
  scenes: Scene[];
};
