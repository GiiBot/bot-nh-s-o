import discord
from discord.ext import commands
from datetime import datetime, timedelta, timezone
import json, os, traceback

# ================= ENV =================
TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID", "0"))
VI_PHAM_ROLE_ID = int(os.getenv("VI_PHAM_ROLE_ID", "0"))

DATA_FILE = "data.json"
VN_TZ = timezone(timedelta(hours=7))
DEADLINE_DAYS = 7

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
bot = commands.Bot(command_prefix="!", intents=intents)

# ================= DATA =================
DEFAULT_DATA = {
    "config": {"log_channel": None},
    "case_id": 0,
    "users": {}
}

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

def countdown(deadline):
    diff = deadline - datetime.now(VN_TZ)
    if diff.total_seconds() <= 0:
        return "🔴 QUÁ HẠN"
    return f"⏳ {diff.days} ngày {diff.seconds // 3600} giờ"

def make_embed(title, color):
    e = discord.Embed(title=title, color=color, timestamp=datetime.now(VN_TZ))
    e.set_footer(text=FOOTER, icon_url=ICON)
    return e

async def send_log(embed):
    try:
        cid = data["config"].get("log_channel")
        if not cid:
            return
        ch = bot.get_channel(cid)
        if ch and ch.permissions_for(ch.guild.me).send_messages:
            await ch.send(embed=embed)
    except Exception as e:
        print("LOG ERROR:", e)

# ================= FAIL SAFE =================
@bot.tree.error
async def on_app_command_error(interaction, error):
    print("SLASH ERROR:", error)
    if interaction.response.is_done():
        await interaction.followup.send("❌ Bot gặp lỗi nội bộ", ephemeral=True)
    else:
        await interaction.response.send_message("❌ Bot gặp lỗi nội bộ", ephemeral=True)

# ================= CONFIRM VIEW =================
class ConfirmView(discord.ui.View):
    def __init__(self, member, record):
        super().__init__(timeout=None)
        self.member = member
        self.record = record

    @discord.ui.button(label="✅ ĐÃ ĐÓNG", style=discord.ButtonStyle.success)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_admin(interaction.user):
            return await interaction.response.send_message("❌ Admin only", ephemeral=True)

        if self.record.get("paid"):
            button.disabled = True
            return await interaction.response.edit_message(view=self)

        self.record["paid"] = True
        self.record["paid_at"] = datetime.now(VN_TZ).isoformat()
        save()

        button.disabled = True

        e = make_embed("✅ XÁC NHẬN ĐÃ ĐÓNG", 0x2ecc71)
        e.add_field(name="👤 Thành viên", value=self.member.mention, inline=False)

        await interaction.response.edit_message(embed=e, view=self)
        await send_log(e)

# ================= MODAL =================
class GhiSeoModal(discord.ui.Modal, title="⚔️ GHI VI PHẠM"):
    lydo = discord.ui.TextInput(label="Lỗi vi phạm", style=discord.TextStyle.paragraph)

    def __init__(self, member):
        super().__init__()
        self.member = member

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()

        u = get_user(self.member.id)
        count = len(u) + 1

        record = {
            "case": next_case(),
            "reason": self.lydo.value,
            "deadline": (datetime.now(VN_TZ) + timedelta(days=DEADLINE_DAYS)).isoformat(),
            "paid": False
        }
        u.append(record)
        save()

        # ADD ROLE VI PHẠM
        if VI_PHAM_ROLE_ID:
            role = interaction.guild.get_role(VI_PHAM_ROLE_ID)
            if role:
                await self.member.add_roles(role, reason="Có vi phạm")

        e = make_embed("🚨 VI PHẠM", COLOR.get(min(count, 3), 0x992d22))
        e.add_field(name="👤 Người vi phạm", value=self.member.mention, inline=False)
        e.add_field(name="📌 Lỗi vi phạm", value=f"```{record['reason']}```", inline=False)
        e.add_field(name="⚠️ Mức kỷ luật", value=PENALTY.get(count, "—"), inline=False)
        e.add_field(name="⏳ Thời hạn", value=countdown(datetime.fromisoformat(record["deadline"])), inline=True)
        e.add_field(name="🧾 Mã bản án", value=record["case"], inline=True)

        await interaction.followup.send(
            content=f"@everyone ⚠️ {self.member.mention}",
            embed=e,
            view=ConfirmView(self.member, record)
        )
        await send_log(e)

# ================= COMMANDS =================
@bot.tree.command(name="ghiseo")
async def ghiseo(interaction: discord.Interaction, member: discord.Member):
    if not is_admin(interaction.user):
        return await interaction.response.send_message("❌ Admin only", ephemeral=True)
    await interaction.response.send_modal(GhiSeoModal(member))

@bot.tree.command(name="thongke")
async def thongke(interaction: discord.Interaction, member: discord.Member | None = None):
    member = member or interaction.user
    u = get_user(member.id)

    total = len(u)
    unpaid = sum(1 for r in u if not r.get("paid"))
    paid = total - unpaid

    e = make_embed("📊 THỐNG KÊ VI PHẠM", 0x3498db)
    e.add_field(name="👤 Thành viên", value=member.mention, inline=False)
    e.add_field(name="📁 Tổng vi phạm", value=total)
    e.add_field(name="✅ Đã đóng", value=paid)
    e.add_field(name="❌ Chưa đóng", value=unpaid)

    await interaction.response.send_message(embed=e, ephemeral=True)
@bot.tree.command(name="topseo", description="Xem bảng xếp hạng vi phạm CIARA")
async def topseo(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)

    ranking = []

    for uid, records in data["users"].items():
        total = len(records)
        if total == 0:
            continue

        unpaid = sum(1 for r in records if not r.get("paid"))
        ranking.append((int(uid), total, unpaid))

    if not ranking:
        return await interaction.followup.send("✨ Hiện chưa có vi phạm nào")

    # Sắp xếp theo số sẹo giảm dần
    ranking.sort(key=lambda x: x[1], reverse=True)
    ranking = ranking[:10]

    e = make_embed("🏆 TOP VI PHẠM CIARA", 0xe67e22)

    medals = ["🥇", "🥈", "🥉"]

    for i, (uid, total, unpaid) in enumerate(ranking):
        member = int

@bot.tree.command(name="datkenhlog")
async def datkenhlog(interaction: discord.Interaction, kenh: discord.abc.GuildChannel):
    await interaction.response.defer(ephemeral=True)
    if not is_admin(interaction.user):
        return await interaction.followup.send("❌ Admin only")

    if not isinstance(kenh, discord.TextChannel):
        return await interaction.followup.send("❌ Chọn kênh text")

    data["config"]["log_channel"] = kenh.id
    save()
    await interaction.followup.send(f"✅ Đã đặt kênh log: {kenh.mention}")

@bot.tree.command(name="resync")
async def resync(interaction: discord.Interaction):
    if not is_admin(interaction.user):
        return await interaction.response.send_message("❌ Admin only", ephemeral=True)
    await interaction.response.defer(ephemeral=True)
    await bot.tree.sync()
    await interaction.followup.send("✅ Đã resync")

# ================= READY =================
@bot.event
async def on_ready():
    try:
        await bot.tree.sync()
        print("⚔️ CIARA BOT ONLINE")
    except Exception:
        traceback.print_exc()

bot.run(TOKEN)
