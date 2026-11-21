"use strict";
const byId = id => document.getElementById(id);
const svgNS = "http://www.w3.org/2000/svg";
const elements = new Set("svg g path rect circle ellipse line polyline polygon defs linearGradient radialGradient stop clipPath title desc text tspan".split(" "));
const attributes = new Set("xmlns viewBox width height fill stroke d points x y x1 y1 x2 y2 cx cy r rx ry fx fy id offset stop-color stop-opacity fill-rule fill-opacity stroke-width stroke-linejoin stroke-linecap stroke-dasharray stroke-opacity opacity transform gradientUnits gradientTransform clip-path text-anchor font-family font-size font-weight dx dy".split(" "));
let active = null;
let drawing = null;
let recent = [];
try { recent = JSON.parse(localStorage.getItem("atelier.drawings") || "[]"); } catch {}
if (!Array.isArray(recent)) recent = [];

function safeSVG(text) {
  const start = text.indexOf("<svg");
  if (start === -1) return null;
  const end = text.indexOf("</svg>", start);
  const fragment = end >= 0 ? text.slice(start, end + 6) : text.slice(start, text.lastIndexOf(">") + 1) + "</svg>";
  const root = new DOMParser().parseFromString(fragment, "image/svg+xml").documentElement;
  if (root.localName !== "svg" || root.namespaceURI !== svgNS || !root.children.length) return null;
  for (const el of [root, ...root.querySelectorAll("*")]) {
    if (!elements.has(el.localName) || el.namespaceURI !== svgNS) return null;
    for (const attr of Array.from(el.attributes)) {
      if (!attributes.has(attr.name) || (/url\s*\(/i.test(attr.value) && !/^url\(#[\w.-]+\)$/.test(attr.value))) {
        el.removeAttributeNode(attr);
      }
    }
  }
  return {uri: "data:image/svg+xml;charset=utf-8," + encodeURIComponent(new XMLSerializer().serializeToString(root)), complete: end >= 0};
}

function render() {
  byId("code").textContent = drawing.svg;
  const svg = safeSVG(drawing.svg);
  if (svg) {
    byId("image").src = svg.uri;
    byId("empty").hidden = true;
    if (svg.complete) {
      byId("download").href = svg.uri;
      byId("download").hidden = false;
    }
  }
  return svg?.complete || false;
}

function show(item) {
  drawing = {...item};
  byId("image").removeAttribute("src");
  byId("empty").hidden = false;
  byId("empty").textContent = active ? "Waiting for the first shape…" : "Your illustration will appear here.";
  byId("download").hidden = true;
  byId("download").removeAttribute("href");
  byId("caption").textContent = drawing.prompt;
  byId("board-label").textContent = drawing.model === "base" ? "Base model" : "Fine-tuned · step 625";
  byId("status").textContent = drawing.note || "";
  render();
}

function updateHistory() {
  const list = byId("history");
  list.replaceChildren();
  for (const item of recent) {
    const button = document.createElement("button");
    button.textContent = item.prompt;
    button.disabled = Boolean(active);
    button.onclick = () => { show(item); byId("prompt").value = item.prompt; };
    list.append(button);
  }
}

function setBusy(value) {
  byId("send").replaceChildren(value ? "Stop generation " : "Generate SVG ");
  const symbol = document.createElement("span");
  symbol.setAttribute("aria-hidden", "true");
  symbol.textContent = value ? "■" : "↗";
  byId("send").append(symbol);
  byId("signal").hidden = !value;
  byId("model").disabled = value;
  byId("prompt").readOnly = value;
  for (const b of document.querySelectorAll(".suggestions button")) b.disabled = value;
  updateHistory();
}

function switchTab(source) {
  byId("stage").hidden = source;
  byId("code").hidden = !source;
  byId("view").setAttribute("aria-pressed", String(!source));
  byId("source").setAttribute("aria-pressed", String(source));
}
byId("view").onclick = () => switchTab(false);
byId("source").onclick = () => switchTab(true);
for (const button of document.querySelectorAll(".suggestions button")) {
  button.onclick = () => { byId("prompt").value = button.textContent; byId("prompt").focus(); };
}
byId("prompt").onkeydown = event => {
  if ((event.metaKey || event.ctrlKey) && event.key === "Enter" && !active) byId("composer").requestSubmit();
};

async function health() {
  let ready = false;
  try { ready = (await (await fetch("/health")).json()).ready; } catch {}
  byId("lamp").classList.toggle("up", ready);
  byId("connection").textContent = ready ? "GPU connected" : "GPU disconnected";
}

byId("composer").onsubmit = async event => {
  event.preventDefault();
  if (active) { active.abort(); return; }
  const prompt = byId("prompt").value.trim();
  if (!prompt) { byId("prompt").focus(); return; }
  const controller = new AbortController();
  active = controller;
  setBusy(true);
  show({prompt, svg: "", model: byId("model").value, note: "Connecting to the model…"});
  const started = performance.now();
  let lastRender = 0, received = false, finished = false;
  const timer = setInterval(() => {
    const elapsed = Math.floor((performance.now() - started) / 1000);
    byId("status").textContent = (received ? "Drawing" : "Waiting for the model") + " · " + elapsed + " s";
  }, 1000);
  try {
    const response = await fetch("/generate", {method: "POST", headers: {"Content-Type": "application/json"},
      body: JSON.stringify({prompt, model: drawing.model}), signal: controller.signal});
    if (!response.ok) throw Error("The GPU could not accept the request. Check the connection and try again.");
    const reader = response.body.pipeThrough(new TextDecoderStream()).getReader();
    let buffer = "";
    for (;;) {
      const part = await reader.read();
      if (part.done) break;
      buffer += part.value;
      let split;
      while ((split = buffer.indexOf("\n")) >= 0) {
        const message = JSON.parse(buffer.slice(0, split));
        buffer = buffer.slice(split + 1);
        if (message.error) throw Error(message.error);
        if (message.text) {
          drawing.svg += message.text;
          received = true;
          if (performance.now() - lastRender >= 160) { render(); lastRender = performance.now(); }
        }
        if (message.done) {
          finished = true;
          const complete = render();
          drawing.note = (complete ? "Finished" : "Incomplete SVG") + " · " + message.tokens.toLocaleString() + " tokens · " + message.seconds + " s";
          byId("status").textContent = drawing.note;
          if (complete) {
            recent = [{...drawing}, ...recent].slice(0, 8);
            try { localStorage.setItem("atelier.drawings", JSON.stringify(recent)); } catch {}
          }
        }
      }
    }
    if (!finished) throw Error("The stream ended early. You can try the prompt again.");
  } catch (error) {
    render();
    byId("status").textContent = controller.signal.aborted ? "Generation stopped" : error.message;
  } finally {
    clearInterval(timer);
    active = null;
    setBusy(false);
    health();
  }
};

async function start() {
  updateHistory(); health();
  setInterval(health, 30000);
  if (recent.length) { show(recent[0]); return; }
  try {
    const sample = await (await fetch("/sample")).json();
    if (sample && !drawing) show({...sample, note: "Sample from the " + (sample.model === "base" ? "base" : "fine-tuned") + " model"});
  } catch {}
}
start();
