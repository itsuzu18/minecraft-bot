import os
import asyncio
import discord
from discord.ext import tasks
from dotenv import load_dotenv
import cloudscraper
import json

load_dotenv()

# ── Config ────────────────────────────────────────────────────────────────────
DISCORD_TOKEN = os.environ.get("DISCORD_TOKEN", "")
CHANNEL_ID    = int(os.environ.get("CHANNEL_ID", "0"))
ATERNOS_USER  = os.environ.get("ATERNOS_USER", "")
ATERNOS_PASS  = os.environ.get("ATERNOS_PASS", "")
SERVER_NAME   = os.environ.get("SERVER_NAME", "")

print(f"[Config] DISCORD_TOKEN: {'SET' if DISCORD_TOKEN else 'MISSING'}")
print(f"[Config] CHANNEL_ID: {CHANNEL_ID}")
print(f"[Config] ATERNOS_USER: {ATERNOS_USER}")
print(f"[Config] SERVER_NAME: {SERVER_NAME}")

# ── Setup Bot ─────────────────────────────────────────────────────────────────
intents = discord.Intents.default()
intents.message_content = True
bot = discord.Client(intents=intents)

# State global
status_message_id = None
scraper = cloudscraper.create_scraper(
    browser={"browser": "chrome", "platform": "windows", "mobile": False}
)
server_info = {
    "status": "offline",
    "address": f"{SERVER_NAME}.aternos.me",
    "players": 0,
    "maxPlayers": 20,
    "software": "Forge",
    "version": "1.20.1"
}

# ── Aternos Login & Control ───────────────────────────────────────────────────
BASE = "https://aternos.org"

def aternos_login():
    try:
        print("[Aternos] Attempting login...")
        # Get login page first
        r = scraper.get(f"{BASE}/go/")
        # Login
        r = scraper.post(f"{BASE}/panel/ajax/account/login.php", data={
            "username": ATERNOS_USER,
            "password": ATERNOS_PASS
        })
        print(f"[Aternos] Login response: {r.status_code}")
        return r.status_code == 200
    except Exception as e:
        print(f"[Aternos] Login error: {e}")
        return False

def aternos_get_status():
    global server_info
    try:
        r = scraper.get(f"{BASE}/panel/ajax/status.php", params={"server": SERVER_NAME})
        if r.status_code == 200:
            data = r.json()
            server_info["status"]  = data.get("class", "offline")
            server_info["players"] = data.get("players", {}).get("online", 0)
            server_info["maxPlayers"] = data.get("players", {}).get("max", 20)
            print(f"[Aternos] Status: {server_info['status']}, Players: {server_info['players']}")
    except Exception as e:
        print(f"[Aternos] Status error: {e}")

def aternos_action(action):
    try:
        r = scraper.get(f"{BASE}/panel/ajax/server/{action}.php", params={"server": SERVER_NAME})
        print(f"[Aternos] Action {action}: {r.status_code}")
        return r.status_code == 200
    except Exception as e:
        print(f"[Aternos] Action error: {e}")
        return False

# ── Build Embed & Buttons ─────────────────────────────────────────────────────
def build_embed_and_buttons():
    status   = server_info.get("status", "offline")
    address  = server_info.get("address", f"{SERVER_NAME}.aternos.me")
    players  = server_info.get("players", 0)
    maxplay  = server_info.get("maxPlayers", 20)
    software = server_info.get("software", "Forge")
    version  = server_info.get("version", "1.20.1")

    status_map = {
        "online":   ("🟢 Online",    0x00ff88),
        "offline":  ("🔴 Offline",   0xff4444),
        "starting": ("🟡 Starting…", 0xffcc00),
        "stopping": ("🟠 Stopping…", 0xff8800),
        "loading":  ("🟡 Loading…",  0xffcc00),
        "saving":   ("🟠 Saving…",   0xff8800),
        "waiting":  ("⏳ Waiting…",  0xffcc00),
        "preparing":("🟡 Preparing…",0xffcc00),
    }
    status_text, color = status_map.get(status, ("⚪ Unknown", 0x888888))

    is_online  = status == "online"
    is_offline = status in ("offline", "")

    embed = discord.Embed(title="🎮  Create SMP", color=color)
    embed.add_field(name="📡 Status",   value=status_text,             inline=True)
    embed.add_field(name="👥 Players",  value=f"{players}/{maxplay}",  inline=True)
    embed.add_field(name="🌐 Address",  value=f"`{address}`",          inline=True)
    embed.add_field(name="⚙️ Software", value=f"{software} {version}", inline=True)
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
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, aternos_get_status)
    await update_status_message()

# ── Bot Ready ─────────────────────────────────────────────────────────────────
@bot.event
async def on_ready():
    print(f"[Bot] Logged in as {bot.user}")
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, aternos_login)
    await loop.run_in_executor(None, aternos_get_status)
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
    loop = asyncio.get_event_loop()

    try:
        if custom_id == "mc_start":
            ok = await loop.run_in_executor(None, lambda: aternos_action("start"))
            await interaction.followup.send(
                "✅ Perintah start dikirim! Tunggu ~2-5 menit (termasuk antrian Aternos)." if ok
                else "❌ Gagal mengirim perintah start.", ephemeral=True)

        elif custom_id == "mc_stop":
            ok = await loop.run_in_executor(None, lambda: aternos_action("stop"))
            await interaction.followup.send(
                "✅ Server sedang dimatikan..." if ok
                else "❌ Gagal mengirim perintah stop.", ephemeral=True)

        elif custom_id == "mc_restart":
            ok = await loop.run_in_executor(None, lambda: aternos_action("restart"))
            await interaction.followup.send(
                "✅ Server sedang restart..." if ok
                else "❌ Gagal mengirim perintah restart.", ephemeral=True)

        elif custom_id == "mc_backup":
            await interaction.followup.send(
                "💾 Backup manual: buka panel Aternos → **Backups** → Create Backup\n🔗 https://aternos.org/server/",
                ephemeral=True)

        await asyncio.sleep(3)
        await loop.run_in_executor(None, aternos_get_status)
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
