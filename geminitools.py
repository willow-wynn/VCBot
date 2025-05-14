import os
import discord
import asyncio
from botcore import intents, client, tree
from config import KNOWLEDGE_FILES, BILL_TXT_STORAGE
from dotenv import load_dotenv
import traceback
from collections import defaultdict
from vector_search import search_vectors_simple, load_search_model, model_path, vector_pkl
import pandas as pd
import requests
import re
from registry import register_tool
load_dotenv()
GUILD_ID = int(os.getenv("GUILD"))


@register_tool
def call_knowledge(file_to_call: str) -> str:
    """
    calls a specific piece or pieces of information from your knowledge base.
    parameters:
      file_to_call: which knowledge file to call. one of ["rules", "constitution", "server_information", "house_rules", "senate_rules"].
    """
    with open(KNOWLEDGE_FILES[file_to_call], "r") as file:
        return file.read()

@register_tool
async def call_other_channel_context(channel_name: str, number_of_messages_called: int, search_query: str = None):
    """
    calls information from another channel in the server.

    parameters:
      channel_name: which channel to call information from. one of ["server-announcements", "twitter-rp", "official-rp-news", "virtual-congress-chat", "staff-announcements", "election-announcements", "house-floor", "senate-floor"].
      number_of_messages_called: how many messages to return from the channel in question. maximum 50. request 10 unless otherwise specified.
      search_query: what specific information to search for in the channel. only returns information that directly matches the search query. leave blank unless user explicitly asks for query.
    """
    GUILD = client.get_guild(GUILD_ID)
    try:
        channel_to_call = discord.utils.get(GUILD.text_channels, name=channel_name)
        if channel_to_call is None:
            raise ValueError(f"channel '{channel_name}' not found in guild '{GUILD.name}'")
        messages = []
        async for message in channel_to_call.history(limit=number_of_messages_called):
            if search_query is None or search_query.lower() in message.content.lower():
                messages.append(message)
        print("Messages found successfully!")
        return messages
    except Exception as e:
        print(f"cotc failed {e}")

@register_tool
def call_bill_search(query: str, top_k: int, reconstruct_bills_from_chunks: bool):
    """
    calls a simple RAG system for vector search through the legislative corpus.

    parameters:
      query: the question the user is asking about the legislation. this will be used to search through the corpus and will return the top result. phrasing the question as a question likely results in better outputs.
      top_k: the number of results to return from the corpus. 5 is a good number for most queries. 10 is the maximum. assign a value of 1 if the user is asking about a single specific bill.
      reconstruct_bills_from_chunks: whether or not to reconstruct the bills from the chunks returned. use for discussion about specific bill. if the user is asking about a general topic, set to false with high top_k.
    """
    print(f"\n--- Running Bill Search ---")
    print(f"Query: '{query}'")
    print(f"Top K Chunks Req: {top_k}")
    print(f"Reconstruct Bills: {reconstruct_bills_from_chunks}")

    # 1. Validate Inputs
    if not query or not query.strip():
        print("ERROR: Query cannot be empty.")
        return {"error": "Query cannot be empty."}

    original_top_k = top_k
    top_k = max(1, min(int(top_k), 10)) # Ensure integer, clamp
    if top_k != original_top_k:
        print(f"INFO: Clamped top_k from {original_top_k} to {top_k} (min 1, max 10).")


    # 2. Load Model (lazily/globally)
    try:
        model = load_search_model(model_path)
    except (RuntimeError, FileNotFoundError) as e:
         print(f"ERROR: Model loading failed, cannot proceed. {e}")
         # Return error dict as the function cannot operate
         return {"error": f"Failed to load embedding model: {e}"}
    except Exception as e: # Catch any other unexpected loading error
         print(f"UNEXPECTED ERROR during model load: {e}")
         print(traceback.format_exc())
         return {"error": f"Unexpected error loading model: {e}"}


    # 3. Perform Vector Search
    try:
        # Ensure search_vectors_simple is available in the scope
        search_results = search_vectors_simple(query, model, vector_pkl, k=top_k)
        # search_vectors_simple should return [] if no results, or raise error on failure
        if not isinstance(search_results, list):
             # This case shouldn't happen if search_vectors_simple adheres to its contract
             print(f"ERROR: Search function returned unexpected type: {type(search_results)}")
             return {"error": "Search function returned unexpected data type."}
        if not search_results:
             print("INFO: Vector search returned no relevant chunks.")
             return [] # Return empty list for no results, not an error

    except NameError:
         print("CRITICAL ERROR: search_vectors_simple function not defined or imported.")
         # This is a setup error, return error dict
         return {"error": "Search function (search_vectors_simple) is not available."}
    except FileNotFoundError as e:
         print(f"ERROR: Vector data file not found during search: {e}")
         # File essential for search is missing
         return {"error": f"Vector data file not found: {vector_pkl}"}
    except (RuntimeError, Exception) as e: # Catch errors raised by search_vectors_simple or others
        print(f"ERROR: An error occurred during vector search: {e}")
        print(traceback.format_exc())
        # Treat search failure as an error condition for the tool call
        return {"error": f"Error during vector search: {e}"}


    # 4. Process Results based on reconstruction flag
    if not reconstruct_bills_from_chunks:
        print(f"INFO: Returning {len(search_results)} raw chunk results.")
        return search_results
    else:
        print("INFO: Reconstructing bill text from retrieved chunks...")
        bills_data = defaultdict(list)
        missing_metadata_count = 0
        for chunk in search_results:
            # Validate chunk structure before accessing keys
            if not isinstance(chunk, dict) or 'metadata' not in chunk or not isinstance(chunk['metadata'], dict) or 'source' not in chunk['metadata']:
                print(f"WARN: Skipping chunk with invalid structure or missing metadata/source: {chunk}")
                missing_metadata_count += 1
                continue
            source = chunk['metadata']['source']
            bills_data[source].append(chunk)

        if missing_metadata_count > 0:
             print(f"WARN: Skipped {missing_metadata_count} chunks due to missing/invalid metadata.")

        reconstructed_bills = []
        print(f"INFO: Found chunks related to {len(bills_data)} unique bill source(s).")

        for bill_filename, chunks in bills_data.items():
            # Sort chunks by their index within the document
            try:
                # Ensure chunk_index_doc exists and is sortable (int)
                sorted_chunks = sorted(chunks, key=lambda c: int(c['metadata']['chunk_index_doc']))
            except (KeyError, ValueError, TypeError) as e:
                print(f"WARN: Cannot sort chunks for '{bill_filename}' reliably using 'chunk_index_doc' (Error: {e}). Concatenating in order received.")
                # Keep original order from search results if index missing/invalid
                sorted_chunks = chunks

            if not sorted_chunks: continue # Should not happen if bills_data[bill_filename] was non-empty

            # Concatenate text - ensure text exists and is string
            reconstructed_text = " ".join([str(c.get('text', '')) for c in sorted_chunks])

            # Calculate max score - ensure score exists and is numeric
            try:
                 max_score = float(max([c.get('score', -1.0) for c in sorted_chunks])) # Use -1 default if score missing?
            except (ValueError, TypeError) as e:
                 print(f"WARN: Could not determine max score for '{bill_filename}' due to invalid score data (Error: {e}). Setting to -1.")
                 max_score = -1.0


            reconstructed_bills.append({
                "source_bill": bill_filename,
                "reconstructed_text": reconstructed_text,
                "max_score": max_score,
                "contributing_chunks": len(sorted_chunks)
            })
            print(f"  Reconstructed '{bill_filename}' from {len(sorted_chunks)} chunk(s), max score: {max_score:.4f}")

        # Sort the final list of reconstructed bills by max_score (descending)
        reconstructed_bills.sort(key=lambda b: b.get('max_score', -1.0), reverse=True)

        print(f"INFO: Returning {len(reconstructed_bills)} reconstructed bill(s).")
        return reconstructed_bills   
def fetch_public_gdoc_text(gdoc_url):
    # extract file id
    match = re.search(r"/document/d/([a-zA-Z0-9-_]+)", gdoc_url)
    if not match:
        raise ValueError("invalid gdoc url")
    file_id = match.group(1)

    export_url = f"https://docs.google.com/document/d/{file_id}/export?format=txt"
    resp = requests.get(export_url)
    
    if resp.status_code != 200:
        raise RuntimeError(f"failed to fetch doc: status {resp.status_code}")
    
    return resp.text
def bill_keyword_search(keyword: str):
    bill_data = [
        {"filename": name, "text": open(os.path.join(BILL_TXT_STORAGE, name), "r").read()}
        for name in os.listdir(BILL_TXT_STORAGE)
    ]
    df = pd.DataFrame(bill_data)
    mask = df["text"].str.contains(keyword, na=False, case=False)
    return(df[mask])


    


# --- Sanitization utilities (prevents unwanted mentions and unsafe filenames) ---
def sanitize(text: str) -> str:
    """
    prevent accidental mass‑pings and unwanted role mentions.
    breaks @everyone, @here, and role mentions (<@&ROLE_ID).
    """
    if text is None:
        return text
    return (
        text.replace("@everyone", "@ everyone")
            .replace("@here", "@ here")
            .replace("<@&", "< @&")
    )

def sanitize_filename(name: str) -> str:
    import re
    name = re.sub(r'[^\w\s.-]', '', name)
    return name.strip()