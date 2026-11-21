import { Easing } from "remotion";
import { loadFont as loadGrotesk } from "@remotion/google-fonts/SpaceGrotesk";
import { loadFont as loadMono } from "@remotion/google-fonts/JetBrainsMono";
import { loadFont as loadPixel } from "@remotion/google-fonts/Silkscreen";

export const display = loadGrotesk("normal", { weights: ["500", "700"], subsets: ["latin"] }).fontFamily;
export const mono = loadMono("normal", { weights: ["400", "700"], subsets: ["latin"] }).fontFamily;
export const pixel = loadPixel("normal", { weights: ["400"], subsets: ["latin"] }).fontFamily;

export const C = {
  bg: "#0D0C14",
  panel: "#16141F",
  line: "#2B2839",
  ink: "#FFF4EA",
  muted: "#A49CBF",
  accent: "#FF8A1F",
  gold: "#FFD23F",
  teal: "#2DD4BF",
};

export const PICO = ["#000000", "#1D2B53", "#7E2553", "#008751", "#AB5236", "#5F574F", "#C2C3C7", "#FFF1E8",
  "#FF004D", "#FFA300", "#FFEC27", "#00E436", "#29ADFF", "#83769C", "#FF77A8", "#FFCCAA"];
export const HEX = "0123456789abcdef";

// expo-out for entrances, smooth in-out for glides
export const EASE = Easing.bezier(0.16, 1, 0.3, 1);
export const GLIDE = Easing.bezier(0.45, 0, 0.2, 1);
export const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;

export const GENRE_BG: Record<string, string> = {
  survivors: "#3B3654",
  snake: "#1D2B53",
  shooter: "#05040A",
  dodge: "#4A4540",
  platformer: "#29ADFF",
};
