import { loadFont } from "@remotion/fonts";
import { staticFile } from "remotion";

loadFont({ family: "Anton", url: staticFile("fonts/Anton-Regular.ttf") });
loadFont({ family: "Inter", url: staticFile("fonts/Inter.ttf"), weight: "100 900" });

export const C = {
  bg: "#1B1036",
  bg2: "#2C1A57",
  text: "#FFF7EC",
  pink: "#FF4D8D",
  yellow: "#FFD23F",
  mint: "#3DDC97",
};

export const HEAD = "Anton, Impact, sans-serif";
export const BODY = "Inter, Arial, sans-serif";

// Sichere Zone für TikTok/Reels (UI unten und rechts)
export const SAFE = { left: 90, right: 150, top: 260, bottom: 420 };
