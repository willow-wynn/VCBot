import os
import pickle
from sentence_transformers import SentenceTransformer
from transformers import AutoTokenizer

def embed_txt_file(
    txt_path: str,
    model_path: str,
    chunk_size_tokens: int = 1024,
    overlap_tokens: int = 50,
    save_to: str = None
):
    if not os.path.isfile(txt_path):
        raise FileNotFoundError(f"no txt file found: {txt_path}")
    if not os.path.isdir(model_path):
        raise FileNotFoundError(f"model path invalid: {model_path}")

    print(f"loading tokenizer/model from {model_path}")
    tokenizer = AutoTokenizer.from_pretrained(model_path)
    model = SentenceTransformer(model_path)

    with open(txt_path, "r", encoding="utf-8") as f:
        raw_text = f.read()

    token_ids = tokenizer.encode(raw_text, add_special_tokens=False)
    print(f"tokenized into {len(token_ids)} tokens")

    chunks = []
    i = 0
    while i < len(token_ids):
        chunk_tokens = token_ids[i:i + chunk_size_tokens]
        chunk_text = tokenizer.decode(chunk_tokens, skip_special_tokens=True)

        if chunk_text.strip():
            chunks.append({
                "text": chunk_text,
                "metadata": {
                    "chunk_index": len(chunks),
                    "start_token_index": i,
                    "end_token_index": min(i + chunk_size_tokens, len(token_ids)),
                    "source": os.path.basename(txt_path)
                }
            })

        if i + chunk_size_tokens >= len(token_ids):
            break
        i += chunk_size_tokens - overlap_tokens

    if not chunks:
        raise ValueError("no valid text chunks generated")

    print(f"encoding {len(chunks)} chunks")
    embeddings = model.encode([c["text"] for c in chunks], show_progress_bar=True)

    final_data = [
        {
            "embedding": embeddings[i],
            "metadata": chunks[i]["metadata"],
            "text": chunks[i]["text"]
        }
        for i in range(len(chunks))
    ]

    if save_to:
        if os.path.exists(save_to):
            print(f"existing pickle found at {save_to}, appending...")
            try:
                with open(save_to, "rb") as f:
                    existing_data = pickle.load(f)
                final_data = existing_data + final_data
            except Exception as e:
                print(f"failed to load existing pickle, overwriting instead: {e}")
        else:
            print(f"no existing pickle, creating new one at {save_to}")

        try:
            with open(save_to, "wb") as f:
                pickle.dump(final_data, f)
            print("done.")
        except Exception as e:
            print(f"epic fail saving pickle file: {e}")

    return final_data