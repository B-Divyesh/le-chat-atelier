"""Push a trained model to a private Hugging Face repo: safetensors folder + Q8_0 GGUF + model card."""
import os, sys
from huggingface_hub import HfApi
api = HfApi()
repo, local_dir, gguf, card = sys.argv[1:5]
user = api.whoami()["name"]
rid = repo if "/" in repo else f"{user}/{repo}"
api.create_repo(rid, private=True, exist_ok=True)
api.upload_folder(folder_path=local_dir, repo_id=rid, allow_patterns=["*.json", "*.safetensors", "*.jinja", "*.txt"])
api.upload_file(path_or_fileobj=gguf, path_in_repo=os.path.basename(gguf), repo_id=rid)
api.upload_file(path_or_fileobj=card, path_in_repo="README.md", repo_id=rid)
print("pushed https://huggingface.co/" + rid)
