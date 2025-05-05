import pickle
import numpy as np
from sentence_transformers import SentenceTransformer, util
import torch
import traceback
import os

model_path = "/Users/wynndiaz/VCBot/final_model"
vector_pkl = "/Users/wynndiaz/VCBot/vectors.pkl"
_MODEL = None
def load_search_model(model_path):
    """Loads the SentenceTransformer model (lazily)."""
    global _MODEL
    if _MODEL is None:
        print(f"INFO: Loading search model from {model_path}...")
        if not os.path.isdir(model_path):
            print(f"CRITICAL ERROR: Model directory not found at {model_path}")
            raise FileNotFoundError(f"Model directory not found: {model_path}")
        try:
            _MODEL = SentenceTransformer(model_path)
            # Optional: Move model to GPU if available and desired
            # device = 'cuda' if torch.cuda.is_available() else 'cpu'
            # _MODEL.to(device)
            print(f"INFO: Model loaded successfully. Device: {_MODEL.device}")
        except Exception as e:
            print(f"CRITICAL ERROR: Could not load model from {model_path}: {e}")
            print(traceback.format_exc())
            # Re-raise to prevent proceeding without a model
            raise RuntimeError(f"Failed to load embedding model from {model_path}") from e
    return _MODEL

def search_vectors_simple(query: str, model: SentenceTransformer, vector_pickle_path: str, k: int = 5):
    """
    Searches vectors loaded from a pickle file using cosine similarity.

    Args:
        query: The search query string.
        model: The loaded SentenceTransformer model instance.
        vector_pickle_path: Path to the .pkl file created previously.
                               (expects a list of dicts with 'embedding', 'metadata', 'text')
        k: Number of top results to return.

    Returns:
        A list of top k results, each a dict: {'score': float, 'metadata': dict, 'text': str}
        Returns empty list if data loading fails or no vectors found.
        Returns fewer than k results if fewer vectors exist.
    """
    print(f"searching for: '{query}' (top {k})")

    # 1. Load data
    try:
        with open(vector_pickle_path, 'rb') as f:
            all_data = pickle.load(f)
        if not all_data:
            print("bruh the pickle file is empty")
            return []
        # Separate embeddings and the rest for easier handling
        corpus_embeddings = np.array([item['embedding'] for item in all_data]).astype(np.float32) # Ensure float32
        corpus_metadata = [item['metadata'] for item in all_data]
        corpus_texts = [item['text'] for item in all_data]
        print(f"loaded {len(corpus_embeddings)} vectors from {vector_pickle_path}")
    except FileNotFoundError:
        print(f"be real, vector file not found: {vector_pickle_path}")
        return []
    except Exception as e:
        print(f"oof, failed to load or parse pickle file {vector_pickle_path}: {e}")
        return []

    # Adjust k if smaller than corpus size
    actual_k = min(k, len(corpus_embeddings))
    if actual_k == 0:
         print("no embeddings loaded to search lmao")
         return []
    if actual_k < k:
         print(f"requested {k} results but only {actual_k} vectors exist.")


    # 2. Embed query
    print("embedding query...")
    query_embedding = model.encode(query, convert_to_tensor=True)
    corpus_embeddings = torch.tensor(corpus_embeddings, dtype=torch.float32)  # convert to tensor

    # Move to same device as query_embedding
    device = query_embedding.device
    corpus_embeddings = corpus_embeddings.to(device)

    # 3. Compute Cosine Similarity
    # util.cos_sim returns a tensor of shape [num_queries, num_corpus_vectors]
    # We have 1 query, so shape is [1, N]
    print("calculating similarities...")
    cos_scores = util.cos_sim(query_embedding, corpus_embeddings)[0] # Get the scores for the first query

    # 4. Get top k results
    # Use torch.topk to get indices and scores of the highest similarities
    top_results = np.argpartition(-cos_scores.cpu().numpy(), range(actual_k))[0:actual_k] # Faster than full sort for top k indices
    # Need to sort the top_k indices by score
    top_indices_unsorted = top_results
    top_scores_unsorted = cos_scores[top_indices_unsorted]
    # Sort these top k results by score
    sorted_indices_in_top_k = np.argsort(-top_scores_unsorted.cpu().numpy())
    top_indices = top_indices_unsorted[sorted_indices_in_top_k]


    # 5. Format results
    results = []
    print("top results:")
    for idx in top_indices:
        score = cos_scores[idx].item() # .item() converts tensor scalar to python float
        metadata = corpus_metadata[idx]
        text = corpus_texts[idx]
        results.append({
            "score": score,
            "metadata": metadata,
            "text": text
        })
        print(f"  Score: {score:.4f} | Source: {metadata.get('source', 'N/A')} | Page: {metadata.get('page_label', 'N/A')} | Chunk: {metadata.get('chunk_index_doc', 'N/A')}")
        print(f"    Text: {text[:150]}...") # Print snippet

    return results

