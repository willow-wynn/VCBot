from google import genai
import re
from google.genai import types
import discord
from discord import app_commands
import asyncio
from dotenv import load_dotenv
import os
import json
from typing import Literal
import geminitools
import csv
from botcore import intents, client, tree
from config import KNOWLEDGE_FILES
import traceback

load_dotenv()

BOT_ID = os.getenv("BOT_ID")
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
RECORDS_CHANNEL_ID = int(os.getenv("RECORDS_CHANNEL"))
NEWS_CHANNEL_ID = int(os.getenv("NEWS_CHANNEL"))
SIGN_CHANNEL_ID = int(os.getenv("SIGN_CHANNEL"))
CLERK_CHANNEL_ID = int(os.getenv("CLERK_CHANNEL"))



genai_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
tools = types.Tool(function_declarations = [geminitools.call_ctx_from_channel, geminitools.call_local_files])

BILL_REF_FILE = os.getenv("BILL_REF_FILE")
NEWS_FILE = os.getenv("NEWS_FILE")
QUERIES_FILE = os.getenv("QUERIES_FILE")

def has_any_role(*role_names):
    async def predicate(interaction: discord.Interaction):
        return any(role.name in role_names for role in interaction.user.roles)
    return app_commands.check(predicate)

def load_refs():
    if os.path.exists(BILL_REF_FILE):
        with open(BILL_REF_FILE, "r") as f:
            return json.load(f)
    return {}

def save_refs(refs):
    with open(BILL_REF_FILE, "w") as f:
        json.dump(refs, f)

async def update_bill_reference(message):
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
        print(f"JSON parse failed: {e}")
        traceback.print_exc()
        return "Error"

@tree.command(name="reference", description="reference a bill")
@has_any_role("Admin", "Representative", "House Clerk", "Moderator")
async def reference(interaction: discord.Interaction, link: str, type: Literal["hr", "hres", "hjres", "hconres"]):
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
async def helper(interaction: discord.Interaction, query: str):
    channel = interaction.channel
    context = [
    types.Content(
        role='model' if msg.author.id == BOT_ID else 'user',
        parts=[types.Part.from_text(text=f"{msg.author.display_name} at {msg.created_at}:\n{msg.content}")]
    )
    async for msg in channel.history(limit=50)
    if msg.content.strip()
]
    context.append(types.Content(role='user', parts=[types.Part.from_text(text=f"{interaction.user.display_name}: {query}")]))
    system_prompt = f"""You are a helper for the Virtual Congress Discord server, based on Gemini 2.0 Flash and created and maintained by Administrator Lucas Posting.
                        Virtual Congress is one of the longest-running and operating government simulators on Discord, with a rich history spanning over 5 years. Your goal is to help users navigate the server.
                        You have access to tool calls. Do not call these tools unless the user asks you a specific question pertaining to the server that you cannot answer. 
                        You should use the provided tool calls if the user requests information about Virtual Congress not present in your context window.          
                    """
    try: 
        output = None
        await interaction.response.defer(ephemeral=False)
        response = genai_client.models.generate_content(model='gemini-2.0-flash', config = types.GenerateContentConfig(tools=[tools], system_instruction=system_prompt), contents = context)
        if response.candidates[0].content.parts[0].function_call:
            function_call = response.candidates[0].content.parts[0].function_call
            print(f"called function {function_call.name}")
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
            if output:
                context.append(f"On your last turn, you called function {function_call.name}. The function call returned the following: {output}")
            new_prompt = f"""You are a helper for the Virtual Congress Discord server, based on Gemini 2.0 Flash and created and maintained by Administrator Lucas Posting.
                        Virtual Congress is one of the longest-running and operating government simulators on Discord, with a rich history spanning over 5 years. Your goal is to help users navigate the server.
                        You have access to tool calls. Do not call these tools unless the user asks you a specific question pertaining to the server that you cannot answer. 
                        On a previous turn, you called tools. Now, your job is to respond to the user.
                        Provide your response to the user now. Do not directly output the contents of the function calls. Summarize unless explicitly requested."""
            response2 = genai_client.models.generate_content(model='gemini-2.0-flash', config = types.GenerateContentConfig(tools=None, system_instruction = new_prompt), contents = context)
            safe_text = re.sub(r'@everyone', '@ everyone', response2.text)
            safe_text = re.sub(r'@here', '@ here', safe_text)
            safe_text = re.sub(r'<@&', '< @&', safe_text)
            safe_text_chunks = [safe_text[i:i+1900] for i in range(0, len(safe_text), 1900)]
            await interaction.followup.send(f"Complete. Input tokens: {response.usage_metadata.prompt_token_count}, Output tokens: {response.usage_metadata.candidates_token_count}", ephemeral=True)
            await interaction.channel.send(f"Query from {interaction.user.mention}: {query}\n\nResponse:")
            for chunk in safe_text_chunks:
                await interaction.channel.send(chunk)
            with open(QUERIES_FILE, mode = "a", newline="") as file:
                writer = csv.writer(file)
                writer.writerow([f'query: {query}', f'response: {safe_text}'])
        else: 
            chunks = [response.text[i:i+1900] for i in range(0, len(response.text), 1900)]
            await interaction.followup.send(f"Complete. Input tokens: {response.usage_metadata.prompt_token_count}, Output tokens: {response.usage_metadata.candidates_token_count}", ephemeral=True)
            await interaction.channel.send(f"Query from {interaction.user.mention}: {query}\n\nResponse:")
            for chunk in chunks:
                await interaction.channel.send(chunk)
            print(response.text)
            with open(QUERIES_FILE, mode = "a", newline="") as file:
                writer = csv.writer(file)
                writer.writerow([f'query: {query}', f'response: {response.text}'])
    except Exception as e:
        print(f"Helper command failed: {e}")
        traceback.print_exc()
        await interaction.followup.send(f"Error in response: {e}")
    return
@client.event
async def on_ready():
    await tree.sync()
    print(f"Logged in as {client.user}")
    global RECORDS_CHANNEL, NEWS_CHANNEL, SIGN_CHANNEL, CLERK_CHANNEL
    RECORDS_CHANNEL = client.get_channel(RECORDS_CHANNEL_ID)
    NEWS_CHANNEL = client.get_channel(NEWS_CHANNEL_ID)
    SIGN_CHANNEL = client.get_channel(SIGN_CHANNEL_ID)
    CLERK_CHANNEL = client.get_channel(CLERK_CHANNEL_ID)
    print(f"Clerk Channel: {CLERK_CHANNEL.name if CLERK_CHANNEL else 'Not Found'}")
    print(f"News Channel: {NEWS_CHANNEL.name if NEWS_CHANNEL else 'Not Found'}")
    print(f"Sign Channel: {SIGN_CHANNEL.name if SIGN_CHANNEL else 'Not Found'}")
    print(f"Records Channel: {RECORDS_CHANNEL.name if RECORDS_CHANNEL else 'Not Found'}")

@client.event
async def on_message(message):
    if message.channel == client.get_channel(CLERK_CHANNEL_ID) and not message.author.bot:
        await update_bill_reference(message)
    if message.channel == client.get_channel(NEWS_CHANNEL_ID):
        with open(NEWS_FILE, "a") as file:
            file.write(message.content)
    if message.channel == client.get_channel(SIGN_CHANNEL_ID) and "docs.google.com" in message.content:
        link = message.jump_url
        await RECORDS_CHANNEL.send(f'<@&1269061253964238919>, a new bill has been signed! {link}')
        
client.run(DISCORD_TOKEN)