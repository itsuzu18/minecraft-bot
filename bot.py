import os
import asyncio
import discord
from discord.ext import commands, tasks
from discord import app_commands
from python_aternos import Client as AternosClient
from dotenv import load_dotenv

load_dotenv()

# ── Config ──────────────────────────────────────────────────────────────────
DISCORD_TOKEN    = os.getenv("DISCORD_TOKEN")
CHANNEL_ID       = int(os.getenv("CHANNEL_ID"))
ATERNOS_USER     = os.getenv("ATERNOS_USER")
ATERNOS_PASS     = os.getenv("ATERNOS_PASS")
SERVER_NAME      = os.getenv("SERVER_NAME")  # nama server di aternos (itzuchi, dll)

# ── Setup Bot ────────────────────────────────────────────────────────────────
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# State global
aternos_server = None
status_message_id = None

# ── Connect ke Aternos ───────────────────────────────────────────────────────
def get_aternos_server():
    global aternos_server
    try:
        client = AternosClient.from_credentials(ATERNOS_USER, ATERNOS_PASS)
        servers = client.list_servers()
        for s in servers:
            if SERVER_NAME.lower() in s.address.lower():
                aternos_server = s
                return s
        # Kalau tidak ditemukan, ambil server pertama
        aternos_server = servers[0]
        return servers[0]
    except Exception as e:
        print(f"[Aternos] Error connecting: {e}")
        return None

# ── Build Embed Status ───────────────────────────────────────────────────────
def build_embed_and_buttons(server=None):
    if server is None:
        server = aternos_server

    # Ambil info server
    try:
        status    = server.status        # online, offline, starting, stopping
        address   = server.address
        players   = server.players_on
        max_play  = server.players_max
        software  = server.software
        version   = server.version
    except Exception:
        status    = "offline"
        address   = "unknown"
        players   = 0
        max_play  = 20
        software  = "Forge"
        version   = "1.20.1"

    # Status styling
    status_map = {
        "online":   ("🟢 Online",   0x00ff88),
        "offline":  ("🔴 Offline",  0xff4444),
        "starting": ("🟡 Starting…", 0xffcc00),
        "stopping": ("🟠 Stopping…", 0xff8800),
        "loading":  ("🟡 Loading…",  0xffcc00),
        "saving":   ("🟠 Saving…",   0xff8800),
    }
    status_text, color = status_map.get(status, ("⚪ Unknown", 0x888888))

    is_online  = status == "online"
    is_offline = status == "offline"

    embed = discord.Embed(
        title="🎮  Create SMP",
        color=color
    )
    embed.add_field(name="📡 Status",   value=status_text,                    inline=True)
    embed.add_field(name="👥 Players",  value=f"{players}/{max_play}",        inline=True)
    embed.add_field(name="🌐 Address",  value=f"`{address}`",                 inline=True)
    embed.add_field(name="⚙️ Software", value=f"{software} {version}",        inline=True)
    embed.set_footer(text="Auto-update tiap 30 detik • Create SMP")
    embed.timestamp = discord.utils.utcnow()

    # Tombol
    row = discord.ui.View(timeout=None)

    start_btn = discord.ui.Button(
        label="Start", emoji="▶️",
        style=discord.ButtonStyle.success,
        custom_id="mc_start",
        disabled=not is_offline
    )
    stop_btn = discord.ui.Button(
        label="Stop", emoji="⏹️",
        style=discord.ButtonStyle.danger,
        custom_id="mc_stop",
        disabled=not is_online
    )
    restart_btn = discord.ui.Button(
        label="Restart", emoji="🔄",
        style=discord.ButtonStyle.primary,
        custom_id="mc_restart",
        disabled=not is_online
    )
    backup_btn = discord.ui.Button(
        label="Backup", emoji="💾",
        style=discord.ButtonStyle.secondary,
        custom_id="mc_backup",
        disabled=not is_online
    )

    row.add_item(start_btn)
    row.add_item(stop_btn)
    row.add_item(restart_btn)
    row.add_item(backup_btn)

    return embed, row

# ── Update Pesan Status ──────────────────────────────────────────────────────
async def update_status_message():
    global status_message_id, aternos_server
    try:
        channel = bot.get_channel(CHANNEL_ID)
        if channel is None:
            channel = await bot.fetch_channel(CHANNEL_ID)

        # Refresh data server dari Aternos
        if aternos_server:
            try:
                aternos_server.fetch()
            except Exception:
                pass

        embed, view = build_embed_and_buttons()

        if status_message_id:
            try:
                msg = await channel.fetch_message(status_message_id)
                await msg.edit(embed=embed, view=view)
                return
            except discord.NotFound:
                status_message_id = None

        # Kirim pesan baru
        msg = await channel.send(embed=embed, view=view)
        status_message_id = msg.id

    except Exception as e:
        print(f"[Status] Error updating: {e}")

# ── Loop Auto-Update ─────────────────────────────────────────────────────────
@tasks.loop(seconds=30)
async def auto_update():
    await update_status_message()

# ── Event: Bot Ready ─────────────────────────────────────────────────────────
@bot.event
async def on_ready():
    global aternos_server
    print(f"✅ Bot online: {bot.user}")

    # Connect ke Aternos
    print("[Aternos] Connecting...")
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, get_aternos_server)

    if aternos_server:
        print(f"[Aternos] Connected to server: {aternos_server.address}")
    else:
        print("[Aternos] ⚠️ Gagal connect ke server Aternos!")

    # Kirim status pertama kali
    await update_status_message()

    # Mulai auto-update
    if not auto_update.is_running():
        auto_update.start()

# ── Event: Tombol Diklik ─────────────────────────────────────────────────────
@bot.event
async def on_interaction(interaction: discord.Interaction):
    if interaction.type != discord.InteractionType.component:
        return

    custom_id = interaction.data.get("custom_id", "")
    if not custom_id.startswith("mc_"):
        return

    await interaction.response.defer(ephemeral=True)

    if aternos_server is None:
        await interaction.followup.send("❌ Bot belum terhubung ke Aternos. Coba restart bot.", ephemeral=True)
        return

    loop = asyncio.get_event_loop()

    try:
        if custom_id == "mc_start":
            await loop.run_in_executor(None, aternos_server.start)
            await interaction.followup.send(
                "✅ **Server sedang dinyalakan!**\nTunggu ~2-5 menit (termasuk antrian Aternos).",
                ephemeral=True
            )

        elif custom_id == "mc_stop":
            await loop.run_in_executor(None, aternos_server.stop)
            await interaction.followup.send("✅ **Server sedang dimatikan...**", ephemeral=True)

        elif custom_id == "mc_restart":
            await loop.run_in_executor(None, aternos_server.restart)
            await interaction.followup.send("✅ **Server sedang restart...**", ephemeral=True)

        elif custom_id == "mc_backup":
            # Aternos tidak punya API backup langsung, kirim link panel
            await interaction.followup.send(
                "💾 **Backup manual:**\nBuka panel Aternos → **Backups** → Create Backup\n"
                f"🔗 https://aternos.org/server/",
                ephemeral=True
            )

        # Update embed setelah aksi
        await asyncio.sleep(3)
        await update_status_message()

    except Exception as e:
        print(f"[Button] Error {custom_id}: {e}")
        await interaction.followup.send(f"❌ Error: `{str(e)}`", ephemeral=True)

# ── Run Bot ──────────────────────────────────────────────────────────────────
bot.run(DISCORD_TOKEN)
