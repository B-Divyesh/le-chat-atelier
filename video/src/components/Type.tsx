import React from "react";
import { interpolate, useCurrentFrame } from "remotion";
import { C, EASE, clamp, display, pixel } from "../theme";

// kinetic headline: each word rises out of a mask, staggered
export const Words: React.FC<{
  text: string;
  start: number;
  size: number;
  stagger?: number;
  color?: string;
  accentWords?: string[];
  weight?: number;
  align?: "left" | "center";
}> = ({ text, start, size, stagger = 3, color = C.ink, accentWords = [], weight = 700, align = "left" }) => {
  const frame = useCurrentFrame();
  const words = text.split(" ");
  return (
    <div
      style={{
        display: "flex",
        flexWrap: "wrap",
        justifyContent: align === "center" ? "center" : "flex-start",
        columnGap: size * 0.26,
        fontFamily: display,
        fontWeight: weight,
        fontSize: size,
        lineHeight: 1.05,
        letterSpacing: -size * 0.03,
      }}
    >
      {words.map((w, i) => {
        const s = start + i * stagger;
        const clean = w.replace(/[^\w']/g, "");
        return (
          <span key={i} style={{ display: "inline-block", overflow: "hidden", paddingBottom: size * 0.12 }}>
            <span
              style={{
                display: "inline-block",
                color: accentWords.includes(clean) ? C.accent : color,
                translate: interpolate(frame, [s, s + 22], ["0px 110%", "0px 0%"], { ...clamp, easing: EASE }),
              }}
            >
              {w}
            </span>
          </span>
        );
      })}
    </div>
  );
};

// small uppercase label with a growing rule, used to open each section
export const Kicker: React.FC<{ text: string; start: number }> = ({ text, start }) => {
  const frame = useCurrentFrame();
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 18,
        fontFamily: pixel,
        fontSize: 26,
        letterSpacing: 3,
        color: C.accent,
        opacity: interpolate(frame, [start, start + 12], [0, 1], clamp),
      }}
    >
      <div
        style={{
          height: 3,
          background: C.accent,
          width: interpolate(frame, [start, start + 20], [0, 64], { ...clamp, easing: EASE }),
        }}
      />
      {text}
    </div>
  );
};

export const Fade: React.FC<{ start: number; dur?: number; children: React.ReactNode; style?: React.CSSProperties }> = ({
  start,
  dur = 16,
  children,
  style,
}) => {
  const frame = useCurrentFrame();
  return (
    <div
      style={{
        ...style,
        opacity: interpolate(frame, [start, start + dur], [0, 1], clamp),
        translate: interpolate(frame, [start, start + dur + 8], ["0px 28px", "0px 0px"], { ...clamp, easing: EASE }),
      }}
    >
      {children}
    </div>
  );
};
