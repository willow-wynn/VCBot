import os
import glob
import pdfplumber

from llama_index.core.schema import Document
from llama_index.core.node_parser import SentenceSplitter
from llama_index.core.prompts import PromptTemplate, BasePromptTemplate
from llama_index.llms.lmstudio import LMStudio
from llama_index.finetuning import generate_qa_embedding_pairs
import random
import pickle
import logging
logging.getLogger("pdfminer").setLevel(logging.ERROR) # so that pdfminer doesn't spam warning messages

os.chdir("every-vc-bill") # might be a better way to do this

pdf_dir = "pdfs" 
txt_dir = "txts"
os.makedirs(txt_dir, exist_ok=True)

cache_path = "/Users/wynndiaz/VCBot/every-vc-bill/cached_nodes.pkl"
if os.path.exists(cache_path):
    print("Loading cached nodes...")
    with open(cache_path, "rb") as f:
        nodes = pickle.load(f)
    print(f"loaded {len(nodes)} cached chunks from {cache_path}")
else:
    print("No cached nodes found, parsing documents...")
    parser = SentenceSplitter(chunk_size=1024, chunk_overlap=50)
    nodes = []
    for txt_path in glob.glob(f"{txt_dir}/*.txt"):
        with open(txt_path, encoding="utf-8") as f:
            content = f.read() + ' '
        doc = Document(text=content, doc_id=txt_path)
        nodes.extend(parser.get_nodes_from_documents([doc]))


    print(f"parsed {len(nodes)} chunks")

    with open(cache_path, "wb") as f:
        pickle.dump(nodes, f)
    print(f"cached {len(nodes)} chunks to {cache_path}")

llm = LMStudio( # modify to openai/gemini model unless you have a NASA computer
    model_name="mlx-community/qwen3-30b-a3b",
    base_url="http://localhost:1234/v1",
)

qa_prompt_template = """\
You are a legislative assistant for a Discord server. You are given a chunk of text from a legislative document. 
You will be generating synthetic questions that will be answered by the document to finetune an RAG model.
The text you are given may be the beginning of a bill, or it may be a chunk of text from the middle or end of a bill.
Please diversify your queries, as they should reflect the types of real queries that Discord users might ask when looking for information about legislation.

---------------------
{context_str}
---------------------

Given the context information and no prior knowledge.
generate only questions based on the below query.

You are an LLM generating questions that will be used to finetune an RAG embedding model. Your task is to setup \
{num_questions_per_chunk} questions that would be answered by the document in question. The questions should be diverse in nature \
across the document. 

Your questions should be in the form of questions that would be asked by a Discord user when querying a legislative assistant.

For example: "What are some bills about [topic]?" or "When was the [bill in question] introduced?" or "What is the [bill in question] about?"

Do NOT under any circumstances include statements like "In this document" or "Under this bill" or "in this legislation" or "Under this Act". Your questions should primarily be based around asking which bills cover topics, not which topics are covered in the bill. 

If the document in question contains the beginning of the bill, one of your questions must be "what are some bills written by [author's name here]?". IF THE DOCUMENT DOES NOT CONTAIN THE BEGINNING OF THE BILL, DO NOT ASK THIS QUESTION.
Do not include agencies or offices in the author question, if one is present. Only include the name. Do not ask this question if the name is not in the chunk.

Use diverse formatting in how you ask your questions and do not start them with the same sentences/strings. Under absolutely no circumstances should you mention "This bill" or "This document" in your queries.

If the chunk contains the DATE THE SPECIFIC BILL WAS INTRODUCED, you must include the question "What are some bills from [month, year]?". You must vary the wording you use; do not use this exact wording.

All your questions should involve *which bill to retrieve*, not *the direct content of a predefined bill*. For example, do not ask questions about what line certain text is in, etc.
VARY YOUR PHRASING. Your questions should be diverse and structured in diverse manners, as your goal is to simulate the types of questions legislators seeking information on past legislation might ask.
You should ask simple queries as well, with varied language: "bills about", "find me some bills about", "bills that" "bills by"... etc.
Under NO circumstances should you begin your questions with "here are..." or any other form of preamble. Respond ONLY with the questions. Do not number your questions.

"""

data = generate_qa_embedding_pairs(nodes=nodes, llm=llm, save_every=10, retry_limit=5, num_questions_per_chunk = 8, verbose=True, output_path="/Users/wynndiaz/VCBot/final_qa_dataset.json", qa_generate_prompt_tmpl=qa_prompt_template)
# The above function is extremely computationally intensive if you use a local model. ~1MTok input, ~2MTok output. Costs between $1 and $30 depending on API used (gemini flash vs Claude Sonnet) if you use API.
# Recommend M3/4 Max/Ultra with at least 48GB of unified memory or 2x RTX 3090 or better. Otherwise, use cloud model or rent H100
# I had to monkey patch llama-index so that Gemma3 wouldn't generate boilerplate that gets passed into the pairs
# Either use the built-in qa_generate_prompt_template argument or monkey patch the function in your library
 # use this prompt
data.save_json('/Users/wynndiaz/VCBot/final_qa_dataset.json') # if your initial pass fails and you need to run it again delete the file and change the name of the JSON that gets saved
import json
from sklearn.model_selection import train_test_split
import copy 
input_filepath = '/Users/wynndiaz/VCBot/final_qa_dataset.json'
train_filepath = '/Users/wynndiaz/VCBot/final_train_dataset.json'
val_filepath = '/Users/wynndiaz/VCBot/final_val_dataset.json'
val_split_ratio = 0.1 # 20% for validation

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