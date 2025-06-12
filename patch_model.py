import torch
from pathlib import Path

RAW = Path(
    "xttsv2_esd_train/run/training/XTTS_v2.0_original_model_files/model.pth"
)  # ← your current checkpoint
NEW = Path(
    "xttsv2_esd_train/run/training/XTTS_v2.0_original_model_files/new_model.pth"
)  # ← output

# How many tokens should the *new* embed hold?
NEW_VOCAB = 6_684  # len(tokenizer)

ckpt = torch.load(RAW, map_location="cpu")


# --- helpers ---------------------------------------------------------------
def pad_matrix(name, extra_rows):
    mat = ckpt["model"][name]
    emb_dim = mat.shape[1]
    add = torch.randn(extra_rows, emb_dim) * 0.02
    ckpt["model"][name] = torch.cat([mat, add], dim=0)


def pad_bias(name, extra_rows):
    bias = ckpt["model"][name]
    add = torch.zeros(extra_rows)
    ckpt["model"][name] = torch.cat([bias, add], dim=0)


# --- enlarge the three vocab-dependent tensors ----------------------------
old_vocab = ckpt["model"]["gpt.text_embedding.weight"].shape[0]
if NEW_VOCAB <= old_vocab:
    raise ValueError(f"Checkpoint already has {old_vocab} tokens ≥ {NEW_VOCAB}")

extra = NEW_VOCAB - old_vocab
print(f"Patching {extra} new tokens …")

pad_matrix("gpt.text_embedding.weight", extra)
pad_matrix("gpt.text_head.weight", extra)
pad_bias("gpt.text_head.bias", extra)

torch.save(ckpt, NEW)
print("Saved", NEW)
