from tokenizers import Tokenizer
from huggingface_hub import hf_hub_download

MODEL = "mistralai/Ministral-3-3B-Instruct-2512-BF16"
SYSTEM = "Draw the requested illustration. Return only a complete SVG on a 200 by 200 viewBox."
PREFIX = "Generate an SVG illustration: "


def get_tokenizer():
    return Tokenizer.from_file(hf_hub_download(MODEL, "tokenizer.json"))


def prompt_tokens(tokenizer, caption):
    prompt = f"<s>[SYSTEM_PROMPT]{SYSTEM}[/SYSTEM_PROMPT][INST]{PREFIX}{caption}[/INST]"
    return tokenizer.encode(prompt, add_special_tokens=False).ids


def load_base():
    import torch
    from transformers import Mistral3ForConditionalGeneration
    return Mistral3ForConditionalGeneration.from_pretrained(
        MODEL, dtype=torch.bfloat16, attn_implementation="sdpa", device_map={"": 0}
    )
