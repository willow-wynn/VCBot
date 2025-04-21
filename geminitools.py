import os
import discord
import asyncio
from botcore import intents, client, tree
from dotenv import load_dotenv

load_dotenv()
KNOWLEDGE_FILES = os.getenv("KNOWLEDGE_FILES")
GUILD = client.get_guild(os.getenv("GUILD"))


call_local_files = {
    "name": "call_knowledge",
    "description": "calls a specific piece or pieces of information from your knowledge base.",
    "parameters": {
        "type": "object",
        "properties": {
            "file_to_call": {
                "type": "string",
                "enum": ["Rules", "Constitution", "Server Information"],
                "description": "which knowledge files to call",
            },
        },
        "required": ["file_to_call"]
    },
}
call_ctx_from_channel = {
    "name": "call_other_channel_context",
    "description": "calls information from another channel in the server",
    "parameters": {
        "type": "object",
        "properties": {
            "channel_to_call": {
                "type": "string",
                "enum": ["server-announcements", "twitter-rp", "official-rp-news", "virtual-congress-chat", "staff-announcements", "election-announcements", "house-floor", "senate-floor"],
                "description": "which channel to call information from."
            },
            "number_of_messages_called": {
                "type": "integer",
                "description": "how many messages to return from the channel in question. Maximum 50."
            },
            "search_query": {
                "type": "string",
                "description": "what specific information to search for in the channel. will only return information that directly matches the search query. leave blank unless user explicitly asks for query."
            },
        },
        "required": ["channel_to_call", "number_of_messages_called"]
    }
}

def call_knowledge(file_to_call):
    with open(KNOWLEDGE_FILES[file_to_call], "r") as file:
        return file.read()
async def call_other_channel_context(channel_name, number_of_messages_called, search_query=None):
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
