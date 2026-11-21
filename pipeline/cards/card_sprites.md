---
license: apache-2.0
base_model: mistralai/Ministral-3-3B-Instruct-2512-BF16
datasets:
- Angais/pixel-art-atlas-1.4m
tags: [pixel-art, sprites, game-assets, pico-8, llama.cpp]
---
# Atelier pixel sprites 8×8

Ministral 3 3B fully fine-tuned to draw **8×8 game sprites** in the 16-colour PICO-8 palette from a short caption
("green slime", "red health potion"). Output is 8 lines of 8 characters: `.` = transparent, `0`–`f` = palette index.
About 60 tokens per sprite, ~0.2–0.7 s on an H100 with llama.cpp.

- **Data:** ~135k captioned 16×16 sprites from Angais/pixel-art-atlas-1.4m (CC0), downscaled to 8×8 and mapped to the
  palette with CIELAB nearest colour.
- **Training:** 3 rounds of full fine-tuning (~45k sprites each); held-out loss 0.76 on the final palette mapping.
- **Prompt:** `<s>[SYSTEM_PROMPT]Draw the requested game sprite as 8x8 pixel art in the PICO-8 palette. Reply with 8 lines of 8 characters: . is transparent, 0-f are palette colors.[/SYSTEM_PROMPT][INST]{caption}[/INST]`
- **Recommended:** temperature 0.75, and a GBNF grammar forcing 8 rows of `[.0-9a-f]{8}`.
- `pixlab-q8_0.gguf` is the quantized file served with llama.cpp in the hackathon demo.
