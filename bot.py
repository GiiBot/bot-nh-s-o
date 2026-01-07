import discord
from discord.ext import commands, tasks
from datetime import datetime, timedelta, timezone
import json, os

# ================= ENV =================
TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID", "0"))
DATA_FILE = "data.json"
VN_TZ = timezone(timedelta(hours=7))
DEADLINE_DAYS = 7

# ================= THEME =================
COLOR = {1: 0x8B0000, 2: 0xB30000, 3: 0x0F0F0F}
FOOTER = "⚔️ LORD OF CIARA | KỶ LUẬT TẠO SỨC MẠNH"
ICON = "https://cdn-icons-png.flaticon.com/512/1695/1695213.png"

# ================= PENALTY =================
PENALTY = {
    1: "Cảnh cáo",
    2: "Đóng quỹ 500k IG",
    3: "Đóng quỹ 1.000.000 IG",
    5: "Kick khỏi crew",
    7: "Ban vĩnh viễn"
}

# ================= BOT =================
intents = discord.Intents.default()
intents.guilds = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

# ================= DATA =================
def load():
    if not os.path.exists(DATA_FILE):
        return {"config": {"log_channel": None}, "case_id": 0, "users": {}, "admin_logs": []}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

data = load()

# ================= UTILS =================
def is_admin(m): return m.guild_permissions.administrator

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
    now = datetime.now(VN_TZ)
    diff = deadline - now
    if diff.total_seconds() <= 0:
        return "🔴 **QUÁ HẠN**"
    d = diff.days
    h = diff.seconds // 3600
    return f"⏳ Còn **{d} ngày {h} giờ**"

def ciara_embed(title, desc, color):
    e = discord.Embed(title=title, description=desc, color=color)
    e.set_footer(text=FOOTER, icon_url=ICON)
    return e

# ================= AUTO PING TASK =================
@tasks.loop(hours=6)
async def auto_ping_unpaid():
    guild = bot.get_guild(GUILD_ID)
    if not guild:
        return

    for uid, records in data["users"].items():
        member = guild.get_member(int(uid))
        if not member:
            continue
        for r in records:
            if not r["paid"]:
                deadline = datetime.fromisoformat(r["deadline"])
                if (deadline - datetime.now(VN_TZ)).days <= 1:
                    try:
                        await member.send(
                            f"🔔 **NHẮC ĐÓNG PHẠT CIARA**\n"
                            f"🧾 Case `{r['case']}`\n"
                            f"{countdown(deadline)}"
                        )
                    except:
                        pass

# ================= VIEW CONFIRM =================
class ConfirmPaidView(discord.ui.View):
    def __init__(self, member, record):
        super().__init__(timeout=60)
        self.member = member
        self.record = record

    @discord.ui.button(label="✅ ĐÃ ĐÓNG", style=discord.ButtonStyle.success)
    async def confirm(self, interaction, _):
        if not is_admin(interaction.user):
            return await interaction.response.send_message("❌ Admin only", ephemeral=True)
        self.record["paid"] = True
        self.record["paid_note"] = "Đã đóng đủ"
        save()
        await interaction.response.edit_message(
            embed=ciara_embed(
                "✅ ĐÃ XÁC NHẬN ĐÓNG PHẠT",
                f"{self.member.mention} đã hoàn tất hình phạt RP",
                0x27ae60
            ),
            view=None
        )

    @discord.ui.button(label="❌ HỦY", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction, _):
        await interaction.response.edit_message(content="❌ Đã hủy", view=None)

# ================= COMMANDS =================
@bot.tree.command(name="ghiseo")
async def ghiseo(interaction, member: discord.Member):
    if not is_admin(interaction.user):
        return await interaction.response.send_message("❌ Admin only", ephemeral=True)

    modal = discord.ui.Modal(title="⚔️ GHI SẸO CIARA")
    lydo = discord.ui.TextInput(label="Lý do vi phạm", style=discord.TextStyle.paragraph)
    modal.add_item(lydo)

    async def on_submit(i):
        record = {
            "case": next_case(),
            "reason": lydo.value,
            "by": i.user.name,
            "created_at": datetime.now(VN_TZ).isoformat(),
            "deadline": (datetime.now(VN_TZ) + timedelta(days=DEADLINE_DAYS)).isoformat(),
            "paid": False,
            "paid_note": ""
        }
        get_user(member.id).append(record)
        save()

        embed = ciara_embed(
            "⚔️ CIARA DISCIPLINE REPORT",
            f"👤 {member.mention}\n🧾 `{record['case']}`\n"
            f"📌 ```{record['reason']}```\n"
            f"🚨 **{PENALTY.get(len(get_user(member.id)), '—')}**\n"
            f"{countdown(datetime.fromisoformat(record['deadline']))}",
            COLOR.get(min(len(get_user(member.id)), 3))
        )
        await i.response.send_message(f"@everyone ⚠️ {member.mention}", embed=embed)

    modal.on_submit = on_submit
    await interaction.response.send_modal(modal)

@bot.tree.command(name="xemseo")
async def xemseo(interaction):
    u = get_user(interaction.user.id)
    if not u:
        return await interaction.response.send_message("✨ Bạn sạch sẹo", ephemeral=True)
    r = u[-1]
    embed = ciara_embed(
        "🧬 HỒ SƠ SẸO",
        f"🧾 `{r['case']}`\n📌 ```{r['reason']}```\n"
        f"{countdown(datetime.fromisoformat(r['deadline']))}",
        COLOR.get(min(len(u), 3))
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="xacnhanphat")
async def xacnhanphat(interaction, member: discord.Member):
    if not is_admin(interaction.user):
        return await interaction.response.send_message("❌ Admin only", ephemeral=True)
    u = get_user(member.id)
    if not u:
        return await interaction.response.send_message("⚠️ Không có sẹo", ephemeral=True)
    await interaction.response.send_message(
        embed=ciara_embed("XÁC NHẬN ĐÓNG PHẠT", f"{member.mention}", 0xf1c40f),
        view=ConfirmPaidView(member, u[-1])
    )

@bot.tree.command(name="dashboard")
async def dashboard(interaction):
    total_case = sum(len(v) for v in data["users"].values())
    unpaid = sum(1 for v in data["users"].values() for r in v if not r["paid"])
    embed = ciara_embed(
        "📊 DASHBOARD CIARA",
        f"📁 Tổng case: **{total_case}**\n"
        f"❌ Chưa đóng phạt: **{unpaid}**",
        0x3498db
    )
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="resync")
async def resync(interaction):
    if not is_admin(interaction.user):
        return await interaction.response.send_message("❌ Admin only", ephemeral=True)
    guild = discord.Object(id=GUILD_ID)
    bot.tree.clear_commands(guild=guild)
    await bot.tree.sync(guild=guild)
    await interaction.response.send_message("✅ Đã resync", ephemeral=True)

# ================= READY =================
@bot.event
async def on_ready():
    guild = discord.Object(id=GUILD_ID)
    bot.tree.clear_commands(guild=guild)
    await bot.tree.sync(guild=guild)
    auto_ping_unpaid.start()
    print("⚔️ CIARA BOT ONLINE")

bot.run(TOKEN)
