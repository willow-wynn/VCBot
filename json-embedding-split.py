import json
from sklearn.model_selection import train_test_split
import copy # Used for deep copying the corpus

# --- config ---
# Use the uploaded file's name directly
input_filepath = '/Users/wynndiaz/VCBot/qa_dataset.json'
train_filepath = '/Users/wynndiaz/VCBot/train_dataset.json'
val_filepath = '/Users/wynndiaz/VCBot/val_dataset.json'
val_split_ratio = 0.2 # 20% for validation

# --- load data ---
try:
    with open(input_filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
except FileNotFoundError:
    print(f"bruh, file not found: {input_filepath}")
    exit()
except json.JSONDecodeError as e:
    print(f"invalid json in {input_filepath}: {e}")
    exit()

# --- extract components ---
queries = data.get('queries', {})
corpus = data.get('corpus', {})
relevant_docs = data.get('relevant_docs', {})
# Add handling for embeddings if they exist in your file
# embeddings = data.get('embeddings', {}) # Example

if not queries or not relevant_docs:
    print("weird, 'queries' or 'relevant_docs' missing/empty in the json.")
    # If corpus is also missing, there's nothing to split
    if not corpus:
      print("also no corpus... file might be empty or malformed. exiting.")
      exit()
    else:
      print("continuing without query/relevant_doc split, just copying corpus.")
      # Handle the case where only corpus exists? Or just exit? Let's exit for now.
      exit()


query_ids = list(queries.keys())

# --- split query IDs ---
if len(query_ids) < 2:
  print("lol not enough queries to split. need at least 2.")
  exit()

# Handle case where test_size results in 0 or all items for one set
n_total = len(query_ids)
n_val = int(n_total * val_split_ratio)
n_train = n_total - n_val

if n_val == 0 or n_train == 0:
    print(f"split ratio {val_split_ratio} results in an empty set for {n_total} items. adjust ratio or check data.")
    # Decide how to handle: maybe default to minimum 1 item? Or exit? Let's exit.
    exit()


train_query_ids, val_query_ids = train_test_split(
    query_ids,
    test_size=val_split_ratio,
    random_state=42 # for reproducibility
)

print(f"total query IDs: {len(query_ids)}")
print(f"training query IDs: {len(train_query_ids)}")
print(f"validation query IDs: {len(val_query_ids)}")

# --- create train dataset ---
train_data = {
    'queries': {qid: queries[qid] for qid in train_query_ids if qid in queries},
    'corpus': copy.deepcopy(corpus), # Keep the full corpus
    'relevant_docs': {qid: relevant_docs[qid] for qid in train_query_ids if qid in relevant_docs}
    # Add embeddings if they exist and need splitting
    # 'embeddings': filter_embeddings(embeddings, train_query_ids) # Placeholder
}

# --- create validation dataset ---
val_data = {
    'queries': {qid: queries[qid] for qid in val_query_ids if qid in queries},
    'corpus': copy.deepcopy(corpus), # Keep the full corpus
    'relevant_docs': {qid: relevant_docs[qid] for qid in val_query_ids if qid in relevant_docs}
    # Add embeddings if they exist and need splitting
    # 'embeddings': filter_embeddings(embeddings, val_query_ids) # Placeholder
}

# --- save datasets ---
def save_json(data, filepath):
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4) # indent=4 for readability
        print(f"saved data to {filepath}")
    except Exception as e:
        print(f"oof, failed to save {filepath}: {e}")

save_json(train_data, train_filepath)
save_json(val_data, val_filepath)

print("split complete.")