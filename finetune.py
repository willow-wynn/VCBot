"""
author: chatgpt‑o3  ‑ v6 (mps compat)

fixes for Apple MPS:
• fallback to plain MultipleNegativesRankingLoss when on mps (Cached MNRL’s rand checkpoint uses torch.mps.device → break)
• keep 64 per‑device bs for in‑batch negs

schema: {queries, corpus, relevant_docs}
"""

import json, os, gc, torch
from pathlib import Path
from typing import List, Dict

from torch.utils.data import DataLoader
from sentence_transformers import SentenceTransformer, losses, InputExample
from sentence_transformers.evaluation import InformationRetrievalEvaluator

# -----------------------------------------------------------------------------
# env & device
# -----------------------------------------------------------------------------
os.environ.setdefault("TOKENIZERS_PARALLELISM", "true")
os.environ.setdefault("PYTORCH_MPS_HIGH_WATERMARK_RATIO", "0.0")
os.environ.setdefault("PYTORCH_MPS_LOW_WATERMARK_RATIO", "0.1")

device = (
    "cuda" if torch.cuda.is_available() else
    "mps" if torch.backends.mps.is_available() else
    "cpu"
)
print(f"training on {device}")

# -----------------------------------------------------------------------------
# data utils
# -----------------------------------------------------------------------------

def load_json(path: Path):
    with open(path) as f:
        return json.load(f)


def make_examples(data: dict) -> List[InputExample]:
    q, c, rel = data["queries"], data["corpus"], data["relevant_docs"]
    ex: List[InputExample] = []
    for qid, qtxt in q.items():
        for did in rel.get(qid, []):
            dtxt = c.get(did)
            if dtxt is not None:
                ex.append(InputExample(texts=[qtxt, dtxt], label=1.0))
    return ex


def make_ir_eval(data: dict):
    queries, corpus, rel = data["queries"], data["corpus"], data["relevant_docs"]
    qrels: Dict[str, Dict[str, int]] = {qid: {did: 1 for did in dids if did in corpus} for qid, dids in rel.items()}
    return InformationRetrievalEvaluator(queries, corpus, qrels, name="val-ir", show_progress_bar=False)

# -----------------------------------------------------------------------------
# load sets
# -----------------------------------------------------------------------------
train_data = load_json(Path("/Users/wynndiaz/VCBot/final_train_dataset.json"))
val_data   = load_json(Path("/Users/wynndiaz/VCBot/final_val_dataset.json"))

train_examples = make_examples(train_data)
print(f"train ex: {len(train_examples):,}")

# -----------------------------------------------------------------------------
# model & loss
# -----------------------------------------------------------------------------
model_name = "BAAI/bge-small-en-v1.5"
model = SentenceTransformer(model_name, trust_remote_code=True, device=device)

# on mps, CachedMNRL triggers torch.mps.device error; fallback to plain MNRL
if device == "cuda":
    try:
        train_loss = losses.CachedMultipleNegativesRankingLoss(model, mini_batch_size=64)
    except TypeError:
        train_loss = losses.MultipleNegativesRankingLoss(model)
        print("⚠️ could not init CachedMultipleNegativesRankingLoss—using MNRL")
else:
    train_loss = losses.MultipleNegativesRankingLoss(model)
    print("ℹ️ running on non‑cuda device; using MNRL only")

# -----------------------------------------------------------------------------
# training config
# -----------------------------------------------------------------------------
PER_DEVICE_BATCH = 64
NUM_EPOCHS       = 3
LR               = 2e-5
WEIGHT_DECAY     = 0.01

train_loader = DataLoader(train_examples, shuffle=True, batch_size=PER_DEVICE_BATCH)
val_evaluator = make_ir_eval(val_data)

steps_per_epoch = len(train_loader)
warmup_steps     = int(steps_per_epoch * NUM_EPOCHS * 0.1)

# -----------------------------------------------------------------------------
# fit
# -----------------------------------------------------------------------------
print(model.evaluate(evaluator=val_evaluator))
model.fit(
    train_objectives=[(train_loader, train_loss)],
    evaluator=val_evaluator,
    epochs=NUM_EPOCHS,
    evaluation_steps=40,
    warmup_steps=warmup_steps,
    optimizer_params={"lr": LR, "weight_decay": WEIGHT_DECAY, "eps": 1e-6, "betas": (0.9, 0.98)},
    scheduler="WarmupLinear",
    max_grad_norm=1.0,
    checkpoint_path="/Users/wynndiaz/VCBot/checkpoints",
    checkpoint_save_steps=steps_per_epoch,
    use_amp=(device == "cuda"),
    show_progress_bar=True,
    output_path="/Users/wynndiaz/VCBot/final_model",
)

# -----------------------------------------------------------------------------
# sanity check
# -----------------------------------------------------------------------------
qs_sample = list(val_data["queries"].values())[:3]
print("emb shape:", model.encode(qs_sample).shape)

gc.collect()
if torch.cuda.is_available(): torch.cuda.empty_cache()
