import os
import glob
import pdfplumber

from llama_index.core.schema import Document
from llama_index.core.node_parser import SentenceSplitter
from llama_index.core.prompts import PromptTemplate
from llama_index.llms.ollama import Ollama
from llama_index.finetuning import generate_qa_embedding_pairs

pdf_dir = "every-vc-bill/pdfs"
txt_dir = "every-vc-bill/data/txts"
os.makedirs(txt_dir, exist_ok=True)

print("starting pdf extraction...")

for pdf_path in glob.glob(f"{pdf_dir}/*.pdf"):
    name = os.path.splitext(os.path.basename(pdf_path))[0]
    txt_path = f"{txt_dir}/{name}.txt"
    print(f"processing {pdf_path} -> {txt_path}") 

    try: 
        with pdfplumber.open(pdf_path) as pdf:
            pages = [p.extract_text() or "" for p in pdf.pages]
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write("\n\n".join(pages))
        print(f"  successfully extracted {len(pages)} pages.") 

    except Exception as e:
        print(f"[ERROR] failed to process {pdf_path}: {e}")
        if os.path.exists(txt_path):
            os.remove(txt_path)
        continue 

print("pdf extraction finished.") 

parser = SentenceSplitter(chunk_size=512, chunk_overlap=50)
nodes = []
for txt_path in glob.glob(f"{txt_dir}/*.txt"):
    with open(txt_path, encoding="utf-8") as f:
        content = f.read()
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
"""

chat_template = PromptTemplate(
    template=gemma_chat_template_string,  
    # input_variables=["messages", "add_generation_prompt"]
    template_format="jinja2",
)

llm = Ollama(
    model="gemma3:27B",
    query_wrapper_prompt=chat_template, # Now uses the correctly defined template
    max_new_tokens=2048,
    context_window=8 * 1024,
)


dataset = generate_qa_embedding_pairs(nodes=nodes, llm=llm)
dataset.save_json("qa_embedding_dataset.json")