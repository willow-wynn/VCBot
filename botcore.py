import discord
from discord import app_commands
import os
intents = discord.Intents.all()
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)
KNOWLEDGE_FILES_RULES="/Knowledge/rules.txt"
KNOWLEDGE_FILES_CONSTITUTION="/Knowledge/constitution.txt"
KNOWLEDGE_FILES_SERVER_INFO="/Knowledge/rules.txt"
KNOWLEDGE_FILES_HOUSE_RULES = "/Knowledge/houserules.txt"
KNOWLEDGE_FILES_SENATE_RULES = "/Knowledge/senaterules.txt"
KNOWLEDGE_FILES = {
    "rules": KNOWLEDGE_FILES_RULES,
    "constitution": KNOWLEDGE_FILES_CONSTITUTION,
    "server_information": KNOWLEDGE_FILES_SERVER_INFO,
    "house_rules": KNOWLEDGE_FILES_HOUSE_RULES,
    "senate_rules": KNOWLEDGE_FILES_SENATE_RULES
}