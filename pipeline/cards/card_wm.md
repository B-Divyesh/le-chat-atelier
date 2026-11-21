---
license: apache-2.0
base_model: mistralai/Ministral-3-3B-Instruct-2512-BF16
tags: [world-model, svg, game, simulation, multi-genre, llama.cpp, le-chat]
---
# Atelier SVG world model

![Le Chat in a model-generated cheese dungeon](images/screenshot.png)

A Ministral 3 3B fine-tuned to be **a game engine whose state is an SVG frame**. Given the genre, the player's key and the
current frame, it writes the **entire next frame**: positions, collisions, damage, pickups, spawns and the HUD text. From an empty
frame and the action `start`, it generates a new environment. Each frame is fed back in as the next input.

Type a prompt and three models build and run the world:

```
prompt ──► DIRECTOR (base model, JSON-schema output) → genre, enemies, obstacles, items, projectile, story
             ├─► SPRITE MODEL (B-Divyesh/atelier-pixel-sprites-8x8) → 8×8 PICO-8 sprites, streamed into the SVG <defs>
             └─► WORLD MODEL (this repo):  "<genre>: <key>\n<current SVG>"  →  next SVG frame   (loop)
```
The hero is Le Chat (Mistral's pixel cat), and the narrator keeps dreaming up the next part of the story.

## Genres learned by one model
| genre | what the model simulates |
|---|---|
| survivors | top-down; 3 enemy kinds chase you by different rules; obstacles block; auto-attack turns enemies into gems; damage; spawns |
| snake | the head moves along the head−neck direction, the body follows, eating grows it, reversing is ignored, a crash resets the game |
| shooter | ship at the bottom auto-fires, bullets rise, enemies descend every 3rd tick, hits score, landings cost HP |
| dodge | vertical scroller; obstacles and coins fall; collisions cost HP; coins score |
| platformer | side view with gravity and jumps (vertical velocity in the HUD), platforms, walking enemies that turn at edges, coins |

## Results (round 2, held-out transitions, greedy)
| genre | exact frame | HUD | hero | ms/frame (H100, n-gram speculation) |
|---|---|---|---|---|
| snake | 93% | 100% | 100% | 217 |
| shooter | 73% | 100% | 100% | 417 |
| platformer | 70% | 100% | 100% | 393 |
| dodge | 43% | 97% | 100% | 585 |
| survivors | 40% | 97% | 97% | 370 |

Random spawns account for most of the exact-frame misses. Over 60 self-fed steps per genre, the tick count stayed consistent and the
hero stayed present 100% of the time. Validation loss is 0.0073.

## What is and isn't the model
- **The model writes every frame in full.** The browser sends the model's own previous output plus the key, and no engine computes state between frames.
- A **GBNF grammar** restricts sampling to well-formed frames for the genre: allowed sprite kinds, HUD format, and coordinates on the 16×12 grid. It never chooses values.
- **First frame:** the model generates it from an empty SVG. If it fails the genre's sanity checks 3 times, the rule simulator generates the first frame instead.
- **Edge crossing:** the model generates the new area, and code carries over HP/XP/tick and places Le Chat at the opposite edge.
- **Smoothing** is browser animation between consecutive model frames (it can be toggled off). It is visual only.
- The rule simulator (`pipeline/wm_multi.py`) generated the training data (~90k transitions over two rounds) and is used for evaluation.

## Files
- `wmm2-q8_0.gguf` is round 2 (recommended), served with llama.cpp. `wmm-q8_0.gguf` is round 1. `model.safetensors` holds the round-2 weights.
- `app/` contains the exact demo that was running: `fast_server.py`, `world.html` and `RUN.md`.
- `pipeline/` contains the simulators, training, evaluation and the Playwright play test.

**Prompt format:** `<s>[INST]{genre}: {action}\n{current_svg}[/INST]`, with action ∈ up, down, left, right, stay, start.
