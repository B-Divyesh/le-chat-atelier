import React, { useMemo } from "react";
import { interpolate } from "remotion";
import { C, GENRE_BG, GLIDE, HEX, PICO, clamp, pixel } from "../theme";
import { Run, matchFrames, parseFrame } from "../lib/frames";
import catRaw from "../mistralCat.json";

// Le Chat: Mistral's pixel cat, exact pixels and colours from mistral.ai, animated at its native 150 ms per frame
type Cat = { w: number; h: number; palette: Record<string, string>; frames: string[][] };
const CAT = catRaw as unknown as Cat;
export const catFrameAt = (videoFrame: number, fps = 30) => Math.floor((videoFrame / fps) * (1000 / 150)) % CAT.frames.length;

// cell = true: fits one game cell (1x1, sitting on the floor); otherwise drawn in its own 16x16 units
export const CatRects: React.FC<{ frame: number; cell?: boolean }> = ({ frame, cell = false }) => {
  const u = cell ? 1 / CAT.w : 1;
  const oy = cell ? (CAT.w - CAT.h) / CAT.w : CAT.w - CAT.h;
  return (
    <>
      {CAT.frames[frame % CAT.frames.length].flatMap((row, y) =>
        [...row].map((ch, x) =>
          ch === "." ? null : (
            <rect key={`${x}-${y}`} x={x * u} y={oy + y * u} width={u * 1.03} height={u * 1.03} fill={CAT.palette[ch]} />
          ),
        ),
      )}
    </>
  );
};

export const MistralCat: React.FC<{ size: number; frame: number; glow?: boolean; rowsVisible?: number }> = ({ size, frame, glow = false, rowsVisible }) => {
  const clip = rowsVisible === undefined ? 16 : (CAT.w - CAT.h) + Math.max(0, Math.min(CAT.h, rowsVisible));
  return (
    <svg viewBox={`0 0 ${CAT.w} ${CAT.w}`} width={size} height={size} shapeRendering="crispEdges"
      style={{ overflow: "visible", filter: glow ? `drop-shadow(0 0 ${size / 12}px rgba(255,138,31,.5))` : undefined }}>
      <defs>
        <clipPath id={`catclip-${Math.round(clip * 10)}`}>
          <rect x={-1} y={-1} width={CAT.w + 2} height={clip + 1} />
        </clipPath>
      </defs>
      <g clipPath={`url(#catclip-${Math.round(clip * 10)})`}>
        <CatRects frame={frame} />
      </g>
      {rowsVisible !== undefined && rowsVisible < CAT.h ? (
        <rect x={-0.5} y={clip} width={CAT.w + 1} height={0.22} fill={C.accent} />
      ) : null}
    </svg>
  );
};

// an 8x8 sprite written by the sprite model; rowsVisible < 8 shows it being written row by row
export const SpriteRects: React.FC<{ rows: string[]; rowsVisible?: number }> = ({ rows, rowsVisible = 8 }) => {
  const shown = Math.min(8, Math.max(0, rowsVisible));
  return (
    <>
      {rows.slice(0, Math.ceil(shown)).flatMap((row, y) =>
        [...row].map((ch, x) =>
          ch === "." ? null : (
            <rect
              key={`${x}-${y}`}
              x={x}
              y={y}
              width={1.03}
              height={1.03}
              fill={PICO[HEX.indexOf(ch)]}
              opacity={y === Math.ceil(shown) - 1 && shown < 8 ? shown - Math.floor(shown) || 1 : 1}
            />
          ),
        ),
      )}
    </>
  );
};

export const Sprite: React.FC<{ rows: string[]; size: number; rowsVisible?: number; glow?: boolean }> = ({
  rows,
  size,
  rowsVisible = 8,
  glow = false,
}) => (
  <svg
    viewBox="0 0 8 8"
    width={size}
    height={size}
    shapeRendering="crispEdges"
    style={{ overflow: "visible", filter: glow ? `drop-shadow(0 0 ${size / 14}px rgba(255,138,31,.55))` : undefined }}
  >
    <SpriteRects rows={rows} rowsVisible={rowsVisible} />
    {rowsVisible < 8 && rowsVisible > 0 ? (
      <rect x={-0.3} y={Math.min(7.85, rowsVisible)} width={8.6} height={0.12} fill={C.accent} opacity={0.9} />
    ) : null}
  </svg>
);

const specks = Array.from({ length: 70 }, (_, i) => ({ x: (i * 7.31) % 16, y: (i * 3.77) % 12 }));

// a game screen redrawn from the model's real SVG frames; sprites glide between consecutive model frames
export const GameView: React.FC<{
  run: Run;
  t: number; // local video frame
  framesPerStep: number;
  width: number;
  startStep?: number;
  hud?: boolean;
  radius?: number;
}> = ({ run, t, framesPerStep, width, startStep = 0, hud = true, radius = 18 }) => {
  const parsed = useMemo(() => run.frames.map((f) => parseFrame(f.svg)), [run]);
  const pos = Math.max(0, t / framesPerStep) + startStep;
  const i = Math.min(parsed.length - 2, Math.floor(pos));
  const p = Math.min(1, pos - i);
  const tweens = useMemo(() => matchFrames(parsed[i].items, parsed[i + 1].items), [parsed, i]);
  const e = GLIDE(Math.min(1, p * 1.25));
  const bg = GENRE_BG[run.genre] ?? C.panel;
  return (
    <svg
      viewBox="0 0 16 12"
      width={width}
      height={(width * 3) / 4}
      shapeRendering="crispEdges"
      style={{ background: bg, borderRadius: radius, display: "block" }}
    >
      {specks.map((s, k) => (
        <rect key={k} x={s.x} y={s.y} width={0.1} height={0.1} fill="#fff" opacity={run.genre === "shooter" ? 0.55 : 0.12} />
      ))}
      {tweens.map((w, k) => {
        const rows = run.sprites[w.k];
        if (w.k === "hero") {
          const hx = w.x0 + (w.x1 - w.x0) * e, hy = w.y0 + (w.y1 - w.y0) * e;
          return (
            <g key={k} transform={`translate(${hx} ${hy})`} style={{ filter: "drop-shadow(0 0 0.07px rgba(255,255,255,.95)) drop-shadow(0 0 0.2px rgba(255,241,232,.5))" }}>
              <CatRects frame={catFrameAt(t)} cell />
            </g>
          );
        }
        if (!rows) return null;
        const x = w.x0 + (w.x1 - w.x0) * e;
        const y = w.y0 + (w.y1 - w.y0) * e;
        const a = w.a0 + (w.a1 - w.a0) * e;
        return (
          <g key={k} transform={`translate(${x} ${y}) scale(0.125)`} opacity={a}>
            <SpriteRects rows={rows} />
          </g>
        );
      })}
      {hud ? (
        <text
          x={0.3}
          y={0.85}
          fontFamily={pixel}
          fontSize={0.62}
          fill="#FFF1E8"
          stroke="#000"
          strokeWidth={0.12}
          paintOrder="stroke"
        >
          {(p < 0.5 ? parsed[i] : parsed[i + 1]).hud}
        </text>
      ) : null}
    </svg>
  );
};

export const fadeUp = (frame: number, start: number, dur = 18) => ({
  opacity: interpolate(frame, [start, start + dur], [0, 1], { ...clamp }),
  translate: interpolate(frame, [start, start + dur], ["0px 36px", "0px 0px"], { ...clamp, easing: GLIDE }),
});
