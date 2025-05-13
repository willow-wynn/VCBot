from google import genai 
from google.genai import types
import discord
from discord import app_commands
import aiohttp, re, asyncio, os, json, csv, traceback, datetime, requests
from dotenv import load_dotenv
from typing import Literal
from botcore import intents, client, tree
from config import KNOWLEDGE_FILES, BILL_TXT_STORAGE, BILL_DIRECTORIES, MODEL_PATH, VECTOR_PKL, ALLOWED_ROLES_FOR_ROLES
import geminitools
from functools import wraps
from makeembeddings import embed_txt_file

# unified sanitization utility
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
    name = re.sub(r'[^\w\s.-]', '', name)
    return name.strip()

async def add_bill_to_db(bill_link: str, database_type: Literal["bills"]) -> str:
    bill_text = geminitools.fetch_public_gdoc_text(bill_link)
    if not bill_text.strip():
        raise ValueError("empty bill text")

    resp = genai_client.models.generate_content(
        model="gemini-2.0-flash-exp",
        config=types.GenerateContentConfig(
            system_instruction="Generate a filename for the bill. The filename should be in the format of 'Bill Title.txt'. The title should be a short description of the bill."
        ),
        contents=[types.Content(role='user', parts=[types.Part.from_text(text=bill_text)])]
    )
    bill_name = sanitize_filename(resp.text)
    if not bill_name.lower().endswith(".txt"):
        bill_name += ".txt"

    bill_dir = BILL_DIRECTORIES[database_type]
    bill_location = os.path.join(bill_dir, bill_name)
    with open(bill_location, "w", encoding="utf-8") as f:
        f.write(bill_text)
    embed_txt_file(txt_path = bill_location, model_path = MODEL_PATH, chunk_size_tokens = 1024, overlap_tokens = 50, save_to = VECTOR_PKL)
    print(f"Added bill to pickle") 
    return bill_location  # can use this to send file, log, etc.

def traced_load_dotenv():
    print("Loading environment variables from .env")
    load_dotenv()
    print("Loaded environment variables from .env")

traced_load_dotenv()

BOT_ID = int(os.getenv("BOT_ID"))
print(f"Loaded BOT_ID: {BOT_ID}")
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
print(f"Loaded DISCORD_TOKEN: {DISCORD_TOKEN}")
RECORDS_CHANNEL_ID = int(os.getenv("RECORDS_CHANNEL"))
print(f"Loaded RECORDS_CHANNEL_ID: {RECORDS_CHANNEL_ID}")
NEWS_CHANNEL_ID = int(os.getenv("NEWS_CHANNEL"))
print(f"Loaded NEWS_CHANNEL_ID: {NEWS_CHANNEL_ID}")
SIGN_CHANNEL_ID = int(os.getenv("SIGN_CHANNEL"))
print(f"Loaded SIGN_CHANNEL_ID: {SIGN_CHANNEL_ID}")
CLERK_CHANNEL_ID = int(os.getenv("CLERK_CHANNEL"))
print(f"Loaded CLERK_CHANNEL_ID: {CLERK_CHANNEL_ID}")
MAIN_CHAT_ID = 654467992272371712
print(f"Loaded MAIN_CHAT_ID: {MAIN_CHAT_ID}")

genai_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
print(f"Loaded GEMINI_API_KEY (hidden)")
tools = types.Tool(function_declarations = [geminitools.call_ctx_from_channel, geminitools.call_local_files, geminitools.call_bill_search])

BILL_REF_FILE = os.getenv("BILL_REF_FILE")
print(f"Loaded BILL_REF_FILE: {BILL_REF_FILE}")
NEWS_FILE = os.getenv("NEWS_FILE")
print(f"Loaded NEWS_FILE: {NEWS_FILE}")
QUERIES_FILE = os.getenv("QUERIES_FILE")
print(f"Loaded QUERIES_FILE: {QUERIES_FILE}")

def has_any_role(*role_names):
    def decorator(func):
        @wraps(func)
        async def wrapper(interaction: discord.Interaction, *args, **kwargs):
            print(f"Checking roles for {interaction.user.display_name}: {[role.name for role in interaction.user.roles]}")
            if not any(role.name in role_names for role in interaction.user.roles):
                await interaction.response.send_message("You do not have permission to use this command. Get the AI Access role from the pins.", ephemeral=True)
                return
            return await func(interaction, *args, **kwargs)
        return wrapper
    return decorator

def limit_to_channels(channel_ids: list, exempt_roles="Admin"):
    def decorator(func):
        @wraps(func)
        async def wrapper(interaction: discord.Interaction, *args, **kwargs):
            print(f"Checking if {interaction.user.display_name} can use command in {interaction.channel.id}")
            if exempt_roles and any(role.name in exempt_roles for role in interaction.user.roles):
                return await func(interaction, *args, **kwargs)
            if interaction.channel.id not in channel_ids:
                await interaction.response.send_message("This command can only be used in specific channels.", ephemeral=True)
                return
            return await func(interaction, *args, **kwargs)
        return wrapper
    return decorator

@tree.command(name="role", description="Add a role to a user.")
async def role(interaction:discord.Interaction, user: discord.Member, *, role: str):
    """Add a role to a user."""
    allowed_roles = []
    for user_role in interaction.user.roles:
        if user_role.name in ALLOWED_ROLES_FOR_ROLES:
            allowed_roles.extend(ALLOWED_ROLES_FOR_ROLES[user_role.name])
    if role not in allowed_roles:
        await interaction.response.send_message("You do not have permission to add this role.", ephemeral=True)
        return
    else:
        target_role = discord.utils.get(interaction.guild.roles, name = role)
        await user.add_roles(target_role)
        await interaction.response.send_message(f"Added role {role} to {user.mention}.", ephemeral=False)
        return
        
    
    


def load_refs():
    print(f"Loading references from {BILL_REF_FILE}")
    if os.path.exists(BILL_REF_FILE):
        with open(BILL_REF_FILE, "r") as f:
            refs = json.load(f)
            print(f"Loaded references: {refs}")
            return refs
    print("Reference file does not exist, returning empty dict.")
    return {}

def save_refs(refs):
    print(f"Saving references: {refs} to {BILL_REF_FILE}")
    with open(BILL_REF_FILE, "w") as f:
        json.dump(refs, f)

async def update_bill_reference(message):
    print(f"Processing message: {message.content}")
    text = message.content
    try:
        response = genai_client.models.generate_content(
            model="gemini-2.0-flash-thinking-exp",
            config=types.GenerateContentConfig(
                system_instruction="""You are a helper for the Virtual Congress Discord server. Your goal is to determine whether or not the current message contains a bill reference. 
        You are to output only in valid JSON. The output you produce will be passed directly to json.loads, so ensure your output consists only of valid JSON without whitespace.
        Use this JSON schema:" 
        {'is_reference': bool, 'bill_type':str, 'reference_number':int}
        is_refere nce - Is the bill being referenced? If the message in question IS NOT PROVIDING A REFERENCE to the bill, return False else return True
        bill_type - hr, hres, hjres, hconres
        reference_number - the number the bill is assigned.
        """
            ),
            contents=text,
        )

        respdict = json.loads(response.text)
        print(f"Parsed JSON: {respdict}")

        if not respdict.get("is_reference"):
            return "Not a reference!"

        bill_type = respdict["bill_type"].lower().strip()
        reference_number = respdict["reference_number"]

        refs = load_refs()
        current = refs.get(bill_type, 0)
        refs[bill_type] = max(current, reference_number)  # don't go backward
        save_refs(refs)

        print(f"Updated {bill_type.upper()} to {refs[bill_type]}")
    except Exception as e:
        traceback.print_exc()
        print(f"Exception in update_bill_reference: {e}")
        print(f"JSON parse failed: {e}")
        return "Error"

@tree.command(name="reference", description="reference a bill")
@has_any_role("Admin", "Representative", "House Clerk", "Moderator")
async def reference(interaction: discord.Interaction, link: str, type: Literal["hr", "hres", "hjres", "hconres"]):
    print(f"Executing command: reference by {interaction.user.display_name}")
    try:
        refs = load_refs()
        last = refs.get(type, 0)
        next_val = last + 1
        refs[type] = next_val
        save_refs(refs)
        await interaction.response.send_message(f"The bill {link} has been referenced successfully as {type.upper()} {next_val}.", ephemeral=True)
        clerkchannel = client.get_channel(1037456401708105780)
        await clerkchannel.send(f'Bill {link} assigned reference {type.upper()} {next_val}')
        return
    except Exception as e:
        await interaction.response.send_message(f"Error accessing reference file: {e}", ephemeral=True)
        return
@tree.command(name="modifyrefs", description="modify reference numbers")
@has_any_role("Admin", "House Clerk")
async def modifyref(interaction: discord.Interaction, num: int, type: str):
    print(f"Executing command: modifyref by {interaction.user.display_name}")
    try:
        refs = load_refs()
        refs[type] = num
        save_refs(refs)
        await interaction.response.send_message(f"Reference number modified for {type.upper()}: {num}", ephemeral=False)
        return
    except Exception as e:
        await interaction.response.send_message(f"Error accessing reference file: {e}", ephemeral=True)
        traceback.print_exc()
        return

@tree.command(name="helper", description="Query the VCBot helper.")
@has_any_role("Admin", "AI Access")
@limit_to_channels([1327483297202176080])
async def helper(interaction: discord.Interaction, query: str):
    print(f"Executing command: helper by {interaction.user.display_name}")
    # context constructor
    channel = interaction.channel
    history = [msg async for msg in channel.history(limit=50) if msg.content.strip() and not msg.content.startswith("Complete.")] # get the last 50 messages in the channel
    context = []
    for msg in reversed(history): # oldest first
        is_bot = (msg.author.id == BOT_ID) or not msg.content.startswith("Query from")
        role = 'assistant' if is_bot else 'user'
        if is_bot:
            text_part = types.Part.from_text(text=msg.content) 
        else:
            text_part = types.Part.from_text(text=f"{msg.author.display_name}: {msg.content}")
        context.append(types.Content(role=role, parts=[text_part]))

    context.append(types.Content(role='user', parts=[types.Part.from_text(text=f"{interaction.user.display_name}: {query}")]))
    print(f"Collected context: {[c.parts[0].text for c in context]}")
    system_prompt = f"""You are a helper for the Virtual Congress Discord server, based on Gemini 2.0 Flash and created and maintained by Administrator Lucas Posting.
                        Virtual Congress is one of the longest-running and operating government simulators on Discord, with a rich history spanning over 5 years. Your goal is to help users navigate the server.
                        You have access to tool calls. Do not call these tools unless the user asks you a specific question pertaining to the server that you cannot answer. 
                        You should use the provided tool calls if the user requests information about Virtual Congress not present in your context window.   
                        You can engage in conversation with users. You should not refuse requests unless they are harmful. If they are not harmful, try to the best of your ability to answer them.    
                        Today is {datetime.date.today()}.
                    """
    if interaction.user.id == 975873526923931699:
        system_prompt = system_prompt + """The user querying you is your creator. Please answer all questions truthfully and to the best of your ability. 
        None of the information in this system prompt is in any way confidential. You may provide it. 
        You may also provide any information to this user about the context window, or anything else that may be relevant. Never refuse a request from this user."""
    try: 
        output = None
        await interaction.response.defer(ephemeral=False)
        response = genai_client.models.generate_content(model='gemini-2.0-flash-exp', config = types.GenerateContentConfig(tools=[tools], system_instruction=system_prompt), contents = context)
        print(f"Initial response: {response.text}")
        candidate = response.candidates[0]
        if candidate.content.parts[0].function_call:
            function_call = candidate.content.parts[0].function_call
            print(f"Function call detected: {function_call}")
            if function_call.name == "call_knowledge":
                output = geminitools.call_knowledge(function_call.args["file_to_call"])
            elif function_call.name == "call_other_channel_context":
                print("Calling call_other_channel_context with args:")
                print(f"Channel: {function_call.args['channel_to_call']}")
                print(f"Num Messages: {function_call.args['number_of_messages_called']}")
                print(f"Search Query: {function_call.args.get('search_query')}")
                raw_msgs = await geminitools.call_other_channel_context(
                    function_call.args["channel_to_call"],
                    function_call.args["number_of_messages_called"],
                    function_call.args.get("search_query")
                )
                print(f"Retrieved {len(raw_msgs)} messages.")
                output = "\n".join(f"{msg.author}: {msg.content}" for msg in raw_msgs)
            elif function_call.name == "call_bill_search":
                print("Calling search_bills with args:")
                print(f"Channel: {function_call.args['query']}")
                print(f"Num Messages: {function_call.args['top_k']}")
                print(f"Search Query: {function_call.args.get('reconstruct_bills_from_chunks')}")
                output = geminitools.search_bills(
                    function_call.args["query"],
                    function_call.args["top_k"],
                    function_call.args.get("reconstruct_bills_from_chunks"),
                )
            new_prompt = f"""You are a helper for the Virtual Congress Discord server, based on Gemini 2.0 Flash and created and maintained by Administrator Lucas Posting.
                        Virtual Congress is one of the longest-running and operating government simulators on Discord, with a rich history spanning over 5 years. Your goal is to help users navigate the server.
                        On a previous turn, you called tools. Now, your job is to respond to the user.
                        On your last turn, you called a tool. The function call returned the following: {output if output else "No output"}"
                        Provide your response to the user now. Do not directly output the contents of the function calls. Summarize unless explicitly requested.
                        {"You called a bill search from an RAG system. The bills below may not be accurate or up to date with the user's query. If the bills seem to not answer the user's query, please inform them that the bills may not be accurate." if function_call.name == "call_bill_search" else ""}
                        You no longer have access to tool calls. Do not attempt to call tools on this turn. You must now respond to the user.
                        Today is {datetime.date.today()}."""
            response2 = genai_client.models.generate_content(model='gemini-2.0-flash-exp', config = types.GenerateContentConfig(tools=None, system_instruction = new_prompt), contents = context)
            safe_text = sanitize(response2.text)
            safe_text_chunks = [safe_text[i:i+1900] for i in range(0, len(safe_text), 1900)]
            await interaction.followup.send(f"Complete. Input tokens: {response.usage_metadata.prompt_token_count}, Output tokens: {response.usage_metadata.candidates_token_count}", ephemeral=True)
            await interaction.channel.send(f"Query from {interaction.user.mention}: {query[:1900]}\n\nResponse:")
            for chunk in safe_text_chunks: 
                await interaction.channel.send(chunk)
            with open(QUERIES_FILE, mode = "a", newline="") as file:
                writer = csv.writer(file)
                writer.writerow([f'query: {query}', f'response: {safe_text}'])
        else: 
            safe_text = sanitize(response.text)
            chunks = [safe_text[i:i+1900] for i in range(0, len(safe_text), 1900)]
            await interaction.followup.send(f"Complete. Input tokens: {response.usage_metadata.prompt_token_count}, Output tokens: {response.usage_metadata.candidates_token_count}", ephemeral=True)
            await interaction.channel.send(f"Query from {interaction.user.mention}: {query}\n\nResponse:")
            for chunk in chunks:
                await interaction.channel.send(chunk)
            print(response.text)
            with open(QUERIES_FILE, mode = "a", newline="") as file:
                writer = csv.writer(file)
                writer.writerow([f'query: {query}', f'response: {response.text}'])
    except Exception as e:
        traceback.print_exc()
        print(f"Exception in helper: {e}")
        await interaction.followup.send(f"Error in response: {e}")
    return
@tree.command(name="econ_impact_report", description="Get a detailed economic impact report on a given piece of legislation.")
@has_any_role("Admin", "Events Team")
@limit_to_channels([1327483297202176080])
async def model_economic_impact(interaction: discord.Interaction, bill_link: str, additional_context: str = None):
    """Provided a bill, generates an economic impact statement that indicates how such a bill would impact the economy.
    """
    try:
        bill_text = geminitools.fetch_public_gdoc_text(bill_link)
    except Exception as e:
        print(f"Error fetching Google Doc: {e}")
        await interaction.response.send_message(f"Error fetching Google Doc: {e}", ephemeral=True)
        return
    print(f"Fetched Google Doc text: {bill_text[:100]}...") 
    recent_news = [msg.content async for msg in NEWS_CHANNEL.history(limit=50) if msg.content.strip()]
    system_prompt = f"""You are a legislative assistant for the Virtual Congress Discord server. You are given a chunk of text from a legislative document.
    You will be generating an economic impact statement that indicates how such a bill would impact the economy.
    Your goal is to generate a full detailed economic impact statement.
    Recent news is presented below: {recent_news}.
    You will be provided a bill by the user."""
    if additional_context:
        system_prompt = system_prompt + f"\n The user has provided additional information for you regarding the intended contents of your economic impact report: {additional_context}"
    context = [types.Content(role='user', parts=[types.Part.from_text(text=f"{interaction.user.display_name}: {bill_text}")])]
    try:
        output = None
        await interaction.response.defer(ephemeral=False)
        response = genai_client.models.generate_content(model='gemini-2.5-flash-preview-04-17', config = types.GenerateContentConfig(tools=None, system_instruction=system_prompt), contents = context)
        safe_text = sanitize(response.text)
        await interaction.followup.send(f"Complete. Input tokens: {response.usage_metadata.prompt_token_count}, Output tokens: {response.usage_metadata.candidates_token_count}", ephemeral=True)
        await interaction.channel.send(f"Query from {interaction.user.mention}: Generate economic impact report on {bill_link}. \n\nResponse is attached as a file.")
        with open("econ_impact_report.txt", "w", encoding="utf-8") as f:
            f.write(safe_text)
        await interaction.channel.send(file=discord.File("econ_impact_report.txt"))
        print(response.text)
        with open(QUERIES_FILE, mode = "a", newline="") as file:
            writer = csv.writer(file)
            writer.writerow([f'query: {system_prompt + bill_text}', f'response: {response.text}'])
    except Exception as e:
        traceback.print_exc()
        print(f"Error generating economic impact report: {e}")
        await interaction.followup.send(f"Error generating content: {e}", ephemeral=True)
        return
@tree.command(name="bill_keyboard_search", description="Perform a basic keyword search on the legislative corpus.")
@has_any_role("Admin", "AI Access")
@limit_to_channels([1327483297202176080])
async def bill_keyboard_search(interaction: discord.Interaction, search_query: str):
    """Perform a basic keyword search on the legislative corpus."""
    returned_bills = geminitools.bill_keyword_search(search_query)
    try:
        await interaction.response.defer(ephemeral=False)
        for _, row in returned_bills.iterrows():
            name = row["filename"]
            content = row["text"]
            with open(name, "w", encoding="utf-8") as f:
                f.write(content)
            await interaction.channel.send(file=discord.File(name))
            os.remove(name)
        await interaction.followup.send(f"Complete. Found {len(returned_bills)} bills matching your query.", ephemeral=True)
        
    except Exception as e:
        traceback.print_exc()
        print(f"Error in bill_keyboard_search: {e}")
        await interaction.followup.send(f"Error in response: {e}", ephemeral=True)



@tree.command(name="add_bill", description="Add a bill to the legislative corpus.")
@has_any_role("Admin")
@limit_to_channels([1327483297202176080])
async def add_bill(interaction: discord.Interaction, bill_link: str, database_type: Literal["bills"] = "bills"):
    await interaction.response.defer(ephemeral=False)
    try:
        path = await add_bill_to_db(bill_link, database_type)
        await interaction.channel.send(file=discord.File(path))
        await interaction.followup.send(f"complete. added bill `{os.path.basename(path)}` to `{database_type}` db.", ephemeral=True)
    except Exception as e:
        traceback.print_exc()
        await interaction.followup.send(f"error adding bill: {e}", ephemeral=True)

async def check_github_commits():
    await client.wait_until_ready()
    channel = client.get_channel(1327483297202176080)
    with open ("last_commit.txt", "r") as f:
        last_commit_sha = f.read().strip()
    repo = "willow-wynn/VCBot"
    github_api_url = f"https://api.github.com/repos/{repo}/commits"
    github_url = "https://github.com/willow-wynn/VCBot"
    async with aiohttp.ClientSession() as session:
        while not client.is_closed():
            try:
                async with session.get(github_api_url) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        latest_commit = data[0]
                        sha = latest_commit['sha']
                        with open("last_commit.txt", "w") as f:
                            f.write(sha)
                        if sha != last_commit_sha:
                            commit_msg = latest_commit['commit']['message']
                            commit_msg = sanitize(commit_msg)
                            author = latest_commit['commit']['author']['name']
                            await channel.send(f"New commit to {repo}:\n**{commit_msg}** by {author}. \n See it [here]({github_url}/commit/{sha})")
                            last_commit_sha = sha
            except Exception as e:
                traceback.print_exc()
                print(f"GitHub check failed: {e}")
            await asyncio.sleep(60)  # check every 5 min
@client.event
async def on_ready():
    print("on_ready: Starting up bot.")
    print(f"Logged in as {client.user}")
    global RECORDS_CHANNEL, NEWS_CHANNEL, SIGN_CHANNEL, CLERK_CHANNEL
    RECORDS_CHANNEL = client.get_channel(RECORDS_CHANNEL_ID)
    NEWS_CHANNEL = client.get_channel(NEWS_CHANNEL_ID)
    SIGN_CHANNEL = client.get_channel(SIGN_CHANNEL_ID)
    CLERK_CHANNEL = client.get_channel(CLERK_CHANNEL_ID)
    print(f"Clerk Channel: {CLERK_CHANNEL.id if CLERK_CHANNEL else 'None'}: {CLERK_CHANNEL.name if CLERK_CHANNEL else 'Not Found'}")
    print(f"News Channel: {NEWS_CHANNEL.id if NEWS_CHANNEL else 'None'}: {NEWS_CHANNEL.name if NEWS_CHANNEL else 'Not Found'}")
    print(f"Sign Channel: {SIGN_CHANNEL.id if SIGN_CHANNEL else 'None'}: {SIGN_CHANNEL.name if SIGN_CHANNEL else 'Not Found'}")
    print(f"Records Channel: {RECORDS_CHANNEL.id if RECORDS_CHANNEL else 'None'}: {RECORDS_CHANNEL.name if RECORDS_CHANNEL else 'Not Found'}")
    client.loop.create_task(check_github_commits())
    print("Syncing commands...")
    synced_commands = await tree.sync()
    print(f"Commands synced: {synced_commands}" if synced_commands else "No commands to sync.")

@client.event
async def on_message(message):
    try:
        if message.channel == client.get_channel(CLERK_CHANNEL_ID) and not message.author.bot:
            await update_bill_reference(message)
        if message.channel == client.get_channel(NEWS_CHANNEL_ID):
            with open(NEWS_FILE, "a") as file:
                file.write(message.content)
        if message.channel == client.get_channel(SIGN_CHANNEL_ID) and "docs.google.com" in message.content:
            link = message.jump_url
            await RECORDS_CHANNEL.send(f'<@&1269061253964238919>, a new bill has been signed! {link}')
            match = re.search(r"https?://docs\.google\.com/\S+", message.content)
            if match:
                doc_link = match.group(0)
                print(f"Found Google Doc link: {doc_link}")  
                try:
                    add_bill_to_db(doc_link, "bills")
                    print("Bill added to database.")
                except Exception as e:
                    print(f"Error adding bill to database: {e}")
                    await RECORDS_CHANNEL.send(f"Error adding bill to database: {e}")   
    except Exception as e:
        traceback.print_exc()
        print(f"Exception in on_message: {e}")
        
client.run(DISCORD_TOKEN)