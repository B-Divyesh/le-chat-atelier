import React, { useMemo } from "react";
import { AbsoluteFill, Sequence, interpolate, useCurrentFrame } from "remotion";
import { C, EASE, GENRE_BG, clamp, display, mono, pixel } from "../theme";
import { data, matchFrames, parseFrame, run } from "../lib/frames";
import { CatRects, GameView, MistralCat, Sprite, SpriteRects, catFrameAt } from "../components/Pixels";
import { Fade, Kicker, Words } from "../components/Type";

const SURV = run("survivors");

const Backdrop: React.FC = () => (
  <AbsoluteFill
    style={{
      backgroundColor: C.bg,
      backgroundImage: `linear-gradient(${C.line}33 1px, transparent 1px), linear-gradient(90deg, ${C.line}33 1px, transparent 1px)`,
      backgroundSize: "60px 60px",
    }}
  >
    <AbsoluteFill style={{ background: "radial-gradient(ellipse at 50% 40%, rgba(255,138,31,0.08), transparent 60%)" }} />
    <AbsoluteFill style={{ background: "radial-gradient(ellipse at center, transparent 55%, rgba(0,0,0,0.6))" }} />
  </AbsoluteFill>
);

const Pill: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <div
    style={{
      fontFamily: mono,
      fontSize: 28,
      color: C.ink,
      border: `2px solid ${C.line}`,
      background: C.panel,
      borderRadius: 999,
      padding: "12px 26px",
    }}
  >
    {children}
  </div>
);

// ---------------------------------------------------------------- 1. cold open
export const ColdOpen: React.FC = () => (
  <AbsoluteFill>
    <Backdrop />
    <AbsoluteFill style={{ justifyContent: "center", padding: "0 160px", gap: 6 }}>
      <Words text="What if a language model" start={6} size={112} />
      <Words text="was the game engine?" start={20} size={112} accentWords={["game", "engine"]} />
    </AbsoluteFill>
  </AbsoluteFill>
);

// ---------------------------------------------------------------- 2. title
export const Title: React.FC = () => {
  const frame = useCurrentFrame();
  return (
    <AbsoluteFill>
      <Backdrop />
      <AbsoluteFill style={{ justifyContent: "center", alignItems: "center", gap: 34 }}>
        <div style={{ scale: interpolate(frame, [0, 40], [0.86, 1], { ...clamp, easing: EASE, output: "perceptual-scale" }) }}>
          <MistralCat size={300} frame={catFrameAt(frame)} rowsVisible={interpolate(frame, [4, 40], [0, 13], clamp)} glow />
        </div>
        <Words text="Le Chat Atelier" start={30} size={156} align="center" />
        <Fade start={48}>
          <div style={{ fontFamily: display, fontWeight: 500, fontSize: 46, color: C.muted, textAlign: "center" }}>
            A world model that renders games as SVG, built on Ministral 3B
          </div>
        </Fade>
        <Fade start={62} style={{ display: "flex", gap: 18 }}>
          <Pill>3 models</Pill>
          <Pill>5 game genres</Pill>
          <Pill>2× H100</Pill>
        </Fade>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};

// ---------------------------------------------------------------- 3. how it works
const NODES = [
  { tag: "INPUT", title: "Your prompt", desc: "“Le Chat survives a haunted cheese dungeon”" },
  { tag: "DIRECTOR", title: "Designs the world", desc: "genre, cast, items and story as JSON" },
  { tag: "SPRITE MODEL", title: "Draws every sprite", desc: "8×8 pixel art, about 60 tokens each" },
  { tag: "WORLD MODEL", title: "Writes every frame", desc: "SVG frame + key → next SVG" },
];
export const HowItWorks: React.FC = () => {
  const frame = useCurrentFrame();
  const cardW = 390;
  const gap = 70;
  const left = (1920 - (cardW * 4 + gap * 3)) / 2;
  const top = 470;
  const step = Math.floor(Math.max(0, frame - 120) / 9) + 12;
  return (
    <AbsoluteFill>
      <Backdrop />
      <div style={{ position: "absolute", left: 160, top: 130 }}>
        <Kicker text="HOW IT WORKS" start={0} />
        <div style={{ height: 22 }} />
        <Words text="Three models. One loop." start={6} size={100} />
      </div>
      <svg width={1920} height={1080} style={{ position: "absolute", inset: 0 }}>
        {[0, 1, 2].map((i) => {
          const x1 = left + cardW * (i + 1) + gap * i + 8;
          const x2 = x1 + gap - 16;
          const s = 44 + i * 14;
          return (
            <g key={i} opacity={interpolate(frame, [s, s + 6], [0, 1], clamp)}>
              <line
                x1={x1}
                y1={top + 130}
                x2={x2}
                y2={top + 130}
                stroke={C.accent}
                strokeWidth={4}
                strokeDasharray={60}
                strokeDashoffset={interpolate(frame, [s, s + 16], [60, 0], { ...clamp, easing: EASE })}
              />
              <path d={`M ${x2 - 2} ${top + 120} L ${x2 + 10} ${top + 130} L ${x2 - 2} ${top + 140}`} fill="none" stroke={C.accent} strokeWidth={4} />
            </g>
          );
        })}
        {(() => {
          const x = left + (cardW + gap) * 3 + cardW / 2;
          const d = `M ${x + 120} ${top + 302} C ${x + 120} ${top + 410}, ${x - 120} ${top + 410}, ${x - 120} ${top + 312}`;
          return (
            <path
              d={d}
              fill="none"
              stroke={C.gold}
              strokeWidth={4}
              strokeDasharray={420}
              strokeDashoffset={interpolate(frame, [96, 130], [420, 0], { ...clamp, easing: EASE })}
            />
          );
        })()}
      </svg>
      {NODES.map((n, i) => {
        const s = 26 + i * 12;
        return (
          <div
            key={i}
            style={{
              position: "absolute",
              left: left + (cardW + gap) * i,
              top,
              width: cardW,
              height: 290,
              background: i === 3 ? "linear-gradient(160deg, #2a1d10, #16141F 60%)" : C.panel,
              border: `2px solid ${i === 3 ? C.accent : C.line}`,
              borderRadius: 22,
              padding: "28px 30px",
              boxSizing: "border-box",
              opacity: interpolate(frame, [s, s + 12], [0, 1], clamp),
              scale: interpolate(frame, [s, s + 22], [0.9, 1], { ...clamp, easing: EASE, output: "perceptual-scale" }),
            }}
          >
            <div style={{ fontFamily: pixel, fontSize: 22, color: C.accent, letterSpacing: 2 }}>{n.tag}</div>
            <div style={{ fontFamily: display, fontWeight: 700, fontSize: 42, color: C.ink, marginTop: 14 }}>{n.title}</div>
            <div style={{ fontFamily: display, fontSize: 27, color: C.muted, marginTop: 10, lineHeight: 1.25 }}>{n.desc}</div>
          </div>
        );
      })}
      <div
        style={{
          position: "absolute",
          left: left + (cardW + gap) * 3,
          width: cardW,
          top: top + 415,
          textAlign: "center",
          fontFamily: mono,
          fontSize: 30,
          color: C.gold,
          opacity: interpolate(frame, [118, 130], [0, 1], clamp),
        }}
      >
        frame {step} → {step + 1}
      </div>
    </AbsoluteFill>
  );
};

// ---------------------------------------------------------------- 4. prompt -> world
const ORDER = ["hero", "e1", "e2", "e3", "o1", "o2", "gem", "b"];
export const PromptToWorld: React.FC = () => {
  const frame = useCurrentFrame();
  const prompt = SURV.prompt;
  const chars = Math.floor(interpolate(frame, [12, 58], [0, prompt.length], clamp));
  const lines: [string, string][] = [
    ["title", `"${SURV.title}"`],
    ["genre", `"${SURV.director_genre}"`],
    ["enemies", `["${SURV.names.e1}", "${SURV.names.e2}"]`],
    ["obstacles", `["${SURV.names.o1}"]`],
    ["gem", `"${SURV.names.gem}"`],
  ];
  return (
    <AbsoluteFill>
      <Backdrop />
      <div style={{ position: "absolute", left: 130, top: 170, width: 880 }}>
        <Kicker text="1 · DESIGN" start={0} />
        <div
          style={{
            marginTop: 30,
            background: C.panel,
            border: `2px solid ${C.line}`,
            borderRadius: 20,
            padding: "26px 30px",
            fontFamily: display,
            fontSize: 46,
            color: C.ink,
            minHeight: 150,
            opacity: interpolate(frame, [2, 12], [0, 1], clamp),
          }}
        >
          {prompt.slice(0, chars)}
          <span style={{ color: C.accent, opacity: frame % 16 < 9 ? 1 : 0 }}>▍</span>
        </div>
        <div
          style={{
            marginTop: 26,
            background: "#0A0910",
            border: `2px solid ${C.line}`,
            borderRadius: 20,
            padding: "24px 30px",
            fontFamily: mono,
            fontSize: 30,
            lineHeight: 1.65,
            color: C.muted,
            opacity: interpolate(frame, [60, 70], [0, 1], clamp),
          }}
        >
          <div style={{ color: C.accent, fontFamily: pixel, fontSize: 20, marginBottom: 8 }}>
            DIRECTOR · {(SURV.design_ms / 1000).toFixed(1)} s
          </div>
          {lines.map(([k, v], i) => (
            <div key={k} style={{ opacity: interpolate(frame, [68 + i * 6, 78 + i * 6], [0, 1], clamp) }}>
              <span style={{ color: C.teal }}>"{k}"</span>: <span style={{ color: C.ink }}>{v}</span>
            </div>
          ))}
        </div>
      </div>
      <div style={{ position: "absolute", left: 1080, top: 170, width: 720 }}>
        <Kicker text="2 · DRAW" start={66} />
        <div style={{ marginTop: 30, display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 22 }}>
          {ORDER.map((k, i) => {
            const s = 80 + i * 7;
            return (
              <div key={k} style={{ textAlign: "center", opacity: interpolate(frame, [s - 4, s + 4], [0, 1], clamp) }}>
                <div
                  style={{
                    background: "linear-gradient(160deg, #D9D3E6, #A9A1C2)",
                    border: `2px solid ${C.line}`,
                    borderRadius: 16,
                    padding: 22,
                    display: "flex",
                    justifyContent: "center",
                  }}
                >
                  {k === "hero" ? (
                    <MistralCat size={124} frame={catFrameAt(frame)} rowsVisible={interpolate(frame, [s, s + 22], [0, 13], clamp)} />
                  ) : (
                    <Sprite rows={SURV.sprites[k]} size={124} rowsVisible={interpolate(frame, [s, s + 22], [0, 8], clamp)} />
                  )}
                </div>
                <div style={{ fontFamily: display, fontSize: 22, color: C.muted, marginTop: 12, lineHeight: 1.2, height: 56 }}>
                  {k === "hero" ? "Le Chat (Mistral's pixel cat)" : SURV.names[k]}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </AbsoluteFill>
  );
};

// ---------------------------------------------------------------- 5. the loop
const STEP = 12;
export const TheLoop: React.FC = () => {
  const frame = useCurrentFrame();
  const t = Math.max(0, frame - 24);
  const i = Math.min(SURV.frames.length - 2, Math.floor(t / STEP) + 1);
  const p = (t % STEP) / STEP;
  const input = SURV.frames[i].svg;
  const out = SURV.frames[i + 1].svg;
  const action = SURV.frames[i + 1].action;
  const typed = out.slice(0, Math.floor(out.length * Math.min(1, p * 1.5)));
  const code: React.CSSProperties = { fontFamily: mono, fontSize: 19, lineHeight: 1.45, color: C.muted, wordBreak: "break-all" };
  return (
    <AbsoluteFill>
      <Backdrop />
      <div style={{ position: "absolute", left: 120, top: 80 }}>
        <Kicker text="3 · SIMULATE" start={0} />
        <div style={{ height: 18 }} />
        <Words text="The current frame plus your key gives the next frame" start={4} size={58} stagger={2} />
      </div>
      <Fade start={14} style={{ position: "absolute", left: 120, top: 300, width: 720 }}>
        <div style={{ background: "#0A0910", border: `2px solid ${C.line}`, borderRadius: 20, padding: 26, height: 300, overflow: "hidden" }}>
          <div style={{ fontFamily: pixel, fontSize: 20, color: C.teal, marginBottom: 10 }}>INPUT</div>
          <div style={{ fontFamily: mono, fontSize: 26, color: C.accent, marginBottom: 8 }}>{action}</div>
          <div style={code}>{input}</div>
        </div>
        <div
          style={{
            marginTop: 22,
            background: "#0A0910",
            border: `2px solid ${C.accent}`,
            borderRadius: 20,
            padding: 26,
            height: 300,
            overflow: "hidden",
          }}
        >
          <div style={{ fontFamily: pixel, fontSize: 20, color: C.accent, marginBottom: 10 }}>OUTPUT · WRITTEN BY THE MODEL</div>
          <div style={{ ...code, color: "#7CFFB0" }}>{typed}</div>
        </div>
      </Fade>
      <Fade start={20} style={{ position: "absolute", left: 900, top: 300 }}>
        <div style={{ borderRadius: 22, border: `3px solid ${C.line}`, overflow: "hidden", boxShadow: "0 30px 80px rgba(0,0,0,.5)" }}>
          <GameView run={SURV} t={t} framesPerStep={STEP} width={900} startStep={1} radius={0} />
        </div>
      </Fade>
      <Fade start={150} style={{ position: "absolute", left: 900, top: 1000 - 30, width: 900 }}>
        <div style={{ fontFamily: display, fontSize: 32, color: C.ink, textAlign: "center" }}>
          No game engine in the loop: <span style={{ color: C.accent }}>the model writes the whole frame</span>.
        </div>
      </Fade>
    </AbsoluteFill>
  );
};

// ---------------------------------------------------------------- 6. five genres
const RULES: Record<string, string> = {
  survivors: "Enemies chase you, each with its own rules. Hits cost HP, kills drop gems.",
  snake: "The body follows the head. It grows when it eats, and it never reverses.",
  shooter: "Your ship auto-fires as enemies descend. Landings cost HP.",
  dodge: "Obstacles and coins fall. Weave through, collect, survive.",
  platformer: "Gravity, jumps and platforms. The HUD carries your velocity.",
};
const GENRES = ["survivors", "snake", "shooter", "dodge", "platformer"];
export const GENRE_LEN = 66;
const GenreCard: React.FC<{ g: string; index: number }> = ({ g, index }) => {
  const frame = useCurrentFrame();
  const r = run(g);
  return (
    <AbsoluteFill>
      <div
        style={{
          position: "absolute",
          left: 120,
          top: 250,
          borderRadius: 24,
          overflow: "hidden",
          border: `3px solid ${C.line}`,
          boxShadow: "0 30px 90px rgba(0,0,0,.55)",
          opacity: interpolate(frame, [0, 8], [0, 1], clamp),
          translate: interpolate(frame, [0, 20], ["80px 0px", "0px 0px"], { ...clamp, easing: EASE }),
        }}
      >
        <GameView run={r} t={frame} framesPerStep={7} width={980} startStep={1} radius={0} />
      </div>
      <div style={{ position: "absolute", left: 1180, top: 300, width: 640 }}>
        <div style={{ fontFamily: pixel, fontSize: 28, color: C.muted, opacity: interpolate(frame, [2, 10], [0, 1], clamp) }}>
          0{index + 1} / 05
        </div>
        <div style={{ height: 14 }} />
        <Words text={g.toUpperCase()} start={4} size={112} color={C.accent} />
        <Fade start={12}>
          <div style={{ fontFamily: display, fontSize: 38, color: C.ink, lineHeight: 1.3, marginTop: 10 }}>{RULES[g]}</div>
        </Fade>
        <Fade start={20}>
          <div style={{ fontFamily: mono, fontSize: 24, color: C.muted, marginTop: 36, lineHeight: 1.5 }}>
            “{r.prompt}”
            <br />
            <span style={{ color: C.gold }}>→ {r.title.replace("’", "'")}</span>
          </div>
        </Fade>
      </div>
    </AbsoluteFill>
  );
};
export const Genres: React.FC = () => (
  <AbsoluteFill>
    <Backdrop />
    <div style={{ position: "absolute", left: 120, top: 110 }}>
      <Kicker text="ONE MODEL · FIVE GAME STYLES" start={0} />
    </div>
    {GENRES.map((g, i) => (
      <Sequence key={g} from={i * GENRE_LEN} durationInFrames={GENRE_LEN} layout="none">
        <GenreCard g={g} index={i} />
      </Sequence>
    ))}
  </AbsoluteFill>
);

// ---------------------------------------------------------------- 7. imagined futures
const StaticFrame: React.FC<{ svg: string; width: number; genre: string }> = ({ svg, width, genre }) => {
  const parsed = useMemo(() => parseFrame(svg), [svg]);
  return (
    <svg viewBox="0 0 16 12" width={width} height={(width * 3) / 4} shapeRendering="crispEdges" style={{ background: GENRE_BG[genre], display: "block" }}>
      {parsed.items.map((it, k) =>
        it.k === "hero" ? (
          <g key={k} transform={`translate(${it.x} ${it.y})`} style={{ filter: "drop-shadow(0 0 0.07px rgba(255,255,255,.95))" }}>
            <CatRects frame={0} cell />
          </g>
        ) : SURV.sprites[it.k] ? (
          <g key={k} transform={`translate(${it.x} ${it.y}) scale(0.125)`}>
            <SpriteRects rows={SURV.sprites[it.k]} />
          </g>
        ) : null,
      )}
    </svg>
  );
};
const ARROWS: Record<string, string> = { up: "↑ up", down: "↓ down", left: "← left", right: "→ right", stay: "· stay" };
export const Futures: React.FC = () => {
  const frame = useCurrentFrame();
  const f = data.futures;
  const keys = ["up", "down", "left", "right", "stay"];
  const hero = (svg: string) => parseFrame(svg).items.find((it) => it.k === "hero");
  return (
    <AbsoluteFill>
      <Backdrop />
      <div style={{ position: "absolute", left: 120, top: 110 }}>
        <Kicker text="IMAGINE" start={0} />
        <div style={{ height: 18 }} />
        <Words text="Every possible next frame, at once." start={4} size={84} />
      </div>
      <Fade start={14} style={{ position: "absolute", left: 120, top: 400 }}>
        <div style={{ borderRadius: 20, overflow: "hidden", border: `3px solid ${C.accent}` }}>
          <StaticFrame svg={f.from} width={640} genre="survivors" />
        </div>
        <div style={{ fontFamily: pixel, fontSize: 22, color: C.accent, marginTop: 14 }}>NOW</div>
      </Fade>
      {keys.map((k, i) => {
        const s = 34 + i * 7;
        const col = i % 3;
        const row = Math.floor(i / 3);
        const h = hero(f.branches[k]);
        return (
          <div
            key={k}
            style={{
              position: "absolute",
              left: 860 + col * 330 + (row === 1 ? 165 : 0),
              top: 380 + row * 300,
              opacity: interpolate(frame, [s, s + 10], [0, 1], clamp),
              scale: interpolate(frame, [s, s + 20], [0.85, 1], { ...clamp, easing: EASE, output: "perceptual-scale" }),
            }}
          >
            <div style={{ borderRadius: 14, overflow: "hidden", border: `2px solid ${C.line}` }}>
              <StaticFrame svg={f.branches[k]} width={300} genre="survivors" />
            </div>
            <div style={{ fontFamily: mono, fontSize: 24, color: C.ink, marginTop: 10 }}>
              {ARROWS[k]} <span style={{ color: C.muted }}>{h ? `hero (${h.x}, ${h.y})` : ""}</span>
            </div>
          </div>
        );
      })}
      <Fade start={80} style={{ position: "absolute", left: 120, top: 960 }}>
        <div style={{ fontFamily: display, fontSize: 34, color: C.muted }}>
          Five futures generated in parallel across <span style={{ color: C.ink }}>2× H100</span> in{" "}
          <span style={{ color: C.accent }}>{(f.ms / 1000).toFixed(1)} s</span>, so your key press never waits.
        </div>
      </Fade>
    </AbsoluteFill>
  );
};

// ---------------------------------------------------------------- 8. results
const BARS = [
  { g: "snake", v: 93 },
  { g: "shooter", v: 73 },
  { g: "platformer", v: 70 },
  { g: "dodge", v: 43 },
  { g: "survivors", v: 40 },
];
const STATS = [
  { big: "100%", small: "tick consistency over 60 self-fed frames, in every genre" },
  { big: "97–100%", small: "HUD and hero position correct, per genre" },
  { big: "217 ms", small: "per frame (snake), with n-gram speculative decoding" },
  { big: "~60", small: "tokens per 8×8 sprite" },
];
export const Results: React.FC = () => {
  const frame = useCurrentFrame();
  return (
    <AbsoluteFill>
      <Backdrop />
      <div style={{ position: "absolute", left: 120, top: 110 }}>
        <Kicker text="MEASURED ON HELD-OUT DATA" start={0} />
        <div style={{ height: 18 }} />
        <Words text="It learned the rules." start={4} size={100} />
      </div>
      <div style={{ position: "absolute", left: 120, top: 400, width: 860 }}>
        <div style={{ fontFamily: pixel, fontSize: 22, color: C.muted, marginBottom: 24 }}>EXACT NEXT FRAME</div>
        {BARS.map((b, i) => {
          const s = 22 + i * 6;
          const v = interpolate(frame, [s, s + 34], [0, b.v], { ...clamp, easing: EASE });
          return (
            <div key={b.g} style={{ display: "flex", alignItems: "center", gap: 22, marginBottom: 26 }}>
              <div style={{ width: 210, fontFamily: display, fontSize: 32, color: C.ink, textAlign: "right" }}>{b.g}</div>
              <div style={{ flex: 1, height: 46, background: C.panel, borderRadius: 10, overflow: "hidden", border: `2px solid ${C.line}` }}>
                <div style={{ width: `${v}%`, height: "100%", background: `linear-gradient(90deg, ${C.accent}, ${C.gold})` }} />
              </div>
              <div style={{ width: 110, fontFamily: mono, fontSize: 32, color: C.ink }}>{Math.round(v)}%</div>
            </div>
          );
        })}
        <Fade start={70}>
          <div style={{ fontFamily: display, fontSize: 24, color: C.muted, marginTop: 6 }}>
            Most misses are random enemy spawns, not broken rules.
          </div>
        </Fade>
      </div>
      <div style={{ position: "absolute", left: 1080, top: 340, width: 720, display: "grid", gap: 16 }}>
        {STATS.map((s, i) => (
          <Fade key={i} start={40 + i * 10}>
            <div style={{ background: C.panel, border: `2px solid ${C.line}`, borderRadius: 18, padding: "16px 28px" }}>
              <div style={{ fontFamily: display, fontWeight: 700, fontSize: 50, color: C.accent }}>{s.big}</div>
              <div style={{ fontFamily: display, fontSize: 26, color: C.muted }}>{s.small}</div>
            </div>
          </Fade>
        ))}
      </div>
    </AbsoluteFill>
  );
};

// ---------------------------------------------------------------- 9. story
export const Story: React.FC = () => {
  const frame = useCurrentFrame();
  const r = run("platformer");
  const text = r.story;
  const chars = Math.floor(interpolate(frame, [16, 86], [0, text.length], clamp));
  return (
    <AbsoluteFill>
      <AbsoluteFill style={{ justifyContent: "center", alignItems: "center", opacity: 0.32 }}>
        <GameView run={r} t={frame} framesPerStep={9} width={1920} startStep={2} hud={false} radius={0} />
      </AbsoluteFill>
      <AbsoluteFill style={{ background: "linear-gradient(180deg, rgba(13,12,20,.55), rgba(13,12,20,.92))" }} />
      <AbsoluteFill style={{ justifyContent: "center", padding: "0 180px" }}>
        <Kicker text="AND THE STORY KEEPS GOING" start={0} />
        <div style={{ height: 30 }} />
        <div style={{ fontFamily: display, fontWeight: 500, fontSize: 64, lineHeight: 1.25, color: C.ink, maxWidth: 1500 }}>
          {text.slice(0, chars)}
          <span style={{ color: C.accent, opacity: frame % 16 < 9 ? 1 : 0 }}>▍</span>
        </div>
        <Fade start={90}>
          <div style={{ fontFamily: mono, fontSize: 28, color: C.muted, marginTop: 34 }}>
            the narrator, live, in “{r.title.replace("’", "'")}”
          </div>
        </Fade>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};

// ---------------------------------------------------------------- 10. outro
export const Outro: React.FC = () => {
  const frame = useCurrentFrame();
  return (
    <AbsoluteFill>
      <Backdrop />
      <AbsoluteFill style={{ justifyContent: "center", alignItems: "center", gap: 30 }}>
        <div style={{ translate: `0px ${-Math.abs(Math.sin(frame / 7)) * 18}px` }}>
          <MistralCat size={220} frame={catFrameAt(frame)} glow />
        </div>
        <Words text="Le Chat Atelier" start={6} size={140} align="center" />
        <Fade start={22}>
          <div style={{ fontFamily: display, fontSize: 40, color: C.muted, textAlign: "center" }}>
            Type a world. The model plays it, frame by frame.
          </div>
        </Fade>
        <Fade start={36}>
          <div style={{ fontFamily: mono, fontSize: 30, color: C.ink, textAlign: "center", lineHeight: 1.7 }}>
            <span style={{ color: C.accent }}>huggingface.co/</span>B-Divyesh/atelier-svg-world-model
            <br />
            <span style={{ color: C.accent }}>huggingface.co/</span>B-Divyesh/atelier-pixel-sprites-8x8
          </div>
        </Fade>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};

// keep the tween helper referenced for type-checking builds that tree-shake unused exports
export const _matchFrames = matchFrames;
