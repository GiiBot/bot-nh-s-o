import discord
from discord.ext import commands
from datetime import datetime, timedelta, timezone
import json, os, math, traceback

# ================= ENV =================
TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID", "0"))
VI_PHAM_ROLE_ID = int(os.getenv("VI_PHAM_ROLE_ID", "0"))

DATA_FILE = "data.json"
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
    except:
        pass

async def send_dm_violation(member, record, count):
    try:
        e = discord.Embed(
            title="🚨 THÔNG BÁO VI PHẠM",
            color=COLOR.get(min(count, 3), 0x992d22),
            timestamp=datetime.now(VN_TZ)
        )
        e.add_field(name="📌 Lỗi vi phạm", value=f"```{record['reason']}```", inline=False)
        e.add_field(name="⚠️ Mức kỷ luật", value=PENALTY.get(count, "—"), inline=False)
        e.add_field(name="⏳ Thời hạn", value=countdown(datetime.fromisoformat(record["deadline"])), inline=True)
        e.add_field(name="🧾 Mã bản án", value=record["case"], inline=True)
        e.set_footer(text=FOOTER, icon_url=ICON)
        await member.send(embed=e)
    except:
        pass

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

        try:
            await self.member.send(
                f"✅ **XÁC NHẬN HOÀN TẤT**\n🧾 Bản án `{self.record['case']}` đã được xác nhận **ĐÃ ĐÓNG**."
            )
        except:
            pass

        e = make_embed("✅ XÁC NHẬN ĐÃ ĐÓNG", 0x2ecc71)
        e.add_field(name="👤 Thành viên", value=self.member.mention, inline=False)
        await interaction.response.edit_message(embed=e, view=self)
        await send_log(e)

# ================= THONGKE VIEW (PAGINATION) =================
class ThongKeView(discord.ui.View):
    def __init__(self, rows, guild):
        super().__init__(timeout=120)
        self.rows = rows
        self.guild = guild
        self.page = 0
        self.max_page = math.ceil(len(rows) / PER_PAGE)

    def build_embed(self):
        start = self.page * PER_PAGE
        end = start + PER_PAGE

        e = make_embed(
            f"📊 THỐNG KÊ VI PHẠM – Trang {self.page+1}/{self.max_page}",
            0x3498db
        )

        for uid, total, unpaid, paid in self.rows[start:end]:
            member = self.guild.get_member(uid)
            name = member.display_name if member else f"User {uid}"

            e.add_field(
                name=name,
                value=f"📁 {total} sẹo | ❌ {unpaid} | ✅ {paid}",
                inline=False
            )

        return e

    @discord.ui.button(label="⬅️", style=discord.ButtonStyle.secondary)
    async def prev(self, interaction: discord.Interaction, _):
        if self.page > 0:
            self.page -= 1
            await interaction.response.edit_message(
                embed=self.build_embed(),
                view=self
            )
        else:
            await interaction.response.defer()

    @discord.ui.button(label="➡️", style=discord.ButtonStyle.secondary)
    async def next(self, interaction: discord.Interaction, _):
        if self.page < self.max_page - 1:
            self.page += 1
            await interaction.response.edit_message(
                embed=self.build_embed(),
                view=self
            )
        else:
            await interaction.response.defer()


# ================= MODAL =================
class GhiSeoModal(discord.ui.Modal, title="🚨 GHI VI PHẠM"):
    lydo = discord.ui.TextInput(label="Lỗi vi phạm", style=discord.TextStyle.paragraph)

    def __init__(self, member):
        super().__init__()
        self.member = member

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()

        u = get_user(self.member.id)

 # CHỈ ĐẾM SẸO CHƯA ĐÓNG
        active_seo = sum(1 for r in u if not r.get("paid"))
        count = active_seo + 1


        record = {
            "case": next_case(),
            "reason": self.lydo.value,
            "deadline": (datetime.now(VN_TZ) + timedelta(days=DEADLINE_DAYS)).isoformat(),
            "paid": False
        }
        u.append(record)
        save()

        if VI_PHAM_ROLE_ID:
            role = interaction.guild.get_role(VI_PHAM_ROLE_ID)
            if role:
                await self.member.add_roles(role, reason="Có vi phạm")

        await send_dm_violation(self.member, record, count)

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

@bot.tree.command(name="thongke", description="Thống kê tổng toàn bộ người bị sẹo")
async def thongke(interaction: discord.Interaction):
    rows = []
    total_users = 0
    total_seo = 0
    total_unpaid = 0
    total_paid = 0

    for uid, records in data["users"].items():
        total = len(records)
        if total == 0:
            continue

        unpaid = sum(1 for r in records if not r.get("paid"))
        paid = total - unpaid

        rows.append((int(uid), total, unpaid, paid))

        total_users += 1
        total_seo += total
        total_unpaid += unpaid
        total_paid += paid

    if not rows:
        return await interaction.response.send_message(
            "✨ Hiện tại **không có ai bị sẹo**",
            ephemeral=True
        )

    # Sắp xếp nhiều sẹo → ít sẹo
    rows.sort(key=lambda x: x[1], reverse=True)

    view = ThongKeView(rows, interaction.guild)
    embed = view.build_embed()

    # 🔥 PHẦN THỐNG KÊ TỔNG (HEADER)
    embed.title = "📊 THỐNG KÊ VI PHẠM TOÀN SERVER"
    embed.description = (
        f"👥 **Người bị sẹo:** {total_users}\n"
        f"📁 **Tổng sẹo:** {total_seo}\n"
        f"❌ **Chưa đóng:** {total_unpaid}\n"
        f"✅ **Đã đóng:** {total_paid}"
    )

    await interaction.response.send_message(
        embed=embed,
        view=view,
        ephemeral=True
    )


@bot.tree.command(name="topseo", description="Bảng xếp hạng vi phạm CIARA")
async def topseo(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)

    ranking = []
    for uid, records in data["users"].items():
        total = len(records)
        if total == 0:
            continue
        unpaid = sum(1 for r in records if not r.get("paid"))
        ranking.append((int(uid), total, unpaid, total - unpaid))

    if not ranking:
        return await interaction.followup.send("✨ Chưa có vi phạm nào")

    ranking.sort(key=lambda x: x[1], reverse=True)
    ranking = ranking[:10]

    e = discord.Embed(
        title="🏆 TOP VI PHẠM CIARA",
        color=0xe67e22,
        timestamp=datetime.now(VN_TZ)
    )
    e.set_footer(text=FOOTER, icon_url=ICON)

    medals = ["🥇", "🥈", "🥉"]

    for i, (uid, total, unpaid, paid) in enumerate(ranking):
        member = interaction.guild.get_member(uid)

        name = member.display_name if member else f"User {uid}"
        rank = medals[i] if i < 3 else f"#{i+1}"

        e.add_field(
            name=f"{rank} {name}",
            value=(
                f"📁 **Tổng sẹo:** {total}\n"
                f"❌ **Chưa đóng:** {unpaid}\n"
                f"✅ **Đã đóng:** {paid}"
            ),
            inline=False
        )

    await interaction.followup.send(embed=e)


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

    await interaction.response.send_message("🔄 Đang resync lệnh cho server...", ephemeral=True)
    guild = discord.Object(id=interaction.guild.id)
    synced = await bot.tree.sync(guild=guild)
    await interaction.followup.send(f"✅ Resync xong – {len(synced)} lệnh", ephemeral=True)

# ================= READY =================
@bot.event
async def on_ready():
    try:
        guild = discord.Object(id=GUILD_ID)
        synced = await bot.tree.sync(guild=guild)
        print(f"⚔️ CIARA BOT ONLINE | {len(synced)} slash commands")
    except Exception:
        traceback.print_exc()

bot.run(TOKEN)
