import os
import glob
import pdfplumber

from llama_index.core.schema import Document
from llama_index.core.node_parser import SentenceSplitter
from llama_index.core.prompts import PromptTemplate
from llama_index.llms.ollama import Ollama
from llama_index.finetuning import generate_qa_embedding_pairs
import random
import logging
logging.getLogger("pdfminer").setLevel(logging.ERROR) # so that pdfminer doesn't spam warning messages

os.chdir("every-vc-bill") # might be a better way to do this

pdf_dir = "pdfs" 
txt_dir = "txts"
os.makedirs(txt_dir, exist_ok=True)

for pdf_path in glob.glob(f"{pdf_dir}/*.pdf"):
    name = os.path.splitext(os.path.basename(pdf_path))[0]
    txt_path = f"{txt_dir}/{name}.txt"
    with pdfplumber.open(pdf_path) as pdf:
        pages = [p.extract_text() or "" for p in pdf.pages]
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write("\n\n".join(pages))

parser = SentenceSplitter(chunk_size=4096, chunk_overlap=50)
nodes = []
for txt_path in glob.glob(f"{txt_dir}/*.txt"):
    with open(txt_path, encoding="utf-8") as f:
        content = f.read() + ' '
    doc = Document(text=content, doc_id=txt_path)
    nodes.extend(parser.get_nodes_from_documents([doc]))


print(f"parsed {len(nodes)} chunks")

gemma_chat_template_string = """{%- if messages[0]['role'] == 'system' -%}
    {%- set system_message_content = messages[0]['content'] -%}
    {%- set loop_messages = messages[1:] -%}
{%- else -%}
    {%- set system_message_content = '' -%}
    {%- set loop_messages = messages -%}
{%- endif -%}
{%- for message in loop_messages -%}
    {%- set is_user_turn = (loop.index0 + (1 if system_message_content else 0)) % 2 == 0 -%}
    {%- if (message['role'] == 'user') != is_user_turn -%}
        {{ raise_exception('Conversation roles must alternate user/assistant/user/assistant/...') }}
    {%- endif -%}
    {%- if message['role'] == 'assistant' -%}
        {%- set role = 'model' -%}
    {%- else -%}
        {%- set role = message['role'] -%}
    {%- endif -%}
<start_of_turn>{{ role }}
{%- if loop.first and system_message_content -%}
{{- system_message_content + '\n\n' -}}
{%- endif -%}
{{- message['content'] | trim -}}
<end_of_turn>
{% endfor %}
{%- if add_generation_prompt %}
<start_of_turn>model
{%- endif -%}
""" # if you use a model other than gemma replace the jinja2 chat template string here

chat_template = PromptTemplate(
    template=gemma_chat_template_string,  
    template_format="jinja2",
)

llm = Ollama( # modify to openai/gemini model unless you have a NASA computer
    model="gemma3:27B",
    query_wrapper_prompt=chat_template, # Now uses the correctly defined template
    max_new_tokens=4096,
    context_window=8 * 4096,
)


data = generate_qa_embedding_pairs(nodes=nodes, llm=llm, save_every=10, retry_limit=5, num_questions_per_chunk = 3, verbose=True, output_path="qa_dataset_new.json") 
# The above function is extremely computationally intensive if you use a local model. ~1MTok input, ~2MTok output. Costs between $1 and $30 depending on API used (gemini flash vs Claude Sonnet) if you use API.
# Recommend M3/4 Max/Ultra with at least 48GB of unified memory or 2x RTX 3090 or better. Otherwise, use cloud model or rent H100
# I had to monkey patch llama-index so that Gemma3 wouldn't generate boilerplate that gets passed into the pairs
# Either use the built-in qa_generate_prompt_template argument or monkey patch the function in your library
"""
Context information is below.

---------------------
{context_str}
---------------------

Given the context information and no prior knowledge, \
generate only questions based on the below query.

You are a Teacher/ Professor. Your task is to setup \
{num_questions_per_chunk} questions for an upcoming \
quiz/examination. The questions should be diverse in nature \
across the document. Restrict the questions to the \
context information provided. 
Under absolutely no circumstances should you preface your questions with \
"Here are" or any similar information. You should ONLY generate questions. 

BAD example:
"Here are three questions based on..."

GOOD example:

"1) [question]
2) [question]
3) [question]"

You are creating a QA dataset for an embedding model. This means that 2/3 or so of your questions should be *general legal questions*, the type that would occur over a very general query. For example, if the provided chunk is about abortion, you could ask "What are some bills that do x y and z with abortion"? 

Generally, your questions should focus on "which bills" - followed by a question answered in the document - rather than "In the document which..."
""" # use this prompt
data.save_json('/Users/wynndiaz/VCBot/qa_dataset_third.json') # if your initial pass fails and you need to run it again delete the file and change the name of the JSON that gets saved
import json
from sklearn.model_selection import train_test_split
import copy 
input_filepath = '/Users/wynndiaz/VCBot/qa_dataset_third.json'
train_filepath = '/Users/wynndiaz/VCBot/train_dataset_third.json'
val_filepath = '/Users/wynndiaz/VCBot/val_dataset)_third.json'
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