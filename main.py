from google import genai 
from google.genai import types
import discord
from discord import app_commands
import aiohttp, re, asyncio, os, json, csv, traceback, datetime, requests
from dotenv import load_dotenv
from typing import Literal
from pathlib import Path
from botcore import intents, client, tree
from settings import settings, KNOWLEDGE_FILES, BILL_DIRECTORIES, MODEL_PATH, VECTOR_PKL, ALLOWED_ROLES_FOR_ROLES
import geminitools
from functools import wraps
from makeembeddings import embed_txt_file
from pydantic import BaseModel
from bot_state import BotState
from command_utils import (
    build_channel_context, sanitize, chunk_text, 
    send_ai_response, handle_command_error
)
from response_formatter import ResponseFormatter
from error_handler import handle_errors, mark_uses_network, mark_uses_ai
import tools  # Import tools to register them with the registry
from registry import registry
from exceptions import (
    VCBotError, ConfigurationError, BillProcessingError, AIServiceError,
    PermissionError as VCBotPermissionError, ToolExecutionError, DiscordAPIError,
    RateLimitError, ParseError, NetworkError, TimeoutError as VCBotTimeoutError
)
from logging_config import setup_logging, logger
from constants import Roles, Limits, Messages

# Pydantic models moved to services

 # ---------- tool dispatch (generic) ----------
def create_tools(discord_client):
    """Factory function to create tools with client in closure"""
    
    def _tool_call_knowledge(**kw):
        return geminitools.call_knowledge(kw["file_to_call"])

    async def _tool_call_other_channel_context(**kw):
        raw = await geminitools.call_other_channel_context(
            kw["channel_to_call"],
            kw["number_of_messages_called"],
            kw.get("search_query"),
            client=discord_client  # Pass the client from closure
        )
        return "\n".join(f"{m.author}: {m.content}" for m in raw)

    def _tool_call_bill_search(**kw):
        return geminitools.search_bills(
            kw["query"],
            kw["top_k"]
        )

    return {
        "call_knowledge": _tool_call_knowledge,
        "call_other_channel_context": _tool_call_other_channel_context,
        "call_bill_search": _tool_call_bill_search,
    }

# Tool functions will be stored in bot_state
# Sanitize function moved to command_utils
# Bill management functions moved to BillService

# Initialize bot state (will be fully configured in on_ready)
logger.info("Loading configuration from settings module...")
bot_state = None  # Will be initialized in on_ready

def has_any_role(*role_names):
    def decorator(func):
        @wraps(func)
        async def wrapper(interaction: discord.Interaction, *args, **kwargs):
            logger.debug(f"Checking roles for {interaction.user.display_name}: {[role.name for role in interaction.user.roles]}")
            if not any(role.name in role_names for role in interaction.user.roles):
                await interaction.response.send_message(Messages.PERMISSION_DENIED_AI_ACCESS, ephemeral=True)
                return
            return await func(interaction, *args, **kwargs)
        return wrapper
    return decorator

def limit_to_channels(channel_ids: list, exempt_roles=[Roles.ADMIN]):
    def decorator(func):
        @wraps(func)
        async def wrapper(interaction: discord.Interaction, *args, **kwargs):
            logger.debug(f"Checking if {interaction.user.display_name} can use command in {interaction.channel.id}")
            if exempt_roles and any(role.name in exempt_roles for role in interaction.user.roles):
                return await func(interaction, *args, **kwargs)
            if interaction.channel.id not in channel_ids:
                await interaction.response.send_message(Messages.CHANNEL_RESTRICTED, ephemeral=True)
                return
            return await func(interaction, *args, **kwargs)
        return wrapper
    return decorator

@tree.command(name="role", description="Add a role to one or more users.")
@handle_errors("Failed to manage roles")
async def role(interaction: discord.Interaction, users: str, *, role: str):
    """add or remove `role` for arbitrary many members.  
    usage: /role @member1 @member2 ... SomeRole   (prefix role with '-' to remove)"""
    remove = role[0] == "-"
    clean_role = role.removeprefix("-")

    # permission check – which roles is the invoker allowed to (un)assign?
    allowed_roles: list[str] = []
    for r in interaction.user.roles:
        if r.name in ALLOWED_ROLES_FOR_ROLES:
            allowed_roles.extend(ALLOWED_ROLES_FOR_ROLES[r.name])

    if clean_role not in allowed_roles:
        raise VCBotPermissionError(f"You do not have permission to add the role '{clean_role}'.")

    target_role = discord.utils.get(interaction.guild.roles, name=clean_role)
    if not target_role:
        raise ValueError(f"Role '{clean_role}' not found in this server.")

    # accept space/comma‑separated mentions or raw user ids
    user_ids = re.findall(r"\d+", users)
    if not user_ids:
        raise ValueError("No valid users specified. Please mention users or provide user IDs.")

    # dedupe while preserving order
    members: list[discord.Member] = []
    for uid in dict.fromkeys(user_ids):
        member = interaction.guild.get_member(int(uid))
        if member:
            members.append(member)

    if not members:
        raise ValueError("Couldn't resolve any members from the provided user IDs.")

    try:
        for m in members:
            if remove:
                await m.remove_roles(target_role)
            else:
                await m.add_roles(target_role)
    except discord.Forbidden:
        raise DiscordAPIError("Bot lacks permission to manage roles. Please check bot role hierarchy.")
    except discord.HTTPException as e:
        raise DiscordAPIError(f"Discord API error: {str(e)}")

    mentions = ", ".join(m.mention for m in members)
    await interaction.response.send_message(
        f"{'Removed' if remove else 'Added'} role {clean_role} "
        f"{'from' if remove else 'to'} {mentions}.",
        ephemeral=False,
    )


# Reference management functions moved to ReferenceService

async def update_bill_reference(message, bot_state: BotState):
    """Process message to update bill references using bill service."""
    logger.debug(f"Processing message for bill reference: {message.content}")
    
    if not bot_state.bill_service or not bot_state.reference_service:
        logger.warning("Services not initialized yet")
        return "Services not initialized"
    
    # Use bill service to detect reference
    ref_update = await bot_state.bill_service.update_reference(message.content)
    
    if ref_update.success and ref_update.bill_type and ref_update.reference_number:
        # Update the reference number
        updated_num = bot_state.reference_service.update_reference(
            ref_update.bill_type,
            ref_update.reference_number
        )
        logger.info(f"Updated {ref_update.bill_type.upper()} to {updated_num}")
        return f"Updated {ref_update.bill_type.upper()} to {updated_num}"
    
    return ref_update.message

@tree.command(name="reference", description="reference a bill")
@has_any_role(Roles.ADMIN, Roles.REPRESENTATIVE, Roles.HOUSE_CLERK, Roles.MODERATOR)
@handle_errors("Failed to reference bill")
async def reference(interaction: discord.Interaction, link: str, type: Literal["hr", "hres", "hjres", "hconres"]):
    """Thin handler - delegates to reference service."""
    logger.info(f"Executing command: reference by {interaction.user.display_name}")
    
    # Get reference service
    reference_service = interaction.client.bot_state.reference_service
    
    if not reference_service:
        raise ConfigurationError("Reference service not initialized yet.")
    
    # Get next reference number
    next_val = reference_service.get_next_reference(type)
    
    # Send success message
    await interaction.response.send_message(
        f"The bill {link} has been referenced successfully as {type.upper()} {next_val}.",
        ephemeral=True
    )
    
    # Announce in clerk channel
    clerk_channel = client.get_channel(settings.channels.clerk_announce_channel)
    if clerk_channel:
        await clerk_channel.send(f'Bill {link} assigned reference {type.upper()} {next_val}')
@tree.command(name="modifyrefs", description="modify reference numbers")
@has_any_role(Roles.ADMIN, Roles.HOUSE_CLERK)
@handle_errors("Failed to modify reference")
async def modifyref(interaction: discord.Interaction, num: int, type: str):
    """Thin handler - delegates to reference service."""
    logger.info(f"Executing command: modifyref by {interaction.user.display_name}")
    
    # Get reference service
    reference_service = interaction.client.bot_state.reference_service
    
    if not reference_service:
        raise ConfigurationError("Reference service not initialized yet.")
    
    # Set reference number
    reference_service.set_reference(type, num)
    
    # Send success message
    await interaction.response.send_message(
        f"Reference number modified for {type.upper()}: {num}",
        ephemeral=False
    )


@tree.command(name="helper", description="Query the VCBot helper.")
@has_any_role(Roles.ADMIN, Roles.AI_ACCESS)
@limit_to_channels([settings.channels.bot_helper_channel])
@handle_errors("Failed to process query")
@mark_uses_ai
async def helper(interaction: discord.Interaction, query: str):
    """Thin handler - delegates to AI service."""
    logger.info(f"Executing command: helper by {interaction.user.display_name}")
    await interaction.response.defer(ephemeral=False)
    
    # Get bot state and AI service
    bot_state = interaction.client.bot_state
    ai_service = bot_state.ai_service
    
    if not ai_service:
        raise ConfigurationError("AI service not initialized yet.")
    
    # Build context
    context = await build_channel_context(
        interaction.channel, 
        bot_state.bot_id,
        limit=Limits.MAX_MESSAGES_HISTORY
    )
    
    # Add current query to context
    context.append(types.Content(
        role='user', 
        parts=[types.Part.from_text(text=f"{interaction.user.display_name}: {query}")]
    ))
    
    # Process query through AI service
    ai_response = await ai_service.process_query(
        query=query,
        context=context,
        user_id=interaction.user.id
    )
    
    # Send response
    await send_ai_response(interaction, ai_response, query)
    
    # Log query
    await ai_service.save_query_log(
        query=query,
        response=ai_response.text,
        file_path=bot_state.queries_file
    )
@tree.command(name="econ_impact_report", description="Get a detailed economic impact report on a given piece of legislation.")
@has_any_role(Roles.ADMIN, Roles.EVENTS_TEAM)
@limit_to_channels([settings.channels.bot_helper_channel])
@handle_errors("Failed to generate economic impact report")
@mark_uses_ai
@mark_uses_network
async def model_economic_impact(interaction: discord.Interaction, bill_link: str, additional_context: str = None):
    """Thin handler - delegates to bill service for economic impact generation."""
    logger.info(f"Executing command: econ_impact_report by {interaction.user.display_name}")
    await interaction.response.defer(ephemeral=False)
    
    # Get bot state and bill service
    bot_state = interaction.client.bot_state
    bill_service = bot_state.bill_service
    
    if not bill_service:
        raise ConfigurationError("Bill service not initialized yet.")
    
    # Get recent news
    news_channel = bot_state.get_channel('news')
    recent_news = []
    if news_channel:
        recent_news = [msg.content async for msg in news_channel.history(limit=Limits.MAX_MESSAGES_HISTORY) if msg.content.strip()]
    
    # Generate economic impact report
    report_text = await bill_service.generate_economic_impact(
        bill_link=bill_link,
        recent_news=recent_news,
        additional_context=additional_context
    )
    
    # Format and send using ResponseFormatter
    formatted = ResponseFormatter.format_response(
        report_text, 
        force_file=True,  # Economic reports should always be files
        filename="econ_impact_report.txt"
    )
    
    query_header = (
        f"Query from {interaction.user.mention}: Generate economic impact report on {bill_link}.\n\n"
        f"Response:"
    )
    
    await ResponseFormatter.send_response(
        interaction,
        formatted,
        completion_message="Complete. Economic impact report generated.",
        query_header=query_header
    )
    
    # Log query
    with open(bot_state.queries_file, mode="a", newline="") as file:
        writer = csv.writer(file)
        writer.writerow([f'query: Generate economic impact report on {bill_link}', f'response: {report_text}'])
@tree.command(name="bill_keyword_search", description="Perform a basic keyword search on the legislative corpus.")
@has_any_role(Roles.ADMIN, Roles.AI_ACCESS)
@limit_to_channels([settings.channels.bot_helper_channel])
@handle_errors("Failed to search bills")
async def bill_keyword_search(interaction: discord.Interaction, search_query: str):
    """Perform a basic keyword search on the legislative corpus."""
    await interaction.response.defer(ephemeral=False)
    
    returned_bills = geminitools.bill_keyword_search(search_query)
    
    # Send completion message first
    completion_message = f"Complete. Found {len(returned_bills)} bills matching your query."
    await interaction.followup.send(completion_message, ephemeral=True)
    
    # Send header
    query_header = f"Query from {interaction.user.mention}: Search bills for '{search_query}'\n\nResults:"
    safe_header, _ = ResponseFormatter.sanitize(query_header)
    await interaction.channel.send(safe_header)
    
    # Send each bill file
    for _, row in returned_bills.iterrows():
        name = row["filename"]
        content = row["text"]
        pdf_path = Path(BILL_DIRECTORIES["billpdfs"]) / name
        await interaction.channel.send(file=discord.File(pdf_path))
        # Note: This os.remove(name) looks incorrect - it removes 'name' instead of the actual file path
        # Consider using the FileManager if cleanup is needed



@tree.command(name="add_bill", description="Add a bill to the legislative corpus.")
@has_any_role(Roles.ADMIN)
@limit_to_channels([settings.channels.bot_helper_channel])
@handle_errors("Failed to add bill")
@mark_uses_network
@mark_uses_ai
async def add_bill(interaction: discord.Interaction, bill_link: str, database_type: Literal["bills"] = "bills"):
    """Thin handler - delegates to bill service."""
    logger.info(f"Executing command: add_bill by {interaction.user.display_name}")
    await interaction.response.defer(ephemeral=False)
    
    # Get bill service
    bill_service = interaction.client.bot_state.bill_service
    
    if not bill_service:
        raise ConfigurationError("Bill service not initialized yet.")
    
    # Add bill to database
    result = await bill_service.add_bill(bill_link, database_type)
    
    if result.success:
        # Send the bill file
        await interaction.channel.send(file=discord.File(result.file_path))
        await interaction.followup.send(
            f"Complete. Added bill `{result.bill_name}` to `{database_type}` database.",
            ephemeral=True
        )
    else:
        raise BillProcessingError(f"Failed to add bill: {result.error}")

async def check_github_commits():
    await client.wait_until_ready()
    channel = client.get_channel(settings.channels.bot_helper_channel)
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
                logger.error(f"GitHub check failed: {e}", exc_info=True)
            await asyncio.sleep(60)  # check every 5 min
@client.event
async def on_ready():
    logger.info("Starting up bot...")
    logger.info(f"Logged in as {client.user}")
    global bot_state
    
    # Initialize bot state from settings
    bot_state = BotState.from_settings(client, settings)
    
    # Set up Discord client in registry for tools that need it
    registry.set_discord_client(client)
    
    # Set up Gemini tools using the new registry system
    tool_declarations = registry.get_gemini_declarations()
    bot_state.set_tools(types.Tool(function_declarations=tool_declarations))
    logger.info(f"Initialized {len(tool_declarations)} tools from registry")
    
    # Initialize tool functions with the client (for backward compatibility)
    bot_state.set_tool_functions(create_tools(client))
    logger.info("Initialized tool system with Discord client")
    
    # Initialize Discord channels
    bot_state.initialize_channels()
    
    # Initialize services
    bot_state.initialize_services(BILL_DIRECTORIES, VECTOR_PKL)
    logger.info("Initialized services")
    
    # Initialize message router
    bot_state.initialize_message_router()
    logger.info("Initialized message router")
    
    # Attach bot_state to client for easy access in commands
    client.bot_state = bot_state
    
    client.loop.create_task(check_github_commits())
    logger.info("Syncing commands...")
    synced_commands = await tree.sync()
    logger.info(f"Commands synced: {len(synced_commands)} commands" if synced_commands else "No commands to sync.")

@client.event
async def on_message(message):
    """Route messages to appropriate handlers using MessageRouter"""
    try:
        # Get bot state
        state = client.bot_state
        
        if state and state.message_router:
            await state.message_router.route(message, state)
        else:
            logger.warning("Bot state or message router not initialized")
            
    except Exception as e:
        logger.exception(f"Critical error in on_message handler: {e}")
        # Don't re-raise to prevent bot from crashing
        
def main():
    """Main entry point"""
    # Setup logging
    setup_logging(
        console_level="INFO",
        logs_dir=Path("logs")
    )
    
    logger.info("Starting VCBot...")
    
    # Run bot
    client.run(settings.discord_token)

if __name__ == "__main__":
    main()