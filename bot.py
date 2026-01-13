import discord
from discord.ext import commands
from datetime import datetime, timedelta, timezone
import json, os, math, traceback, sqlite3, re

# ================= ENV =================
TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID", "0"))
VI_PHAM_ROLE_ID = int(os.getenv("VI_PHAM_ROLE_ID", "0"))
FUND_CHANNEL_ID = int(os.getenv("FUND_CHANNEL_ID", "0"))

BQT_ROLE_IDS = [
    int(x) for x in os.getenv("BQT_ROLE_ID", "").split(",")
    if x.strip().isdigit()
]

DATA_FILE = "data.json"
FUND_DB_FILE = "fund.db"

VN_TZ = timezone(timedelta(hours=7))
DEADLINE_DAYS = 7
PER_PAGE = 10

# ================= THEME =================
COLOR = {1: 0xFF6B6B, 2: 0xFF4757, 3: 0xC0392B}
FOOTER = "⚔️ LORD OF CIARA | KỶ LUẬT TẠO SỨC MẠNH"
ICON = "https://cdn-icons-png.flaticon.com/512/1695/1695213.png"

PENALTY = {
    1: "⚠️ Cảnh cáo",
    2: "💰 Đóng quỹ 500.000",
    3: "💸 Đóng quỹ 1.000.000",
    5: "👢 Kick crew",
    7: "⛔ Ban vĩnh viễn"
}

# ================= BOT =================
intents = discord.Intents.default()
intents.members = True
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# ================= DATA (SẸO) =================
DEFAULT_DATA = {"config": {"log_channel": None}, "case_id": 0, "users": {}}

def load():
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_DATA, f, indent=2, ensure_ascii=False)
        return DEFAULT_DATA.copy()
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

data = load()

# ================= DATABASE (QUỸ) =================
fund_conn = sqlite3.connect(FUND_DB_FILE)
fund_cur = fund_conn.cursor()

fund_cur.execute("""
CREATE TABLE IF NOT EXISTS fund (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    balance INTEGER NOT NULL
)
""")

fund_cur.execute("""
CREATE TABLE IF NOT EXISTS logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user TEXT,
    amount INTEGER,
    content TEXT,
    time TEXT
)
""")

fund_cur.execute("INSERT OR IGNORE INTO fund (id, balance) VALUES (1, 0)")
fund_conn.commit()

# ================= UTILS =================
def is_admin(m: discord.Member):
    return m.guild_permissions.administrator

def next_case():
    data["case_id"] += 1
    save()
    return f"#{data['case_id']:04d}"

def get_user(uid):
    uid = str(uid)
    if uid not in data["users"]:
        data["users"][uid] = []
        save()
    return data["users"][uid]

def format_money(x: int):
    return f"{x:,}".replace(",", ".")

# ================= ON MESSAGE (SỔ QUỸ) =================
@bot.event
async def on_message(message: discord.Message):
    # CHO PHÉP USER + BOT GHI QUỸ
    if message.channel.id != FUND_CHANNEL_ID:
        await bot.process_commands(message)
        return

    clean = message.content.replace(".", "")
    m = re.search(r"([+-])\s*(\d+)\s*([kKmM]?)", clean)
    if not m:
        await bot.process_commands(message)
        return

    sign, num, unit = m.groups()
    value = int(num)

    if unit.lower() == "k":
        value *= 1_000
    elif unit.lower() == "m":
        value *= 1_000_000
    if sign == "-":
        value = -value

    fund_cur.execute("SELECT balance FROM fund WHERE id=1")
    bal = fund_cur.fetchone()[0]
    new_bal = bal + value

    if new_bal < 0:
        return

    fund_cur.execute(
        "UPDATE fund SET balance=? WHERE id=1",
        (new_bal,)
    )

    # 🔥 FIX LỖI 5 CỘT – 4 VALUE (CHỈ RÕ TÊN CỘT)
    fund_cur.execute(
        "INSERT INTO logs (user, amount, content, time) VALUES (?,?,?,?)",
        (
            str(message.author),
            value,
            message.content,
            datetime.now(VN_TZ).strftime("%d/%m/%Y %H:%M")
        )
    )
    fund_conn.commit()

    embed = discord.Embed(
        title="📒 SỔ QUỸ CHIẾM ĐÓNG (ĐÃ CẬP NHẬT)",
        color=0x2ecc71 if value > 0 else 0xe74c3c,
        timestamp=datetime.now(VN_TZ)
    )
    embed.add_field(name="👤 Người ghi", value=message.author.mention, inline=False)
    embed.add_field(
        name="💰 Giao dịch",
        value=f"{value:+,}".replace(",", ".") + "$",
        inline=False
    )
    embed.add_field(
        name="📊 TỔNG QUỸ HIỆN TẠI",
        value=f"{format_money(new_bal)}$",
        inline=False
    )

    ping_roles = " ".join(f"<@&{rid}>" for rid in BQT_ROLE_IDS)

    await message.reply(
        content=f"🔔 {ping_roles}",
        embed=embed,
        allowed_mentions=discord.AllowedMentions(roles=True)
    )

    await bot.process_commands(message)

# ================= READY =================
@bot.tree.command(name="logquy", description="Xem lịch sử quỹ chiếm đóng")
async def logquy(interaction: discord.Interaction, limit: int = 10):
    if not is_admin(interaction.user):
        return await interaction.response.send_message(
            "❌ Admin only",
            ephemeral=True
        )

    fund_cur.execute(
        "SELECT user, amount, content, time FROM logs ORDER BY id DESC LIMIT ?",
        (limit,)
    )
    rows = fund_cur.fetchall()

    if not rows:
        return await interaction.response.send_message(
            "📭 Chưa có giao dịch nào",
            ephemeral=True
        )

    msg = ""
    for user, amount, content, time in rows:
        sign = "+" if amount > 0 else ""
        msg += (
            f"[{time}] {sign}{format_money(amount)}$\n"
            f"{user}\n"
            f"{content}\n\n"
        )

    await interaction.response.send_message(
        f"```{msg}```",
        ephemeral=True
    )

@bot.event
async def on_ready():
    try:
        guild = discord.Object(id=GUILD_ID)
        synced = await bot.tree.sync(guild=guild)
        print(f"⚔️ CIARA BOT ONLINE | {len(synced)} slash commands")
    except:
        traceback.print_exc()

bot.run(TOKEN)
