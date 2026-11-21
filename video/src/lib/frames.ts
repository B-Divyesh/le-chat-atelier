import raw from "../data.json";

export type Frame = { action: string; svg: string; ms: number; source?: string };
export type Run = {
  genre: string;
  prompt: string;
  title: string;
  intro: string;
  design_ms: number;
  director_genre: string;
  names: Record<string, string>;
  sprites: Record<string, string[]>;
  sprite_ms: Record<string, number>;
  frames: Frame[];
  story: string;
};
export type Data = { runs: Run[]; futures: { from: string; ms: number; branches: Record<string, string> } };

export const data = raw as unknown as Data;
export const run = (genre: string): Run => data.runs.find((r) => r.genre === genre) ?? data.runs[0];

export type Item = { k: string; x: number; y: number };
export type Parsed = { hud: string; items: Item[] };

// the model's own SVG frame -> the elements it wrote
export const parseFrame = (svg: string): Parsed => {
  const hud = (/<text[^>]*>([^<]*)<\/text>/.exec(svg) || [])[1] ?? "";
  const items: Item[] = [];
  const re = /<use href="#(\w+)" x="(\d+)" y="(\d+)"\/>/g;
  let m: RegExpExecArray | null;
  while ((m = re.exec(svg))) items.push({ k: m[1], x: Number(m[2]), y: Number(m[3]) });
  return { hud, items };
};

export type Tween = { k: string; x0: number; y0: number; x1: number; y1: number; a0: number; a1: number };

// pair each element of the next frame with the nearest same-kind element of the previous one (as the game does)
export const matchFrames = (a: Item[], b: Item[]): Tween[] => {
  const used = a.map(() => false);
  const out: Tween[] = [];
  for (const w of b) {
    let best = -1;
    let bd = 3.5;
    a.forEach((o, i) => {
      if (!used[i] && o.k === w.k) {
        const d = Math.abs(o.x - w.x) + Math.abs(o.y - w.y);
        if (d < bd) {
          bd = d;
          best = i;
        }
      }
    });
    if (best >= 0) {
      used[best] = true;
      out.push({ k: w.k, x0: a[best].x, y0: a[best].y, x1: w.x, y1: w.y, a0: 1, a1: 1 });
    } else {
      out.push({ k: w.k, x0: w.x, y0: w.y, x1: w.x, y1: w.y, a0: 0, a1: 1 });
    }
  }
  a.forEach((o, i) => {
    if (!used[i]) out.push({ k: o.k, x0: o.x, y0: o.y, x1: o.x, y1: o.y, a0: 1, a1: 0 });
  });
  return out;
};
