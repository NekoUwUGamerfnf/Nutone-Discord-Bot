import os
import json
from discord import app_commands
from discord.ext import commands, tasks
import discord
import requests
import random
import asyncio
from dotenv import load_dotenv

NUTONE_WEBSITE = "https://nutone.okudai.dev/v1"

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.guild_messages = True
intents.members = True

client = commands.Bot(command_prefix="", intents=intents)
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
BOTOWNER = os.getenv("BOT_OWNER", "402550402140340224")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LINKED_USERNAMES_PATH = os.path.join(BASE_DIR, "linked_usernames.json")
SERVER_IDS_PATH = os.path.join(BASE_DIR, "server_ids.json")
LINKED_UIDS_PATH = os.path.join(BASE_DIR, "linked_uids.json")
VALID_USERNAMES_PATH = os.path.join(BASE_DIR, "valid_usernames.json")
HIDDEN_PATH = os.path.join(BASE_DIR, "hidden.json")

linked_usernames = {}
server_ids = {}
linked_uids = {}
valid_usernames = {}
hidden_status = []

def load_data():
    global linked_usernames, server_ids, linked_uids, valid_usernames, hidden_status
    if os.path.exists(LINKED_USERNAMES_PATH):
        with open(LINKED_USERNAMES_PATH, 'r') as f:
            linked_usernames.update(json.load(f))
    if os.path.exists(SERVER_IDS_PATH):
        with open(SERVER_IDS_PATH, 'r') as f:
            server_ids.update(json.load(f))
    if os.path.exists(LINKED_UIDS_PATH):
        with open(LINKED_UIDS_PATH, 'r') as f:
            linked_uids.update(json.load(f))
    if os.path.exists(VALID_USERNAMES_PATH):
        with open(VALID_USERNAMES_PATH, 'r') as f:
            valid_usernames.update(json.load(f))
    if os.path.exists(HIDDEN_PATH):
        with open(HIDDEN_PATH, 'r') as f:
            data = json.load(f)
            if isinstance(data, dict):
                hidden_status = [guild_id for guild_id, is_hidden in data.items() if not is_hidden]
            else:
                hidden_status = data


def save_data():
    with open(LINKED_USERNAMES_PATH, 'w') as f:
        json.dump(linked_usernames, f)
    with open(SERVER_IDS_PATH, 'w') as f:
        json.dump(server_ids, f)
    with open(LINKED_UIDS_PATH, 'w') as f:
        json.dump(linked_uids, f)
    with open(VALID_USERNAMES_PATH, 'w') as f:
        json.dump(valid_usernames, f)
    with open(HIDDEN_PATH, 'w') as f:
        json.dump(hidden_status, f)

@client.event
async def on_message(message):
    return

@client.event
async def on_ready():
    print(f'Bot Is Ready Logged In As {client.user}')
    load_data()
    
    current_guild_ids = {str(guild.id) for guild in client.guilds}
    guilds_to_remove = [guild_id for guild_id in server_ids.keys() if guild_id not in current_guild_ids]
    hidden_to_remove = [guild_id for guild_id in hidden_status if guild_id not in current_guild_ids]
    
    for guild_id in guilds_to_remove:
        del server_ids[guild_id]
    
    for guild_id in hidden_to_remove:
        hidden_status.remove(guild_id)
    
    if guilds_to_remove or hidden_to_remove:
        save_data()
        total_removed = len(set(guilds_to_remove + hidden_to_remove))
        print(f'Cleaned Up Server Data For {total_removed} Guilds The Bot Is No Longer In')
    
    await client.tree.sync()
    update_status.start()

status_index = 0
statuses = [
    lambda total_members, total_guilds: discord.Game(name=f"I'm In {total_guilds} Discord Servers"),
    lambda total_members, total_guilds: discord.Game(name="Okudai Is Very Cool"),
    lambda total_members, total_guilds: discord.Game(name=f"Check Player Stats On {NUTONE_WEBSITE}")
]

@tasks.loop(minutes=1)
async def update_status():
    global status_index
    total_guilds = len(client.guilds)
    unique_members = set()
    for guild in client.guilds:
        for member in guild.members:
            unique_members.add(member.id)
    total_members = len(unique_members)
    
    status = statuses[status_index](total_members, total_guilds)
    await client.change_presence(activity=status)
    
    status_index = (status_index + 1) % len(statuses)

@client.event
async def on_guild_join(guild):
    guild_id = str(guild.id)
    save_data()

@client.event
async def on_guild_remove(guild):
    guild_id = str(guild.id)
    if guild_id in hidden_status:
        hidden_status.remove(guild_id)
    if guild_id in server_ids:
        del server_ids[guild_id]
    save_data()

@client.event
async def on_command_error(ctx, error):
    await ctx.send(f'An Error Has Occurred: {error}', ephemeral=True)

def is_nutone_contributor(ctx):
    if str(ctx.user.id) == 477779764627767297:
        return True
    if str(ctx.user.id) == 581483164103606292:
        return True
    if str(ctx.user.id) == 402550402140340224:
        return True
    if str(ctx.user.id) == BOTOWNER:
        return True
    return False

def is_admin(ctx):
    if ctx.guild.owner_id == ctx.user.id:
        return True
    if ctx.user.guild_permissions.administrator:
        return True
    if is_nutone_contributor:
        return True
    return False

async def fetch_stats(interaction, player, server_id, ephemeral):
    if server_id == "All":
        url = f'{NUTONE_WEBSITE}/players/{player}'
    else:
        url = f'{NUTONE_WEBSITE}/players/{player}?server_id={server_id}'

    try:
        r = await asyncio.wait_for(asyncio.to_thread(requests.get, url), timeout=10.0)
        r.raise_for_status()
    except asyncio.TimeoutError:
        await interaction.followup.send(f"Request Timed Out While Fetching Stats For Server ID: {server_id}", ephemeral=ephemeral)
        return None
    except requests.exceptions.HTTPError as e:
        if r.status_code == 404:
            await interaction.followup.send(f"No Stats Found For Player: {player} On Server: {server_id}", ephemeral=ephemeral)
        else:
            await interaction.followup.send(f"An Error Has Occurred: {e}", ephemeral=ephemeral)
        return None
    except requests.exceptions.RequestException as e:
        await interaction.followup.send(f"An Error Has Occurred: {e}", ephemeral=ephemeral)
        return None

    try:
        data = r.json()
    except ValueError:
        await interaction.followup.send("Error: Received Invalid JSON Response", ephemeral=ephemeral)
        return None

    uid = data.get('uid')
    if uid:
        valid_usernames[player] = True
        linked_uids[player] = uid
        save_data()

    return data

async def fetch_uid(interaction, player, ephemeral):
    url = f'{NUTONE_WEBSITE}/players/{player}'
    try:
        r = await asyncio.wait_for(asyncio.to_thread(requests.get, url), timeout=10.0)
        r.raise_for_status()
    except asyncio.TimeoutError:
        await interaction.followup.send("Request Timed Out While Fetching Uid", ephemeral=ephemeral)
        return 'N/A'
    except requests.exceptions.HTTPError:
        return 'N/A'
    except requests.exceptions.RequestException as e:
        await interaction.followup.send(f"An Error Has Occurred: {e}", ephemeral=ephemeral)
        return 'N/A'

    try:
        data = r.json()
    except ValueError:
        await interaction.followup.send("Error: Received Invalid JSON Response", ephemeral=ephemeral)
        return 'N/A'

    uid = data.get('uid', 'N/A')
    return uid

async def fetch_aliases(interaction, player, ephemeral):
    url = f'{NUTONE_WEBSITE}/players/{player}'
    try:
        r = await asyncio.wait_for(asyncio.to_thread(requests.get, url), timeout=10.0)
        r.raise_for_status()
    except asyncio.TimeoutError:
        await interaction.followup.send("Request Timed Out While Fetching Aliases", ephemeral=ephemeral)
        return None, None
    except requests.exceptions.HTTPError as e:
        if r.status_code == 404:
            await interaction.followup.send(f"No Data Found For Player: {player}", ephemeral=ephemeral)
        else:
            await interaction.followup.send(f"An Error Has Occurred: {e}", ephemeral=ephemeral)
        return None, None
    except requests.exceptions.RequestException as e:
        await interaction.followup.send(f"An Error Has Occurred: {e}", ephemeral=ephemeral)
        return None, None

    try:
        data = r.json()
    except ValueError:
        await interaction.followup.send("Error: Received Invalid JSON Response", ephemeral=ephemeral)
        return None, None

    current_name = data.get('name', player)
    aliases = data.get('aliases', [])
    
    return current_name, aliases

@client.tree.command(name="stats", description="Search For A Player's Stats On All Servers Or By Server")
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
async def stats(interaction: discord.Interaction, player: str = None, server_id: str = None):
    ephemeral = str(interaction.guild.id) not in hidden_status if interaction.guild else True

    await interaction.response.defer(ephemeral=ephemeral)

    if player is None:
        discord_user = str(interaction.user.id)
        player = linked_usernames.get(discord_user)

    load_data()
    available_server_ids = server_ids.get(str(interaction.guild.id), []) + ["All"] if interaction.guild else ["All"]

    if server_id:
        data = await fetch_stats(interaction, player, server_id, ephemeral)
        if data:
            total_stats = data.get('total', {})
            kills = total_stats.get('kills', 'N/A')
            deaths = total_stats.get('deaths', 'N/A')
            kd_ratio = total_stats.get('kd', 'N/A')

            embed = discord.Embed(
                title=f"Stats for {player} on server {server_id}",
                color=discord.Color.blue()
            )
            embed.add_field(name="Kills", value=kills, inline=True)
            embed.add_field(name="Deaths", value=deaths, inline=True)
            embed.add_field(name="K/D Ratio", value=kd_ratio, inline=True)

            await interaction.followup.send(embed=embed, ephemeral=ephemeral)
    else:
        for sid in available_server_ids:
            data = await fetch_stats(interaction, player, sid, ephemeral)
            if data:
                total_stats = data.get('total', {})
                kills = total_stats.get('kills', 'N/A')
                deaths = total_stats.get('deaths', 'N/A')
                kd_ratio = total_stats.get('kd', 'N/A')

                embed = discord.Embed(
                    title=f"Stats for {player} on server {sid}",
                    color=discord.Color.blue()
                )
                embed.add_field(name="Kills", value=kills, inline=True)
                embed.add_field(name="Deaths", value=deaths, inline=True)
                embed.add_field(name="K/D Ratio", value=kd_ratio, inline=True)

                await interaction.followup.send(embed=embed, ephemeral=ephemeral)

@client.tree.command(name="kd", description="Get The K/D Ratio Of A Linked Username")
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
async def kd(interaction: discord.Interaction, player: str = None, server_id: str = None):
    ephemeral = str(interaction.guild.id) not in hidden_status if interaction.guild else True

    await interaction.response.defer(ephemeral=ephemeral)

    if player is None:
        discord_user = str(interaction.user.id)
        player = linked_usernames.get(discord_user)

    load_data()
    available_server_ids = server_ids.get(str(interaction.guild.id), []) + ["All"] if interaction.guild else ["All"]

    if server_id:
        data = await fetch_stats(interaction, player, server_id, ephemeral)
        if data:
            total_stats = data.get('total', {})
            kd_ratio = total_stats.get('kd', 'N/A')

            embed = discord.Embed(
                title=f"K/D Ratio for {player} on server {server_id}",
                color=discord.Color.blue()
            )
            embed.add_field(name="K/D Ratio", value=kd_ratio, inline=True)

            await interaction.followup.send(embed=embed, ephemeral=ephemeral)
    else:
        for sid in available_server_ids:
            data = await fetch_stats(interaction, player, sid, ephemeral)
            if data:
                total_stats = data.get('total', {})
                kd_ratio = total_stats.get('kd', 'N/A')

                embed = discord.Embed(
                    title=f"K/D Ratio for {player} on server {sid}",
                    color=discord.Color.blue()
                )
                embed.add_field(name="K/D Ratio", value=kd_ratio, inline=True)

                await interaction.followup.send(embed=embed, ephemeral=ephemeral)

@client.tree.command(name="uid", description="Get The Uid Of A Linked Username")
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
async def uid(interaction: discord.Interaction, player: str = None):
    ephemeral = str(interaction.guild.id) not in hidden_status if interaction.guild else True

    await interaction.response.defer(ephemeral=ephemeral)

    if player is None:
        discord_user = str(interaction.user.id)
        player = linked_usernames.get(discord_user)

    if player in linked_uids:
        uid = linked_uids[player]
    else:
        uid = await fetch_uid(interaction, player, ephemeral)
        if uid != 'N/A':
            linked_uids[player] = uid
            save_data()

    await interaction.followup.send(f'Username: {player}\nUid: {uid}', ephemeral=ephemeral)

@client.tree.command(name="alias", description="Get The Aliases Of A Linked Username")
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
async def alias(interaction: discord.Interaction, player: str = None):
    ephemeral = str(interaction.guild.id) not in hidden_status if interaction.guild else True

    await interaction.response.defer(ephemeral=ephemeral)

    if player is None:
        discord_user = str(interaction.user.id)
        player = linked_usernames.get(discord_user)

    current_name, aliases = await fetch_aliases(interaction, player, ephemeral)
    
    if current_name is None:
        return

    embed = discord.Embed(
        title=f"Aliases for {current_name}",
        color=discord.Color.blue()
    )
    embed.add_field(name="Current Name", value=current_name, inline=False)
    
    if aliases and len(aliases) > 0:
        aliases_text = "\n".join(aliases)
        embed.add_field(name="Aliases", value=aliases_text, inline=False)
    else:
        embed.add_field(name="Aliases", value="No Aliases Found", inline=False)

    await interaction.followup.send(embed=embed, ephemeral=ephemeral)

@client.tree.command(name="link", description="Link A Username To Your Discord Account")
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
async def link(interaction: discord.Interaction, username: str):
    await interaction.response.defer(ephemeral=True)
    discord_user = str(interaction.user.id)
    ephemeral = str(interaction.guild.id) not in hidden_status if interaction.guild else True

    if username in valid_usernames:
        valid = True
        uid = linked_uids.get(username, 'N/A')
    else:
        url = f'{NUTONE_WEBSITE}/players/{username}'
        try:
            r = requests.get(url)
            r.raise_for_status()
            valid = True
        except requests.exceptions.HTTPError:
            valid = False
        except requests.exceptions.RequestException:
            await interaction.followup.send("An Error Has Occurred While Checking The Username Validity", ephemeral=ephemeral)
            return

        if valid:
            uid = await fetch_uid(interaction, username, ephemeral)
            if uid != 'N/A':
                linked_uids[username] = uid
            valid_usernames[username] = valid

    linked_usernames[discord_user] = username
    save_data()
    message = f'Username "{username}" Linked To Discord Account "{discord_user}"'
    if not valid:
        message += " However The Username Is Not Valid On Nutone"
    await interaction.followup.send(message, ephemeral=ephemeral)

@client.tree.command(name="unlink", description="Unlink The Linked Username From Your Discord Account")
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
async def unlink(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    discord_user = str(interaction.user.id)
    ephemeral = str(interaction.guild.id) not in hidden_status if interaction.guild else True

    if discord_user in linked_usernames:
        username = linked_usernames[discord_user]
        del linked_usernames[discord_user]
        if username in linked_uids:
            del linked_uids[username]
        save_data()
        await interaction.followup.send(f'Unlinked The Username "{username}" From Discord Account "{discord_user}"', ephemeral=ephemeral)
    else:
        await interaction.followup.send(f'No Username Is Linked To Your Discord Account "{discord_user}"', ephemeral=ephemeral)

@client.tree.command(name="forcelink", description="Forces Link Of A User")
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
async def forcelink(interaction: discord.Interaction, username: str, user: discord.User = None):
    if not is_nutone_contributor(interaction):
        ephemeral_value = str(interaction.guild.id) not in hidden_status if interaction.guild else True
        await interaction.response.send_message("You Do Not Have Permission To Use This Command", ephemeral=ephemeral_value)
        return

    await interaction.response.defer(ephemeral=True)
    discord_user = str(user.id)
    ephemeral = str(interaction.guild.id) not in hidden_status if interaction.guild else True

    if username in valid_usernames:
        valid = True
        uid = linked_uids.get(username, 'N/A')
    else:
        url = f'{NUTONE_WEBSITE}/players/{username}'
        try:
            r = requests.get(url)
            r.raise_for_status()
            valid = True
        except requests.exceptions.HTTPError:
            valid = False
        except requests.exceptions.RequestException:
            await interaction.followup.send("An Error Has Occurred While Checking The Username Validity", ephemeral=ephemeral)
            return

        if valid:
            uid = await fetch_uid(interaction, username, ephemeral)
            if uid != 'N/A':
                linked_uids[username] = uid
            valid_usernames[username] = valid

    linked_usernames[discord_user] = username
    save_data()
    message = f'Username "{username}" Linked To Discord Account "{discord_user}"'
    if not valid:
        message += " However The Username Is Not Valid On Nutone"
    await interaction.followup.send(message, ephemeral=ephemeral)

@client.tree.command(name="forceunlink", description="Forces Unlink Of A User")
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
async def forceunlink(interaction: discord.Interaction, user: discord.User = None):
    if not is_nutone_contributor(interaction):
        ephemeral_value = str(interaction.guild.id) not in hidden_status if interaction.guild else True
        await interaction.response.send_message("You Do Not Have Permission To Use This Command", ephemeral=ephemeral_value)
        return

    await interaction.response.defer(ephemeral=True)
    discord_user = str(user.id)
    ephemeral = str(interaction.guild.id) not in hidden_status if interaction.guild else True

    if discord_user in linked_usernames:
        username = linked_usernames[discord_user]
        del linked_usernames[discord_user]
        if username in linked_uids:
            del linked_uids[username]
        save_data()
        await interaction.followup.send(f'Unlinked The Username "{username}" From Discord Account "{discord_user}"', ephemeral=ephemeral)
    else:
        await interaction.followup.send(f'No Username Is Linked To Your Discord Account "{discord_user}"', ephemeral=ephemeral)

@client.tree.command(name="username", description="Show The Linked Username And Your Discord Account Username")
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
async def username(interaction: discord.Interaction, user: discord.User = None):
    ephemeral = str(interaction.guild.id) not in hidden_status if interaction.guild else True
    await interaction.response.defer(ephemeral=ephemeral)

    if user is None:
        discord_user = str(interaction.user.id)
    else:
        discord_user = str(user.id)

    username = linked_usernames.get(discord_user)
    if not username:
        if discord_user in valid_usernames:
            username = discord_user
        else:
            url = f'{NUTONE_WEBSITE}/players/{discord_user}'
            try:
                r = requests.get(url)
                r.raise_for_status()
                valid = True
            except requests.exceptions.HTTPError:
                valid = False
            except requests.exceptions.RequestException:
                await interaction.response.send_message("An Error Has Occurred While Checking The Username Validity", ephemeral=False)
                return

            if valid:
                valid_usernames[discord_user] = True
                username = discord_user
                save_data()
            else:
                username = "N/A"

    await interaction.followup.send(f'Discord Username: {discord_user}\nUsername: {username}', ephemeral=ephemeral)

@client.tree.command(name="roll", description="Roll A Number Between 1 And 100")
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
async def roll(interaction: discord.Interaction, number: int = None):
    ephemeral = str(interaction.guild.id) not in hidden_status if interaction.guild else True

    if number is None:
        max_number = 100
    else:
        if number < 1:
            await interaction.response.send_message("Number Must Be At Least 1", ephemeral=False)
            return
        max_number = number

    roll_result = random.randint(1, max_number)
    await interaction.response.send_message(f'You Rolled: {roll_result} (Max: {max_number})', ephemeral=ephemeral)

@client.tree.command(name="ping", description="Check The Bot's Latency")
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
async def ping(interaction: discord.Interaction):
    latency = client.latency
    ephemeral = str(interaction.guild.id) not in hidden_status if interaction.guild else True

    await interaction.response.send_message(f'Pong! Latency: {latency * 1000:.2f} ms', ephemeral=ephemeral)

@client.tree.command(name="help", description="Show The Help Message With Available Commands")
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
async def help(interaction: discord.Interaction):
    ephemeral = str(interaction.guild.id) not in hidden_status if interaction.guild else True
    embed = discord.Embed(
        title="Help - Available Commands",
        color=discord.Color.green()
    )
    embed.add_field(
        name="/stats [player] [server_id]",
        value="Search For A Player's Stats On All Servers Or By Server If No Player Is Specified It Will Use Your Linked Username Or Discord Username Optionally Specify A Server ID",
        inline=False
    )
    embed.add_field(
        name="/kd [player] [server_id]",
        value="Get The K/D Ratio Of A Linked Username If No Player Is Specified It Will Use Your Linked Username Or Discord Username Optionally Specify A Server ID",
        inline=False
    )
    embed.add_field(
        name="/uid [player]",
        value="Get The Uid Of A Linked Username On 'All' The Servers If No Player Is Specified It Will Use Your Linked Username Or Discord Username",
        inline=False
    )
    embed.add_field(
        name="/alias [player]",
        value="Get The Aliases Of A Linked Username If No Player Is Specified It Will Use Your Linked Username Or Discord Username",
        inline=False
    )
    embed.add_field(
        name="/roll [number]",
        value="Roll A Number Between 1 And 100",
        inline=False
    )
    embed.add_field(
        name="/ping",
        value="Check The Bot's Latency",
        inline=False
    )
    embed.add_field(
        name="/rps [choice]",
        value="Play Rock-Paper-Scissors Against The Bot Choose Rock Paper Or Scissors",
        inline=False
    )
    embed.add_field(
        name="/help",
        value="Show This Help Message With Available Commands",
        inline=False
    )
    embed.add_field(
        name="/link [username]",
        value="Link A Username To Your Discord Account",
        inline=False
    )
    embed.add_field(
        name="/unlink",
        value="Unlink The Linked Username From Your Discord Account",
        inline=False
    )
    embed.add_field(
        name="/forcelink [username]",
        value="Forces Link Of A User",
        inline=False
    )
    embed.add_field(
        name="/forceunlink",
        value="Forces Unlink Of A User",
        inline=False
    )
    embed.add_field(
        name="/username [user]",
        value="Show The Linked Username And Your Discord Account Username Optionally Specify A User To See Their Linked Username",
        inline=False
    )
    embed.add_field(
        name="/add_server_id [server_id]",
        value="Associate A Server-Specific ID With This Discord Server Only The Server Owner Can Use This Command",
        inline=False
    )
    embed.add_field(
        name="/remove_server_id [server_id]",
        value="Remove A Server-Specific ID From This Discord Server Only The Server Owner Can Use This Command",
        inline=False
    )
    embed.add_field(
        name="/server_id",
        value="Display The Current Server IDs Being Used Always Includes 'All'",
        inline=False
    )
    embed.add_field(
        name="/hidden",
        value="Hide The Bot's Messages From Everyone Only The Server Owner Can Use This Command",
        inline=False
    )
    embed.add_field(
        name="/unhidden",
        value="Unhide The Bot's Messages From Everyone Only The Server Owner Can Use This Command",
        inline=False
    )

    await interaction.response.send_message(embed=embed, ephemeral=ephemeral)

@client.tree.command(name="add_server_id", description="Associate A Server-Specific ID With This Discord Server")
async def add_server_id(interaction: discord.Interaction, server_id: str):
    if not interaction.guild:
        await interaction.response.send_message("This Command Can Only Be Used In A Server", ephemeral=True)
        return

    if interaction.guild not in client.guilds:
        await interaction.response.send_message("Bot Is Not In This Server", ephemeral=True)
        return

    if not is_admin(interaction):
        await interaction.response.send_message("You Do Not Have Permission To Use This Command", ephemeral=str(interaction.guild.id) not in hidden_status)
        return

    guild_id = str(interaction.guild.id)
    load_data()
    if guild_id not in server_ids:
        server_ids[guild_id] = []
    if server_id not in server_ids[guild_id]:
        server_ids[guild_id].append(server_id)
        save_data()
        await interaction.response.send_message(f'Server-Specific ID "{server_id}" Associated With This Discord Server', ephemeral=str(interaction.guild.id) not in hidden_status)
    else:
        await interaction.response.send_message(f'Server-Specific ID "{server_id}" Is Already Associated With This Discord Server', ephemeral=str(interaction.guild.id) not in hidden_status)

@client.tree.command(name="remove_server_id", description="Remove A Server-Specific ID From This Discord Server")
async def remove_server_id(interaction: discord.Interaction, server_id: str):
    if not interaction.guild:
        await interaction.response.send_message("This Command Can Only Be Used In A Server", ephemeral=True)
        return

    if interaction.guild not in client.guilds:
        await interaction.response.send_message("Bot Is Not In This Server", ephemeral=True)
        return
    
    if not is_admin(interaction):
        await interaction.response.send_message("You Do Not Have Permission To Use This Command", ephemeral=str(interaction.guild.id) not in hidden_status)
        return

    guild_id = str(interaction.guild.id)
    load_data()
    if guild_id in server_ids and server_id in server_ids[guild_id]:
        server_ids[guild_id].remove(server_id)
        save_data()
        await interaction.response.send_message(f'Server-Specific ID "{server_id}" Removed From This Discord Server', ephemeral=str(interaction.guild.id) not in hidden_status)
    else:
        await interaction.response.send_message(f'Server-Specific ID "{server_id}" Is Not Associated With This Discord Server', ephemeral=str(interaction.guild.id) not in hidden_status)

@client.tree.command(name="server_id", description="Display The Current Server IDs Being Used")
async def server_id(interaction: discord.Interaction):
    if not interaction.guild:
        await interaction.response.send_message("This Command Can Only Be Used In A Server", ephemeral=True)
        return

    guild_id = str(interaction.guild.id)
    load_data()
    ids = server_ids.get(guild_id, []) + ["All"]
    await interaction.response.send_message(f'The Current Server IDs Being Used Are: {", ".join(ids)}', ephemeral=guild_id not in hidden_status)

@client.tree.command(name="rps", description="Play Rock-Paper-Scissors Against The Bot")
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
async def rps(interaction: discord.Interaction, choice: str):
    ephemeral = str(interaction.guild.id) not in hidden_status if interaction.guild else True

    choices = ["rock", "paper", "scissors"]
    if choice.lower() not in choices:
        await interaction.response.send_message("Invalid Choice Please Choose Rock Paper Or Scissors", ephemeral=ephemeral)
        return

    bot_choice = random.choice(choices)
    result = ""
    if choice == bot_choice:
        result = "It's A Tie!"
    elif (choice == "rock" and bot_choice == "scissors") or \
            (choice == "scissors" and bot_choice == "paper") or \
            (choice == "paper" and bot_choice == "rock"):
        result = "You Win!"
    else:
        result = "You Lose!"

    embed = discord.Embed(
        title="Rock-Paper-Scissors",
        color=discord.Color.blue()
    )
    embed.add_field(name="Your Choice", value=choice, inline=True)
    embed.add_field(name="Bot's Choice", value=bot_choice, inline=True)
    embed.add_field(name="Result", value=result, inline=True)

    await interaction.response.send_message(embed=embed, ephemeral=ephemeral)

@client.tree.command(name="hidden", description="Hide The Bot's Messages From Everyone")
async def hidden(interaction: discord.Interaction):
    if not interaction.guild:
        await interaction.response.send_message("This Command Can Only Be Used In A Server", ephemeral=True)
        return

    if interaction.guild not in client.guilds:
        await interaction.response.send_message("Bot Is Not In This Server", ephemeral=True)
        return

    if not is_admin(interaction):
        await interaction.response.send_message("You Do Not Have Permission To Use This Command", ephemeral=True)
        return

    guild_id = str(interaction.guild.id)
    if guild_id in hidden_status:
        hidden_status.remove(guild_id)
        save_data()
        await interaction.response.send_message("Bot Messages Are Now Hidden From Everyone", ephemeral=True)
    else:
        await interaction.response.send_message("Bot Messages Are Already Hidden From Everyone", ephemeral=True)

@client.tree.command(name="unhidden", description="Unhide The Bot's Messages From Everyone")
async def unhidden(interaction: discord.Interaction):
    if not interaction.guild:
        await interaction.response.send_message("This Command Can Only Be Used In A Server", ephemeral=True)
        return

    if interaction.guild not in client.guilds:
        await interaction.response.send_message("Bot Is Not In This Server", ephemeral=True)
        return

    if not is_admin(interaction):
        await interaction.response.send_message("You Do Not Have Permission To Use This Command", ephemeral=True)
        return

    guild_id = str(interaction.guild.id)
    if guild_id not in hidden_status:
        hidden_status.append(guild_id)
        save_data()
        await interaction.response.send_message("Bot Messages Are Now Visible To Everyone", ephemeral=True)
    else:
        await interaction.response.send_message("Bot Messages Are Already Visible To Everyone", ephemeral=True)

@client.tree.command(name="uiduser", description="Get The Uid Of A Specific Discord User")
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
async def uiduser(interaction: discord.Interaction, user: discord.User):
    ephemeral = str(interaction.guild.id) not in hidden_status if interaction.guild else True

    await interaction.response.defer(ephemeral=ephemeral)

    discord_user = str(user.id)
    player = linked_usernames.get(discord_user)

    if player in linked_uids:
        uid = linked_uids[player]
    else:
        uid = await fetch_uid(interaction, player, ephemeral)
        if uid != 'N/A':
            linked_uids[player] = uid
            save_data()

    await interaction.followup.send(f'Discord User: {discord_user}\nUsername: {player}\nUid: {uid}', ephemeral=ephemeral)

@client.tree.command(name="kduser", description="Get The K/D Ratio Of A Specific Discord User")
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
async def kduser(interaction: discord.Interaction, user: discord.User, server_id: str = None):
    ephemeral = str(interaction.guild.id) not in hidden_status if interaction.guild else True

    await interaction.response.defer(ephemeral=ephemeral)

    discord_user = str(user.id)
    player = linked_usernames.get(discord_user)

    load_data()
    available_server_ids = server_ids.get(str(interaction.guild.id), []) + ["All"] if interaction.guild else ["All"]

    if server_id:
        data = await fetch_stats(interaction, player, server_id, ephemeral)
        if data:
            total_stats = data.get('total', {})
            kd_ratio = total_stats.get('kd', 'N/A')

            embed = discord.Embed(
                title=f"K/D Ratio for {player} on server {server_id}",
                color=discord.Color.blue()
            )
            embed.add_field(name="K/D Ratio", value=kd_ratio, inline=True)

            await interaction.followup.send(embed=embed, ephemeral=ephemeral)
    else:
        for sid in available_server_ids:
            data = await fetch_stats(interaction, player, sid, ephemeral)
            if data:
                total_stats = data.get('total', {})
                kd_ratio = total_stats.get('kd', 'N/A')

                embed = discord.Embed(
                    title=f"K/D Ratio for {player} on server {sid}",
                    color=discord.Color.blue()
                )
                embed.add_field(name="K/D Ratio", value=kd_ratio, inline=True)

                await interaction.followup.send(embed=embed, ephemeral=ephemeral)


client.remove_command('help')

client.run(TOKEN)