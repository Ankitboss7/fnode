# v2.py — All-in-one Discord bot for Pterodactyl (prefix "*")
# Requirements:
#   pip install discord.py aiohttp
# Edit CONFIG below before running.

import os
import json
import asyncio
import datetime
from typing import Dict, Any, Optional, List, Tuple
import aiohttp
import discord
from discord.ext import commands

# =========================
# CONFIG (EDIT THESE)
# =========================
BOT_TOKEN = ""
PANEL_URL = "https://panel.fluidmc.fun"  # no trailing slash
PANEL_API_KEY = "ptla_S47faeE3JcTChMKRllMz6ekGiJQKXQ4jkoXm0Wd550M"
API_KEY = "ptla_S47faeE3JcTChMKRllMz6ekGiJQKXQ4jkoXm0Wd550M"
APP_API_KEY = "ptla_S47faeE3JcTChMKRllMz6ekGiJQKXQ4jkoXm0Wd550M"
ADMIN_IDS = "1405866008127864852"
PANEL_NODE_ID = "2"  # node id to select allocations
DEFAULT_ALLOCATION_ID = "None"
# initial admin bootstrap (replace with your Discord ID)
BOOTSTRAP_ADMIN_IDS = {1405866008127864852}

# bot branding
BOT_VERSION = "27.6v"
MADE_BY = "Gamerzhacker"
SERVER_LOCATION = "India"

# data file
DATA_FILE = "v2_data.json"

# prefix and intents
PREFIX = "*"
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix=PREFIX, intents=intents, help_command=None)

# =========================
# persistence utilities
# =========================
def load_data() -> Dict[str, Any]:
    if not os.path.exists(DATA_FILE):
        return {
            "admins": [str(i) for i in BOOTSTRAP_ADMIN_IDS],
            "invites": {},        # user_id -> int
            "client_keys": {},    # user_id -> client api key
            "panel_users": {},    # discord_user_id -> panel_user_id
            "locked_channels": [] # list of channel ids (strings)
        }
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_data(d: Dict[str, Any]) -> None:
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(d, f, indent=2)

data = load_data()

# =========================
# Application API helper
# =========================
APP_HEADERS = {
    "Authorization": f"Bearer {PANEL_API_KEY}",
    "Content-Type": "application/json",
    "Accept": "application/vnd.pterodactyl.v1+json",
}

def app_url(path: str) -> str:
    # path must start with '/'
    return f"{PANEL_URL}/api/application{path}"

async def request_app(method: str, path: str, json_payload: dict = None, params: dict = None, timeout: int = 30) -> Tuple[int, Optional[dict], str]:
    url = app_url(path)
    async with aiohttp.ClientSession() as session:
        try:
            async with session.request(method, url, headers=APP_HEADERS, json=json_payload, params=params, timeout=timeout) as resp:
                text = await resp.text()
                try:
                    js = await resp.json()
                except Exception:
                    js = None
                return resp.status, js, text
        except Exception as e:
            return 0, None, f"request-exception: {e}"

# =========================
# EGG CATALOG and defaults
# =========================
DEFAULT_ENV = {
    "SERVER_JARFILE": "server.jar",
    "EULA": "TRUE",
    "VERSION": "latest",
    "BUILD_NUMBER": "latest",
    "SPONGE_VERSION": "stable-7",
    "FORGE_VERSION": "latest",
    "MINECRAFT_VERSION": "latest",
    "BUNGEE_VERSION": "latest",
}

EGG_CATALOG: Dict[str, Dict[str, Any]] = {
    "paper": {
        "display": "Minecraft: Paper",
        "nest_id": 1,
        "egg_id": 3,  # your Paper egg
        "docker_image": "ghcr.io/pterodactyl/yolks:java_21",
        "startup": "java -Xms128M -XX:MaxRAMPercentage=95.0 -Dterminal.jline=false -Dterminal.ansi=true -jar {{SERVER_JARFILE}}",
        "environment": {"MINECRAFT_VERSION": "latest", "SERVER_JARFILE": "server.jar", "BUILD_NUMBER": "latest", "EULA": "TRUE"},
    },
    "forge": {
        "display": "Minecraft: Forge",
        "nest_id": 1,
        "egg_id": 4,
        "docker_image": "ghcr.io/pterodactyl/yolks:java_17",
        "startup": "java -Xms128M -Xmx{{SERVER_MEMORY}}M -jar {{SERVER_JARFILE}}",
        "environment": {"SERVER_JARFILE": "server.jar", "FORGE_VERSION": "latest", "MINECRAFT_VERSION": "latest"},
    },
    "sponge": {
        "display": "Minecraft: Sponge",
        "nest_id": 1,
        "egg_id": 6,
        "docker_image": "ghcr.io/pterodactyl/yolks:java_11",
        "startup": "java -Xms128M -Xmx{{SERVER_MEMORY}}M -jar {{SERVER_JARFILE}}",
        "environment": {"SERVER_JARFILE": "server.jar", "SPONGE_VERSION": "stable-7", "MINECRAFT_VERSION": "1.12.2", "EULA": "TRUE"},
    },
    "nodejs": {
        "display": "Node.js",
        "nest_id": 5,
        "egg_id": 16,
        "docker_image": "ghcr.io/pterodactyl/yolks:nodejs_18",
        "startup": "node index.js",
        "environment": {"STARTUP_FILE": "index.js"},
    },
    "python": {
        "display": "Python",
        "nest_id": 5,
        "egg_id": 17,
        "docker_image": "ghcr.io/pterodactyl/yolks:python_3.11",
        "startup": "python3 main.py",
        "environment": {"STARTUP_FILE": "main.py"},
    },
    "mariadb": {
        "display": "MariaDB",
        "nest_id": 7,
        "egg_id": 20,
        "docker_image": "ghcr.io/pterodactyl/yolks:debian",
        "startup": "mysqld --defaults-file=/mnt/server/my.cnf",
        "environment": {"MYSQL_ROOT_PASSWORD": "root", "MYSQL_DATABASE": "panel"},
    },
}

def build_env_for_egg(egg_key: str) -> Dict[str, Any]:
    env = dict(DEFAULT_ENV)
    env.update(EGG_CATALOG.get(egg_key, {}).get("environment", {}))
    # ensure defaults
    for k, v in DEFAULT_ENV.items():
        if env.get(k) in (None, ""):
            env[k] = v
    return env

def egg_list_text() -> str:
    return "\n".join([f"- `{k}` → {v['display']}" for k, v in EGG_CATALOG.items()])

# =========================
# Admin checks
# =========================
def is_admin_member(member: discord.Member) -> bool:
    if not member:
        return False
    # guild admin perms
    try:
        if getattr(member, "guild_permissions", None) and member.guild_permissions.administrator:
            return True
    except Exception:
        pass
    # stored admins
    if str(member.id) in set(data.get("admins", [])):
        return True
    return False

async def require_admin_ctx(ctx: commands.Context) -> bool:
    if not is_admin_member(ctx.author):
        await ctx.reply("🔒 You are not authorized to use admin commands.")
        return False
    return True

# =========================
# Panel helpers: allocations / user lookup / server create/delete/list
# =========================
async def get_free_allocation(node_id: int = PANEL_NODE_ID) -> Optional[int]:
    status, js, text = await request_app("GET", f"/nodes/{node_id}/allocations")
    if status != 200 or not js:
        # fallback: if DEFAULT_ALLOCATION_ID is set
        try:
            return int(DEFAULT_ALLOCATION_ID) if DEFAULT_ALLOCATION_ID else None
        except Exception:
            return None
    for item in js.get("data", []):
        attr = item.get("attributes", {})
        if not attr.get("assigned", False):
            # Attribute id commonly is attr['id'] (allocation record id)
            try:
                return int(attr.get("id"))
            except Exception:
                continue
    try:
        return int(DEFAULT_ALLOCATION_ID) if DEFAULT_ALLOCATION_ID else None
    except Exception:
        return None

async def find_panel_user_by_email(email: str) -> Optional[int]:
    # try filter param first
    status, js, text = await request_app("GET", "/users", params={"filter[email]": email})
    if status == 200 and js:
        if js.get("data"):
            return int(js["data"][0]["attributes"]["id"])
    # fallback: list all and match email
    status, js, text = await request_app("GET", "/users")
    if status == 200 and js:
        for u in js.get("data", []):
            a = u.get("attributes", {})
            if a.get("email", "").lower() == email.lower():
                return int(a.get("id"))
    return None

async def create_panel_user(email: str, username: str, password: Optional[str] = None, first_name: str = "Discord", last_name: str = "User") -> Optional[int]:
    payload = {"email": email, "username": username, "first_name": first_name, "last_name": last_name}
    if password:
        payload["password"] = password
    status, js, text = await request_app("POST", "/users", json_payload=payload)
    if status in (200, 201) and js:
        try:
            return int(js.get("attributes", {}).get("id"))
        except Exception:
            pass
    # if failed due to exists, try lookup
    if status == 422:
        uid = await find_panel_user_by_email(email)
        return uid
    return None

async def delete_panel_user(panel_user_id: int) -> bool:
    status, js, text = await request_app("DELETE", f"/users/{panel_user_id}")
    return status in (200, 204)

async def create_server_app(name: str, owner_panel_id: int, egg_key: str, memory: int, cpu: int, disk: int, allocation_id: Optional[int] = None) -> Tuple[bool, str]:
    if egg_key not in EGG_CATALOG:
        return False, "Unknown egg key."
    egg_def = EGG_CATALOG[egg_key]
    alloc = allocation_id or await get_free_allocation()
    if not alloc:
        return False, "No free allocation available and no DEFAULT_ALLOCATION_ID set."

    payload = {
        "name": name,
        "user": owner_panel_id,
        "nest": egg_def["nest_id"],
        "egg": egg_def["egg_id"],
        "docker_image": egg_def["docker_image"],
        "startup": egg_def["startup"],
        "limits": {"memory": memory, "swap": 0, "disk": disk, "io": 500, "cpu": cpu},
        "feature_limits": {"databases": 1, "allocations": 1, "backups": 1},
        "allocation": {"default": alloc},
        "environment": build_env_for_egg(egg_key)
    }

    status, js, text = await request_app("POST", "/servers", json_payload=payload, timeout=60)
    if status in (200, 201) and js:
        ident = js.get("attributes", {}).get("identifier", js.get("attributes", {}).get("id", "unknown"))
        return True, f"✅ Server creation queued. Identifier: `{ident}`"
    return False, f"❌ Panel error {status}: {text}"

async def delete_server_app(server_id: int) -> Tuple[bool, str]:
    status, js, text = await request_app("DELETE", f"/servers/{server_id}")
    if status in (200, 204):
        return True, "✅ Server deleted."
    return False, f"❌ Panel error {status}: {text}"

async def list_servers_app() -> List[Dict[str, Any]]:
    status, js, text = await request_app("GET", "/servers")
    out = []
    if status != 200 or not js:
        return out
    for d in js.get("data", []):
        a = d.get("attributes", {})
        out.append({"id": a.get("id"), "name": a.get("name"), "identifier": a.get("identifier"), "limits": a.get("limits", {})})
    return out

async def node_stats(node_id: int = PANEL_NODE_ID) -> Tuple[int, int]:
    free = 0
    total = 0
    status, js, text = await request_app("GET", f"/nodes/{node_id}/allocations")
    if status != 200 or not js:
        return 0, 0
    for item in js.get("data", []):
        total += 1
        if not item.get("attributes", {}).get("assigned", False):
            free += 1
    return free, total

# =========================
# Client (user) API helpers for manage
# =========================
def client_headers(client_key: str) -> Dict[str, str]:
    return {"Authorization": f"Bearer {client_key}", "Content-Type": "application/json", "Accept": "application/json"}

async def client_power(client_key: str, identifier: str, signal: str) -> Tuple[bool, str]:
    url = f"{PANEL_URL}/api/client/servers/{identifier}/power"
    async with aiohttp.ClientSession() as s:
        async with s.post(url, headers=client_headers(client_key), json={"signal": signal}) as r:
            text = await r.text()
            if r.status in (200, 204):
                return True, f"✅ Power `{signal}` sent."
            return False, f"❌ Client error {r.status}: {text}"

async def client_reinstall(client_key: str, identifier: str) -> Tuple[bool, str]:
    url = f"{PANEL_URL}/api/client/servers/{identifier}/reinstall"
    async with aiohttp.ClientSession() as s:
        async with s.post(url, headers=client_headers(client_key)) as r:
            text = await r.text()
            if r.status in (200, 202, 204):
                return True, "✅ Reinstall queued."
            return False, f"❌ Client error {r.status}: {text}"

async def client_info(client_key: str, identifier: str) -> Tuple[bool, str]:
    url = f"{PANEL_URL}/api/client/servers/{identifier}"
    async with aiohttp.ClientSession() as s:
        async with s.get(url, headers=client_headers(client_key)) as r:
            text = await r.text()
            if r.status != 200:
                return False, f"❌ Client error {r.status}: {text}"
            js = await r.json()
            a = js.get("attributes", {})
            sftp = a.get("relationships", {}).get("allocations", {}) if isinstance(a.get("relationships", {}), dict) else {}
            # best-effort extract
            sftp_details = a.get("sftp_details", {})
            ip = sftp_details.get("ip", "n/a")
            port = sftp_details.get("port", "n/a")
            return True, f"🧩 Name: **{a.get('name')}**\nID: `{a.get('identifier')}`\nSFTP: `{ip}:{port}`\nStatus: {a.get('status','n/a')}"

# =========================
# Events
# =========================
@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user} | Prefix {PREFIX} | Version {BOT_VERSION}")
    await bot.change_presence(activity=discord.Game(name=f"{PREFIX}help | {BOT_VERSION}"))

# =========================
# HELP
# =========================
@bot.command(name="help")
async def help_cmd(ctx: commands.Context):
    em = discord.Embed(title="Bot Help", color=discord.Color.blurple())
    em.add_field(name="User", value=(
        f"`{PREFIX}register <email> <password>` — link/create panel user\n"
        f"`{PREFIX}admin create_ad <email> <pass> <admin panel yes/no>` — create (link required)\n"
        f"`{PREFIX}plans` `{PREFIX}i [@user]` `{PREFIX}upgrade` `{PREFIX}serverinfo` `{PREFIX}botinfo`"
    ), inline=False)
    em.add_field(name="Server (client)", value=(
        f"`{PREFIX}suspendserver <serverid>`\n"
        f"`{PREFIX}unsuspendserver <serverid>`\n"
        f"`{PREFIX}sendserver `ram cpu disk email pass usertag>`\n"
        f"`{PREFIX}node <status>`"
    ), inline=False)
    em.add_field(name="Admin", value=(
        f"`{PREFIX}admin add_i @user <amount>` / `remove_i @user <amount>`\n"
        f"`{PREFIX}admin add_a @user` / `rm_a @user`\n"
        f"`{PREFIX}admin create_a @user <email> <password>`\n"
        f"`{PREFIX}admin rm_ac @user`\n"
        f"`{PREFIX}admin create_s <owner_email> <egg> <name> <ram> <cpu> <disk>`\n"
        f"`{PREFIX}admin delete_s <server_id>` `{PREFIX}admin serverlist`\n"
        f"`{PREFIX}admin newmsg <channel_id> <text>` `{PREFIX}admin lock` / `unlock`"
    ), inline=False)
    em.set_footer(text=f"{MADE_BY} • {SERVER_LOCATION} • {BOT_VERSION}")
    await ctx.reply(embed=em, mention_author=False)

# -------------------- USER CREATE OWN API KEY --------------------
@bot.command(name="createkey")
async def createkey(ctx, email: str, password: str, namekey: str):
    await ctx.message.delete()  # hide user credentials from chat for security
    msg = await ctx.send("⏳ Generating your API key...")

    login_url = "https://panel.fluidmc.fun/auth/login"
    create_url = "https://panel.fluidmc.fun/api/client/account/api-keys"

    async with aiohttp.ClientSession() as session:
        # Step 1: login with user email + password
        login_data = {"user": email, "password": password}
        async with session.post(login_url, data=login_data) as resp:
            if resp.status != 200:
                return await msg.edit(content="❌ Invalid email or password.")

        # Step 2: create new API key
        headers = {"Accept": "application/json", "Content-Type": "application/json"}
        payload = {"description": namekey}
        async with session.post(create_url, headers=headers, json=payload) as resp2:
            if resp2.status in [200, 201]:
                data = await resp2.json()
                secret = data.get("token", "❌ Not Found")

                embed = discord.Embed(
                    title="✅ API Key Created",
                    color=discord.Color.green()
                )
                embed.add_field(name="📧 Email", value=f"`{email}`", inline=False)
                embed.add_field(name="🔑 Key Name", value=f"`{namekey}`", inline=True)
                embed.add_field(name="🗝️ API Key", value=f"```{secret}```", inline=False)
                embed.set_footer(text="Save this key safely, you won’t see it again.")

                await msg.edit(content="", embed=embed)
            else:
                err = await resp2.text()
                await msg.edit(content=f"❌ Failed to create API key. ({resp2.status})\n{err}")
    
# =========================
# Plans / invites / info
# =========================
@bot.command(name="plans")
async def plans_cmd(ctx):
    plans = [
        ("Basic", 0, 4096, 150, 10000),
        ("Advanced", 4, 6144, 200, 15000),
        ("Pro", 6, 7168, 230, 20000),
        ("Premium", 8, 9216, 270, 25000),
        ("Elite", 15, 12288, 320, 30000),
        ("Ultimate", 20, 16384, 400, 35000),
    ]
    desc = "\n\n".join([f"**{n}** — at {inv} invites\nRAM {ram}MB | CPU {cpu}% | Disk {disk}MB" for (n, inv, ram, cpu, disk) in plans])
    await ctx.reply(embed=discord.Embed(title="Invite Plans", description=desc, color=discord.Color.gold()))

@bot.command(name="i")
async def i_cmd(ctx, member: Optional[discord.Member] = None):
    target = member or ctx.author
    invites = int(data.get("invites", {}).get(str(target.id), 0))
    tier = "Basic"
    if invites >= 20: tier = "Ultimate"
    elif invites >= 15: tier = "Elite"
    elif invites >= 8: tier = "Premium"
    elif invites >= 6: tier = "Pro"
    elif invites >= 4: tier = "Advanced"
    em = discord.Embed(title=f"Invites — {target.display_name}", color=discord.Color.blue())
    em.add_field(name="Total Invites", value=str(invites))
    em.add_field(name="Tier", value=tier)
    await ctx.reply(embed=em)

@bot.command(name="upgrade")
async def upgrade_cmd(ctx):
    await ctx.reply("To upgrade, contact admin or use invite thresholds. (This is a placeholder.)")

@bot.command(name="serverinfo")
async def serverinfo_cmd(ctx):
    g = ctx.guild
    if not g:
        return await ctx.reply("This command must be used in a guild.")
    em = discord.Embed(title=g.name, color=discord.Color.green())
    em.add_field(name="ID", value=str(g.id))
    em.add_field(name="Owner", value=str(g.owner))
    em.add_field(name="Members", value=str(g.member_count))
    em.add_field(name="Boosts", value=str(g.premium_subscription_count))
    await ctx.reply(embed=em)

@bot.command(name="botinfo")
async def botinfo_cmd(ctx):
    em = discord.Embed(title="Bot Info", color=discord.Color.purple())
    em.add_field(name="Version", value=BOT_VERSION)
    em.add_field(name="Made By", value=MADE_BY)
    em.add_field(name="Location", value=SERVER_LOCATION)
    await ctx.reply(embed=em)

# =========================
# Register & Create (User)
# =========================
@bot.command(name="register")
async def register_cmd(ctx, email: str, password: str):
    # create or link panel user
    try:
        # attempt to create
        uid = await create_panel_user(email=email, username=f"u{ctx.author.id}", password=password, first_name=ctx.author.name)
        if not uid:
            return await ctx.reply("❌ Failed to create or find panel user. Check API/permissions.")
        data.setdefault("panel_users", {})[str(ctx.author.id)] = uid
        save_data(data)
        await ctx.reply(f"✅ Linked panel user id `{uid}` to your Discord account.")

# =========================
# Manage group (client API)
# =========================
import aiohttp, discord, random, os
from discord.ext import commands

bot = commands.Bot(command_prefix="*", intents=discord.Intents.all())

DB_FILE = "manage_db.txt"

# ---------------- Database Helpers ----------------
def load_db():
    if not os.path.exists(DB_FILE):
        return {}
    with open(DB_FILE, "r") as f:
        lines = f.readlines()
    db = {}
    for line in lines:
        user, mid, token = line.strip().split("|")
        if user not in db:
            db[user] = []
        db[user].append({"mid": mid, "token": token})
    return db

def save_db(db):
    with open(DB_FILE, "w") as f:
        for user, entries in db.items():
            for e in entries:
                f.write(f"{user}|{e['mid']}|{e['token']}\n")

def token_in_use(db, token):
    for entries in db.values():
        for e in entries:
            if e["token"] == token:
                return True
    return False

def generate_mid():
    return f"MNG-{random.randint(10000,99999)}"

# ---------------- Panel Control View ----------------
class ManageServerView(discord.ui.View):
    def __init__(self, token: str, serverid: str):
        super().__init__(timeout=None)
        self.token = token
        self.serverid = serverid
        self.base = f"https://panel.fluidmc.fun/api/client/servers/{self.serverid}"

    async def _post_power(self, interaction: discord.Interaction, signal: str):
        url = f"{self.base}/power"
        headers = {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json={"signal": signal}) as resp:
                if resp.status == 204:
                    await interaction.response.send_message(f"✅ `{signal}` sent.", ephemeral=True)
                else:
                    await interaction.response.send_message(f"❌ Failed ({resp.status})", ephemeral=True)

    @discord.ui.button(label="Start", style=discord.ButtonStyle.success)
    async def start(self, interaction, button): await self._post_power(interaction, "start")

    @discord.ui.button(label="Stop", style=discord.ButtonStyle.danger)
    async def stop(self, interaction, button): await self._post_power(interaction, "stop")

    @discord.ui.button(label="Restart", style=discord.ButtonStyle.primary)
    async def restart(self, interaction, button): await self._post_power(interaction, "restart")

    @discord.ui.button(label="Reinstall", style=discord.ButtonStyle.secondary)
    async def reinstall(self, interaction, button): await self._post_power(interaction, "reinstall")

    @discord.ui.button(label="List Files", style=discord.ButtonStyle.blurple)
    async def listfiles(self, interaction, button):
        url = f"{self.base}/files/list?directory=/"
        headers = {"Authorization": f"Bearer {self.token}"}
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    files = [f['attributes']['name'] for f in data['data']]
                    await interaction.response.send_message("📂 Files:\n" + "\n".join(files[:10]), ephemeral=True)
                else:
                    await interaction.response.send_message(f"❌ Cannot list files ({resp.status})", ephemeral=True)

    @discord.ui.button(label="Upload File", style=discord.ButtonStyle.gray)
    async def uploadfile(self, interaction, button):
        await interaction.response.send_message("📤 Reply with file to upload.", ephemeral=True)

    @discord.ui.button(label="Delete File", style=discord.ButtonStyle.red)
    async def deletefile(self, interaction, button):
        await interaction.response.send_message("🗑️ Enter file path to delete.", ephemeral=True)

    @discord.ui.button(label="Edit File", style=discord.ButtonStyle.green)
    async def editfile(self, interaction, button):
        await interaction.response.send_message("✏️ Enter file path + new content.", ephemeral=True)

    @discord.ui.button(label="Run CMD", style=discord.ButtonStyle.gray)
    async def runcmd(self, interaction, button):
        await interaction.response.send_message("⌨️ Enter command to run.", ephemeral=True)
    
    @discord.ui.button(label="➕ Op Add (Minecraft)", style=discord.ButtonStyle.green)
    async def op_add(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.userid:
            return await interaction.response.send_message("❌ You are not the owner of this manage session.", ephemeral=True)

        await interaction.response.send_message("🎮 Please enter your **Minecraft Server Name**:", ephemeral=True)

        def check(m): 
            return m.author == interaction.user and m.channel == interaction.channel

        try:
            msg = await bot.wait_for("message", check=check, timeout=30)
        except:
            return await interaction.followup.send("⌛ Timeout! Try again.", ephemeral=True)

        server_name = msg.content.strip()

        # Save operation in database.txt (or separate file)
        with open("operations.txt", "a") as f:
            f.write(f"{interaction.user.id}|{server_name}\n")

        await interaction.followup.send(f"✅ Operation added: **Minecraft – {server_name}**", ephemeral=True)

    @discord.ui.button(label="📦 Backup Create", style=discord.ButtonStyle.gray)
    async def backup_create(self, interaction: discord.Interaction, button: discord.ui.Button):
        url = f"{self.base}/backups"
        headers = {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}
        payload = {"name": f"backup-{random.randint(1000,9999)}"}
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as resp:
                if resp.status == 201:
                    data = await resp.json()
                    bid = data["attributes"]["uuid"]
                    await interaction.response.send_message(f"✅ Backup Created: `{bid}`", ephemeral=True)
                else:
                    await interaction.response.send_message(f"❌ Backup Failed ({resp.status})", ephemeral=True)
                    
    @discord.ui.button(label="Status", style=discord.ButtonStyle.blurple)
    async def status(self, interaction, button):
        url = f"{self.base}/resources"
        headers = {"Authorization": f"Bearer {self.token}"}
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    state = data["attributes"]["current_state"]
                    cpu = data["attributes"]["resources"]["cpu_absolute"]
                    mem = round(data["attributes"]["resources"]["memory_bytes"] / 1024 / 1024, 2)
                    await interaction.response.send_message(f"ℹ️ {state} | CPU: {cpu}% | RAM: {mem} MB", ephemeral=True)
                else:
                    await interaction.response.send_message(f"❌ Failed status ({resp.status})", ephemeral=True)

    @discord.ui.button(label="Exit", style=discord.ButtonStyle.red)
    async def exit(self, interaction, button):
        await interaction.message.delete()
        await interaction.response.send_message("❌ Closed panel.", ephemeral=True)

# ---------------- Manage Command ----------------
@bot.command(name="manage")
async def manage(ctx, token: str = None):
    user_id = str(ctx.author.id)
    db = load_db()

    # First time (with token)
    if token:
        if token_in_use(db, token):
            return await ctx.reply("❌ This token is already linked to another account.")

        await ctx.reply("⚡ Do you want to save this token? Reply with `yes` or `no`.")

        def check(m): return m.author == ctx.author and m.channel == ctx.channel
        try:
            msg = await bot.wait_for("message", check=check, timeout=30)
        except:
            return await ctx.reply("⌛ Timeout. Try again.")

        if msg.content.lower() == "yes":
            mid = generate_mid()
            if user_id not in db: db[user_id] = []
            db[user_id].append({"mid": mid, "token": token})
            save_db(db)
            await ctx.reply(f"✅ Your ManageID `{mid}` has been linked.")
        else:
            return await ctx.reply("❌ Token not saved.")

    # Second time (without token)
    if user_id not in db or not db[user_id]:
        return await ctx.reply("❌ No saved tokens. Use `*manage <token>` first.")

    # For simplicity, always pick first linked token
    entry = db[user_id][0]
    token = entry["token"]
    mid = entry["mid"]

    # Get servers from panel
    headers = {"Authorization": f"Bearer {token}"}
    async with aiohttp.ClientSession() as session:
        async with session.get("https://panel.fluidmc.fun/api/client", headers=headers) as resp:
            if resp.status != 200:
                return await ctx.reply("❌ Invalid saved token.")
            data = await resp.json()

    servers = data.get("data", [])
    if not servers:
        return await ctx.reply("❌ No servers found.")

    for server in servers:
        sid = server["attributes"]["identifier"]
        name = server["attributes"]["name"]
        embed = discord.Embed(
            title=f"🎮 {name} ({mid})",
            description="Use the buttons below to control your server.",
            color=discord.Color.green()
        )
        await ctx.send(embed=embed, view=ManageServerView(token, sid))

# -------------------- GET SERVER INTERNAL ID --------------------
async def get_server_internal_id(identifier):
    url = "https://panel.fluidmc.fun/api/application/servers"
    headers = {"Authorization": f"Bearer {API_KEY}", "Accept": "application/json"}
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as resp:
            if resp.status != 200:
                return None
            data = await resp.json()
            for s in data.get("data", []):
                if s['attributes']['identifier'] == identifier:
                    return s['attributes']['id']
    return None
# -------------------- ADMIN CREATE ACCOUNT --------------------
@bot.command(name="create_ad")
async def create_ad(ctx, email: str, password: str, is_admin: str):
    if not await require_admin_ctx(ctx):
        return await ctx.reply("❌ Only admins can use this command.")

    url = "https://panel.fluidmc.fun/api/application/users"
    headers = {"Authorization": f"Bearer {API_KEY}", "Accept": "application/json", "Content-Type": "application/json"}
    payload = {
        "email": email,
        "username": email.split("@")[0],
        "first_name": "User",
        "last_name": "Created",
        "password": password,
        "root_admin": True if is_admin.lower() == "yes" else False,
        "language": "en"
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=payload) as resp:
            if resp.status == 201:
                return await ctx.reply(f"✅ Created account for `{email}` | Admin: {is_admin}")
            else:
                err = await resp.text()
                return await ctx.reply(f"❌ Failed to create account. ({resp.status})\n{err}")

# =========================
# Node status
# =========================
@bot.command(name="node")
async def node_cmd(ctx):
    free, total = await node_stats()
    await ctx.reply(f"🖥 Node `{PANEL_NODE_ID}` allocations: **{free} free / {total} total**")

# =========================
# Moderation
# =========================
@bot.command(name="clear")
@commands.has_permissions(manage_messages=True)
async def clear_cmd(ctx, amount: int = 10):
    await ctx.channel.purge(limit=amount)
    m = await ctx.send(f"🧹 Cleared {amount} messages.")
    await asyncio.sleep(3)
    try:
        await m.delete()
    except Exception:
        pass

# =========================
# Admin group + commands
# =========================
@bot.group(name="admin", invoke_without_command=True)
async def admin_grp(ctx):
    if not await require_admin_ctx(ctx): return
    await ctx.reply("Use admin subcommands (add_i/remove_i/add_a/rm_a/create_a/rm_ac/create_s/delete_s/serverlist/newmsg/lock/unlock)")

@admin_grp.command(name="add_i")
async def admin_add_i(ctx, member: discord.Member, amount: int):
    if not await require_admin_ctx(ctx): return
    inv = data.setdefault("invites", {})
    inv[str(member.id)] = int(inv.get(str(member.id), 0)) + amount
    save_data(data)
    await ctx.reply(f"✅ Added {amount} invites to {member.mention} (now {inv[str(member.id)]}).")

@admin_grp.command(name="remove_i")
async def admin_remove_i(ctx, member: discord.Member, amount: int):
    if not await require_admin_ctx(ctx): return
    inv = data.setdefault("invites", {})
    inv[str(member.id)] = max(0, int(inv.get(str(member.id), 0)) - amount)
    save_data(data)
    await ctx.reply(f"✅ Removed {amount} invites from {member.mention} (now {inv[str(member.id)]}).")

@admin_grp.command(name="add_a")
async def admin_add_a(ctx, member: discord.Member):
    if not await require_admin_ctx(ctx): return
    admins = set(data.get("admins", []))
    admins.add(str(member.id))
    data["admins"] = list(admins)
    save_data(data)
    await ctx.reply(f"✅ {member.mention} added to bot-admins.")

@admin_grp.command(name="rm_a")
async def admin_rm_a(ctx, member: discord.Member):
    if not await require_admin_ctx(ctx): return
    admins = set(data.get("admins", []))
    admins.discard(str(member.id))
    data["admins"] = list(admins)
    save_data(data)
    await ctx.reply(f"✅ {member.mention} removed from bot-admins.")

@admin_grp.command(name="create_a")
async def admin_create_a(ctx, member: discord.Member, email: str, password: str):
    if not await require_admin_ctx(ctx): return
    uid = await create_panel_user(email=email, username=f"u{member.id}", password=password, first_name=member.name)
    if not uid:
        return await ctx.reply("❌ Failed to create panel user.")
    data.setdefault("panel_users", {})[str(member.id)] = uid
    save_data(data)
    await ctx.reply(f"✅ Created panel user `{uid}` and linked to {member.mention}")

@admin_grp.command(name="rm_ac")
async def admin_rm_ac(ctx, member: discord.Member):
    if not await require_admin_ctx(ctx): return
    pu = data.get("panel_users", {}).pop(str(member.id), None)
    if pu:
        save_data(data)
        await ctx.reply(f"✅ Unlinked panel user from {member.mention}")
    else:
        await ctx.reply("Nothing to unlink.")

@admin_grp.command(name="create_s")
async def admin_create_s(ctx, owner_email: str, egg: str, name: str, ram: int, cpu: int, disk: int):
    if not await require_admin_ctx(ctx): return
    uid = await find_panel_user_by_email(owner_email)
    if not uid:
        return await ctx.reply("❌ Owner email not found in panel.")
    await ctx.reply("⚙️ Creating server...")
    ok, msg = await create_server_app(name=name, owner_panel_id=uid, egg_key=egg, memory=ram, cpu=cpu, disk=disk)
    await ctx.reply(msg)

@admin_grp.command(name="delete_s")
async def admin_delete_s(ctx, server_id: int):
    if not await require_admin_ctx(ctx): return
    ok, msg = await delete_server_app(server_id)
    await ctx.reply(msg)

@admin_grp.command(name="serverlist")
async def admin_serverlist(ctx):
    if not await require_admin_ctx(ctx): return
    servers = await list_servers_app()
    if not servers:
        return await ctx.reply("No servers found.")
    lines = [f"- ID `{s['id']}` | {s['name']} | ident `{s['identifier']}` | RAM {s['limits'].get('memory','?')}MB" for s in servers]
    await ctx.reply("\n".join(lines)[:1900])

@admin_grp.command(name="newmsg")
async def admin_newmsg(ctx, channel_id: int, *, text: str):
    if not await require_admin_ctx(ctx): return
    ch = ctx.guild.get_channel(channel_id)
    if not ch:
        return await ctx.reply("Channel not found or bot lacks access.")
    await ch.send(text)
    await ctx.reply("✅ Sent.")

@admin_grp.command(name="lock")
async def admin_lock(ctx):
    if not await require_admin_ctx(ctx): return
    ch: discord.TextChannel = ctx.channel
    overwrite = ch.overwrites_for(ctx.guild.default_role)
    overwrite.send_messages = False
    await ch.set_permissions(ctx.guild.default_role, overwrite=overwrite)
    locked_ids = set(map(int, data.get("locked_channels", [])))
    locked_ids.add(ch.id)
    data["locked_channels"] = list(map(str, locked_ids))
    save_data(data)
    await ctx.reply("🔒 Channel locked.")

@admin_grp.command(name="unlock")
async def admin_unlock(ctx):
    if not await require_admin_ctx(ctx): return
    ch: discord.TextChannel = ctx.channel
    overwrite = ch.overwrites_for(ctx.guild.default_role)
    overwrite.send_messages = None
    await ch.set_permissions(ctx.guild.default_role, overwrite=overwrite)
    locked_ids = set(map(int, data.get("locked_channels", [])))
    if ch.id in locked_ids:
        locked_ids.remove(ch.id)
    data["locked_channels"] = list(map(str, locked_ids))
    save_data(data)
    await ctx.reply("🔓 Channel unlocked.")

# ==========================
# Suspend server (Admin only)
# ==========================
@bot.command(name="suspendserver")
async def suspend_server(ctx, serverid: str):
    if str(ctx.author.id) not in ADMIN_IDS:
        return await ctx.reply("❌ You are not authorized to use this command.")

    url = f"{PANEL_URL}/api/application/servers/{serverid}/suspend"
    headers = {"Authorization": f"Bearer {APP_API_KEY}", "Content-Type": "application/json", "Accept": "application/json"}
    r = requests.post(url, headers=headers)

    if r.status_code == 204:
        await ctx.reply(f"✅ Server `{serverid}` suspended successfully.")
    else:
        await ctx.reply(f"❌ Failed to suspend server. ({r.text})")


# ==========================
# Unsuspend server (Admin only)
# ==========================
@bot.command(name="unsuspendserver")
async def unsuspend_server(ctx, serverid: str):
    if str(ctx.author.id) not in ADMIN_IDS:
        return await ctx.reply("❌ You are not authorized to use this command.")

    url = f"{PANEL_URL}/api/application/servers/{serverid}/unsuspend"
    headers = {"Authorization": f"Bearer {APP_API_KEY}", "Content-Type": "application/json", "Accept": "application/json"}
    r = requests.post(url, headers=headers)

    if r.status_code == 204:
        await ctx.reply(f"✅ Server `{serverid}` unsuspended successfully.")
    else:
        await ctx.reply(f"❌ Failed to unsuspend server. ({r.text})")


# ==========================
# Create Client API Key (User allowed)
# ==========================
@bot.command(name="createapikey")
async def create_api_key(ctx, name: str):
    url = f"{PANEL_URL}/api/client/account/api-keys"
    headers = {"Authorization": f"Bearer {APP_API_KEY}", "Content-Type": "application/json", "Accept": "application/json"}
    data = {"description": name}
    r = requests.post(url, headers=headers, json=data)

    if r.status_code in (200, 201):
        api_key = r.json().get("secret")
        await ctx.author.send(f"🔑 Your Client API Key: `{api_key}`")
        await ctx.reply("✅ API key created and sent to your DM.")
    else:
        await ctx.reply(f"❌ Failed to create API key. ({r.text})")


# ==========================
# Change user password (User allowed)
# ==========================
@bot.command(name="changepass")
async def change_pass(ctx, email: str, old: str, new: str, confirm: str):
    if new != confirm:
        return await ctx.reply("❌ New password and confirm password do not match.")

    user_id = await find_panel_user_by_email(email)  # 👉 tera function
    if not user_id:
        return await ctx.reply("❌ User not found.")

    url = f"{PANEL_URL}/api/application/users/{user_id}"
    headers = {"Authorization": f"Bearer {APP_API_KEY}", "Content-Type": "application/json", "Accept": "application/json"}
    data = {"password": new}
    r = requests.patch(url, headers=headers, json=data)

    if r.status_code == 200:
        await ctx.reply(f"✅ Password updated for `{email}`.")
    else:
        await ctx.reply(f"❌ Failed to change password. ({r.text})")


# ==========================
# Send Server Info to User (Admin only)
# ==========================
@bot.command(name="sendserver")
async def send_server(ctx, ram: int, cpu: int, disk: int, email: str, password: str, usertag: discord.User):
    if str(ctx.author.id) not in ADMIN_IDS:
        return await ctx.reply("❌ You are not authorized to use this command.")

    uid = await find_panel_user_by_email(email)
    if not uid:
        return await ctx.reply("❌ User email not found.")

    ok, msg = await create_server_app(
        name=f"{usertag.name}_server",
        owner_panel_id=uid,
        egg_key="paper",
        memory=ram,
        cpu=cpu,
        disk=disk
    )

    if ok:
        try:
            await usertag.send(
                f"🎉 Your server has been created!\n"
                f"🔗 Panel: {PANEL_URL}\n"
                f"📧 Email: `{email}`\n"
                f"🔑 Password: `{password}`\n"
                f"💾 Specs: {ram}MB RAM | {cpu}% CPU | {disk}MB Disk"
            )
            await ctx.reply(f"✅ Server created and info sent to {usertag.mention}")
        except:
            await ctx.reply("⚠️ Could not DM user, maybe DMs are off.")
    else:
        await ctx.reply(f"❌ {msg}")


# ==========================
# Drop message (Admin broadcast)
# ==========================
@bot.command(name="drop")
async def drop_msg(ctx, *, message: str):
    if str(ctx.author.id) not in ADMIN_IDS:
        return await ctx.reply("❌ You are not authorized to use this command.")

    for member in ctx.guild.members:
        try:
            await member.send(f"📢 {message}")
        except:
            continue
    await ctx.reply("✅ Broadcast message sent to all users.")

# =========================
# Run bot
# =========================
bot.run(BOT_TOKEN)
