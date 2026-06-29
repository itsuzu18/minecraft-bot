import os
import asyncio
import discord
from discord.ext import tasks
from python_aternos import Client as AternosClient
from dotenv import load_dotenv

load_dotenv()

# ── Config ───────────────────────────────────────────────────────────────────
DISCORD_TOKEN = os.environ.get("DISCORD_TOKEN", "")
CHANNEL_ID    = int(os.environ.get("CHANNEL_ID", "0"))
ATERNOS_USER  = os.environ.get("ATERNOS_USER", "")
ATERNOS_PASS  = os.environ.get("ATERNOS_PASS", "")
SERVER_NAME   = os.environ.get("SERVER_NAME", "")

# Debug: print env vars (sensor value)
print(f"[Config] DISCORD_TOKEN: {'SET' if DISCORD_TOKEN else 'MISSING'}")
print(f"[Config] CHANNEL_ID: {CHANNEL_ID}")
print(f"[Config] ATERNOS_USER: {ATERNOS_USER}")
print(f"[Config] SERVER_NAME: {SERVER_NAME}")

# ── Setup Bot ─────────────────────────────────────────────────────────────────
intents = discord.Intents.default()
intents.message_content = True
bot = discord.Client(intents=intents)

# State global
aternos_server = None
status_message_id = None

# ── Connect ke Aternos ────────────────────────────────────────────────────────
def get_aternos_server():
    global aternos_server
    try:
        print("[Aternos] Logging in...")
        client = AternosClient.from_credentials(ATERNOS_USER, ATERNOS_PASS)
        servers = client.list_servers()
        print(f"[Aternos] Found {len(servers)} server(s)")
        for s in servers:
            print(f"[Aternos] Server: {s.address}")
            if SERVER_NAME.lower() in s.address.lower():
                aternos_server = s
                return s
        aternos_server = servers[0]
        return servers[0]
    except Exception as e:
        print(f"[Aternos] Error: {e}")
        return None

# ── Build Embed & Buttons ─────────────────────────────────────────────────────
def build_embed_and_buttons():
    try:
        if aternos_server:
            aternos_server.fetch()
        status   = aternos_server.status if aternos_server else "offline"
        address  = aternos_server.address if aternos_server else "unknown"
        players  = aternos_server.players_on if aternos_server else 0
        maxplay  = aternos_server.players_max if aternos_server else 20
        software = aternos_server.software if aternos_server else "Forge"
        version  = aternos_server.version if aternos_server else "1.20.1"
    except Exception as e:
        print(f"[Embed] Error fetching server info: {e}")
        status   = "offline"
        address  = SERVER_NAME + ".aternos.me"
        players  = 0
        maxplay  = 20
        software = "Forge"
        version  = "1.20.1"

    status_map = {
        "online":   ("🟢 Online",    0x00ff88),
        "offline":  ("🔴 Offline",   0xff4444),
        "starting": ("🟡 Starting…", 0xffcc00),
        "stopping": ("🟠 Stopping…", 0xff8800),
        "loading":  ("🟡 Loading…",  0xffcc00),
        "saving":   ("🟠 Saving…",   0xff8800),
    }
    status_text, color = status_map.get(status, ("⚪ Unknown", 0x888888))

    is_online  = status == "online"
    is_offline = status == "offline"

    embed = discord.Embed(title="🎮  Create SMP", color=color)
    embed.add_field(name="📡 Status",    value=status_text,           inline=True)
    embed.add_field(name="👥 Players",   value=f"{players}/{maxplay}", inline=True)
    embed.add_field(name="🌐 Address",   value=f"`{address}`",        inline=True)
    embed.add_field(name="⚙️ Software",  value=f"{software} {version}", inline=True)
    embed.set_footer(text="Auto-update tiap 30 detik • Create SMP")
    embed.timestamp = discord.utils.utcnow()

    view = discord.ui.View(timeout=None)
    view.add_item(discord.ui.Button(label="Start",   emoji="▶️", style=discord.ButtonStyle.success,   custom_id="mc_start",   disabled=not is_offline))
    view.add_item(discord.ui.Button(label="Stop",    emoji="⏹️", style=discord.ButtonStyle.danger,    custom_id="mc_stop",    disabled=not is_online))
    view.add_item(discord.ui.Button(label="Restart", emoji="🔄", style=discord.ButtonStyle.primary,   custom_id="mc_restart", disabled=not is_online))
    view.add_item(discord.ui.Button(label="Backup",  emoji="💾", style=discord.ButtonStyle.secondary, custom_id="mc_backup",  disabled=not is_online))

    return embed, view

# ── Update Pesan Status ───────────────────────────────────────────────────────
async def update_status_message():
    global status_message_id
    try:
        channel = bot.get_channel(CHANNEL_ID) or await bot.fetch_channel(CHANNEL_ID)
        embed, view = build_embed_and_buttons()

        if status_message_id:
            try:
                msg = await channel.fetch_message(status_message_id)
                await msg.edit(embed=embed, view=view)
                return
            except discord.NotFound:
                status_message_id = None

        msg = await channel.send(embed=embed, view=view)
        status_message_id = msg.id
        print(f"[Status] Message sent: {msg.id}")
    except Exception as e:
        print(f"[Status] Error: {e}")

# ── Auto Update Loop ──────────────────────────────────────────────────────────
@tasks.loop(seconds=30)
async def auto_update():
    await update_status_message()

# ── Bot Ready ─────────────────────────────────────────────────────────────────
@bot.event
async def on_ready():
    print(f"[Bot] Logged in as {bot.user}")
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, get_aternos_server)
    await update_status_message()
    if not auto_update.is_running():
        auto_update.start()

# ── Handle Tombol ─────────────────────────────────────────────────────────────
@bot.event
async def on_interaction(interaction: discord.Interaction):
    if interaction.type != discord.InteractionType.component:
        return

    custom_id = interaction.data.get("custom_id", "")
    if not custom_id.startswith("mc_"):
        return

    await interaction.response.defer(ephemeral=True)

    if not aternos_server:
        await interaction.followup.send("❌ Bot belum terhubung ke Aternos!", ephemeral=True)
        return

    loop = asyncio.get_event_loop()
    try:
        if custom_id == "mc_start":
            await loop.run_in_executor(None, aternos_server.start)
            await interaction.followup.send("✅ Server sedang dinyalakan! Tunggu ~2-5 menit.", ephemeral=True)
        elif custom_id == "mc_stop":
            await loop.run_in_executor(None, aternos_server.stop)
            await interaction.followup.send("✅ Server sedang dimatikan...", ephemeral=True)
        elif custom_id == "mc_restart":
            await loop.run_in_executor(None, aternos_server.restart)
            await interaction.followup.send("✅ Server sedang restart...", ephemeral=True)
        elif custom_id == "mc_backup":
            await interaction.followup.send(
                "💾 Backup manual: buka panel Aternos → **Backups** → Create Backup\n🔗 https://aternos.org/server/",
                ephemeral=True
            )
        await asyncio.sleep(3)
        await update_status_message()
    except Exception as e:
        print(f"[Button] Error {custom_id}: {e}")
        await interaction.followup.send(f"❌ Error: `{str(e)}`", ephemeral=True)

# ── Run ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    if not DISCORD_TOKEN:
        print("❌ DISCORD_TOKEN is missing!")
        exit(1)
    bot.run(DISCORD_TOKEN)
