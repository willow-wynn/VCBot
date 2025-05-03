import os
import glob
import pickle
import fitz  # PyMuPDF
from sentence_transformers import SentenceTransformer
from transformers import AutoTokenizer # Using AutoTokenizer to count tokens accurately for chunking

# --- Configuration ---
pdf_folder = "/Users/wynndiaz/VCBot/every-vc-bill/pdfs"
model_path = "/Users/wynndiaz/VCBot/final_model"
output_path = "/Users/wynndiaz/VCBot/vectors.pkl"
chunk_size_tokens = 512
overlap_tokens = 50
# --- End Configuration ---

# Input validation lol
if not os.path.isdir(pdf_folder):
    raise FileNotFoundError(f"be real, pdf folder not found: {pdf_folder}")
if not os.path.isdir(model_path):
   
    raise FileNotFoundError(f"bruh where's the model? path not found: {model_path}")
output_dir = os.path.dirname(output_path)
if not os.path.exists(output_dir):
    os.makedirs(output_dir)
    print(f"made dir {output_dir} bc it wasn't there")


print(f"loading tokenizer and model from {model_path}... might take a sec")
# Load the tokenizer associated with the model for accurate chunking
# Using AutoTokenizer assumes it's a hugging face compatible model structure
try:
    tokenizer = AutoTokenizer.from_pretrained(model_path)
except Exception as e:
    print(f"ngl, failed to load tokenizer from {model_path} using AutoTokenizer: {e}")
    print("this might MESS UP token counting for chunks. proceed with caution or fix the path/model format.")
    # As a fallback, SentenceTransformer *might* load its own tokenizer implicitly,
    # but explicit is better for chunking. We'll still try to load the main model.

# Load the sentence transformer model
try:
    model = SentenceTransformer(model_path)
    # Check if the model's max sequence length is sufficient
    # This info might not always be easily accessible depending on the model config
    if hasattr(model, 'max_seq_length'):
        if model.max_seq_length < chunk_size_tokens:
            print(f"WARNING: model max sequence length ({model.max_seq_length}) is less than chunk size ({chunk_size_tokens}). chunks will be truncated by the model.")
    elif hasattr(model, 'get_max_seq_length'): # newer sentence-transformers versions
         if model.get_max_seq_length() < chunk_size_tokens:
              print(f"WARNING: model max sequence length ({model.get_max_seq_length()}) is less than chunk size ({chunk_size_tokens}). chunks will be truncated by the model.")
    else:
        print(f"couldn't automatically verify model max sequence length. assuming it can handle {chunk_size_tokens} tokens.")

except Exception as e:
    print(f"CRITICAL FAIL: couldn't load the embedding model from {model_path}: {e}")
    print("lol no, quitting bc no model")
    exit()

print("model loaded. starting pdf processing...")

all_chunks_data = []
pdf_files = glob.glob(os.path.join(pdf_folder, "*.pdf"))

if not pdf_files:
    print(f"no pdfs found in {pdf_folder}. wyd?")
    exit()

print(f"found {len(pdf_files)} pdfs")

for i, pdf_path in enumerate(pdf_files):
    filename = os.path.basename(pdf_path)
    print(f"processing {i+1}/{len(pdf_files)}: {filename}...")
    doc_chunks_data = []
    full_text_tokens = []
    page_map = [] # Stores (token_index, page_num)

    try:
        doc = fitz.open(pdf_path)
        current_token_index = 0
        for page_num, page in enumerate(doc):
            page_text = page.get_text("text")
            if not page_text:
                continue
            # Use the loaded tokenizer here
            page_tokens = tokenizer.encode(page_text, add_special_tokens=False)
            full_text_tokens.extend(page_tokens)
            # Record the start token index for each page
            page_map.append({"token_start_index": current_token_index, "page_num": page_num + 1})
            current_token_index += len(page_tokens)
        doc.close()

        # Now chunk the full_text_tokens
        if not full_text_tokens:
            print(f"  WARN: no text extracted from {filename}")
            continue

        doc_chunk_index = 0
        start_token = 0
        while start_token < len(full_text_tokens):
            end_token = start_token + chunk_size_tokens
            chunk_tokens = full_text_tokens[start_token:end_token]

            chunk_text = tokenizer.decode(chunk_tokens, skip_special_tokens=True)

            if not chunk_text.strip(): 
                 start_token += chunk_size_tokens - overlap_tokens 
                 continue

            start_page = -1
            end_page = -1
            for mapping in page_map:
                if start_page == -1 and mapping["token_start_index"] >= start_token:
                     for j in range(len(page_map) -1, -1, -1):
                          if page_map[j]["token_start_index"] <= start_token:
                               start_page = page_map[j]["page_num"]
                               break
                if mapping["token_start_index"] < end_token:
                    end_page = mapping["page_num"]
                elif start_page != -1:
                    break 

            if start_page == -1 and page_map: 
                start_page = page_map[0]["page_num"]
            if end_page == -1 and start_page != -1: 
                 end_page = start_page


            page_label = f"p{start_page}" if start_page == end_page or end_page == -1 else f"pp{start_page}-{end_page}"

            metadata = {
                "source": filename,
                "page_label": page_label, 
                "chunk_index_doc": doc_chunk_index, 
                "start_token_index": start_token,
                "end_token_index": min(end_token, len(full_text_tokens))
            }

            doc_chunks_data.append({
                "text": chunk_text,
                "metadata": metadata
            })

            doc_chunk_index += 1
            if end_token >= len(full_text_tokens):
                break 
            start_token += chunk_size_tokens - overlap_tokens 


    except Exception as e:
        print(f"  FAILED to process {filename}: {e}")
        continue

    all_chunks_data.extend(doc_chunks_data)
    print(f"  extracted {len(doc_chunks_data)} chunks.")


if not all_chunks_data:
    print("sad! no chunks were generated from any pdf. check pdfs or extraction logic.")
    exit()

# --- Embed all chunks ---
print(f"\nembedding {len(all_chunks_data)} chunks total...")
chunk_texts = [item['text'] for item in all_chunks_data]

embeddings = model.encode(chunk_texts, show_progress_bar=True)

final_data = []
for i, chunk_data in enumerate(all_chunks_data):
    final_data.append({
        "embedding": embeddings[i],
        "metadata": chunk_data['metadata'],
        "text": chunk_data['text'] 
    })

print(f"\nsaving {len(final_data)} vectors with metadata to {output_path}...")
try:
    with open(output_path, 'wb') as f:
        pickle.dump(final_data, f)
    print("done.")
except Exception as e:
    print(f"epic fail saving pickle file: {e}")