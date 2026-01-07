import discord
from discord.ext import commands
from datetime import datetime, timezone, timedelta
import json, os

# ================= ENV =================
TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID", "0"))
DATA_FILE = "data.json"
VN_TZ = timezone(timedelta(hours=7))

# ================= THEME =================
CIARA_LEVEL_COLOR = {1: 0x8B0000, 2: 0xB30000, 3: 0x0F0F0F}
CIARA_FOOTER = "⚔️ LORD OF CIARA | KỶ LUẬT TẠO SỨC MẠNH"
CIARA_ICON = "https://cdn-icons-png.flaticon.com/512/1695/1695213.png"
CIARA_BANNER_BY_LEVEL = {
    1: "https://i.imgur.com/RED_LV1.png",
    2: "https://i.imgur.com/RED_LV2.png",
    3: "https://i.imgur.com/BLACK_LV3.png"
}

# ================= PENALTY =================
PENALTY_RULES = {
    2: "🔨 Đóng quỹ 400IG",
    3: "⛓️ Đóng quỹ 1m IG",
    5: "👢 Kick khỏi crew",
    7: "🔨 Ban vĩnh viễn"
}

# ================= BOT =================
intents = discord.Intents.default()
intents.guilds = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

# ================= SAFE DEFER =================
async def safe_defer(interaction: discord.Interaction, ephemeral=False):
    try:
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=ephemeral)
    except:
        pass

# ================= DATA =================
def load():
    if not os.path.exists(DATA_FILE):
        return {
            "config": {
                "log_channel": None,
                "scar_roles": {"1": "Sẹo 1", "2": "Sẹo 2", "3": "Sẹo 3"}
            },
            "case_id": 0,
            "users": {},
            "admin_logs": []
        }
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

data = load()

def next_case_id():
    data["case_id"] += 1
    save()
    return f"#{data['case_id']:04d}"

def get_user(uid):
    uid = str(uid)
    if uid not in data["users"]:
        data["users"][uid] = []
        save()
    return data["users"][uid]

def is_admin(member: discord.Member):
    return member.guild_permissions.administrator

# ================= HELPERS =================
def get_ciara_banner(count):
    return CIARA_BANNER_BY_LEVEL.get(min(count, 3))

async def update_scar_roles(member, count):
    for r in data["config"]["scar_roles"].values():
        role = discord.utils.get(member.guild.roles, name=r)
        if role and role in member.roles:
            await member.remove_roles(role)

    if count > 0:
        role = discord.utils.get(
            member.guild.roles,
            name=data["config"]["scar_roles"][str(min(count, 3))]
        )
        if role:
            await member.add_roles(role)

async def send_log(guild, embed):
    cid = data["config"].get("log_channel")
    if cid:
        ch = guild.get_channel(cid)
        if ch:
            await ch.send(embed=embed)

async def send_dm(member, embed):
    try:
        await member.send(embed=embed)
    except:
        pass

# ================= PAGINATOR =================
class SeoProfilePaginator(discord.ui.View):
    def __init__(self, uid, page=0):
        super().__init__(timeout=120)
        self.uid = uid
        self.page = page

    async def interaction_check(self, interaction):
        return interaction.user.id == self.uid or is_admin(interaction.user)

    def build(self, guild):
        records = data["users"][str(self.uid)][::-1]
        self.page = max(0, min(self.page, len(records)-1))
        r = records[self.page]

        m = guild.get_member(self.uid)
        total = len(records)

        embed = discord.Embed(
            title=f"🧬 HỒ SƠ SẸO | {m.display_name if m else self.uid}",
            description=f"☠️ **Tổng:** `{total}` • 🧾 **Case:** `{r['case']}`",
            color=CIARA_LEVEL_COLOR.get(min(total,3))
        )

        embed.add_field(name="📌 Lý do", value=f"> {r['reason']}", inline=False)
        embed.add_field(name="👤 Ghi bởi", value=r["by"], inline=True)
        embed.add_field(name="🕒 Thời gian", value=r["time"], inline=True)

        banner = get_ciara_banner(total)
        if banner:
            embed.set_image(url=banner)

        embed.set_footer(text=f"{CIARA_FOOTER} • Trang {self.page+1}/{total}", icon_url=CIARA_ICON)
        return embed

    @discord.ui.button(label="⬅️", style=discord.ButtonStyle.secondary)
    async def prev(self, interaction, _):
        self.page -= 1
        await interaction.response.edit_message(embed=self.build(interaction.guild), view=self)

    @discord.ui.button(label="➡️", style=discord.ButtonStyle.secondary)
    async def next(self, interaction, _):
        self.page += 1
        await interaction.response.edit_message(embed=self.build(interaction.guild), view=self)

# ================= TOPSEO VIEW =================
class TopSeoSelectView(discord.ui.View):
    def __init__(self, ranking):
        super().__init__(timeout=60)
        self.select = discord.ui.Select(
            placeholder="☠️ Chọn người để xem hồ sơ",
            options=[
                discord.SelectOption(
                    label=f"{c} sẹo",
                    description=f"ID {u}",
                    value=str(u),
                    emoji="☠️"
                ) for u,c in ranking
            ]
        )
        self.select.callback = self.cb
        self.add_item(self.select)

    async def cb(self, interaction):
        uid = int(self.select.values[0])
        p = SeoProfilePaginator(uid)
        await interaction.response.send_message(embed=p.build(interaction.guild), view=p, ephemeral=True)

# ================= MODAL =================
class GhiSeoModal(discord.ui.Modal, title="⚔️ GHI SẸO – CIARA"):
    ly_do = discord.ui.TextInput(label="Lý do vi phạm", style=discord.TextStyle.paragraph)

    def __init__(self, member):
        super().__init__()
        self.member = member

    async def on_submit(self, interaction):
        await safe_defer(interaction, True)

        u = get_user(self.member.id)
        cid = next_case_id()
        week = datetime.now(VN_TZ).isocalendar()[1]

        u.append({
            "case": cid,
            "reason": self.ly_do.value,
            "by": interaction.user.name,
            "time": datetime.now(VN_TZ).strftime("%d/%m/%Y %H:%M"),
            "week": week
        })
        save()

        await update_scar_roles(self.member, len(u))

        embed = discord.Embed(
            title="⚔️ CIARA DISCIPLINE REPORT",
            description=f"{self.member.mention}\n🧾 `{cid}` • ☠️ `{len(u)}` sẹo",
            color=CIARA_LEVEL_COLOR.get(min(len(u),3))
        )
        embed.add_field(name="📌 Lý do", value=f"> {self.ly_do.value}", inline=False)

        if len(u) in PENALTY_RULES:
            embed.add_field(name="⚠️ Hình phạt", reminding:=PENALTY_RULES[len(u)], inline=False)

        data["admin_logs"].append({
            "action":"ghiseo",
            "admin":interaction.user.name,
            "target":self.member.id,
            "time":datetime.now(VN_TZ).strftime("%d/%m %H:%M")
        })
        save()

        await interaction.followup.send(f"@everyone ⚠️ {self.member.mention}", embed=embed)
        await send_log(interaction.guild, embed)
        await send_dm(self.member, embed)

# ================= SLASH COMMANDS =================
@bot.tree.command(name="ghiseo")
async def ghiseo(interaction, member: discord.Member):
    if not is_admin(interaction.user):
        return await interaction.response.send_message("❌ Admin only", ephemeral=True)
    await interaction.response.send_modal(GhiSeoModal(member))

@bot.tree.command(name="goiseo")
async def goiseo(interaction, member: discord.Member):
    await safe_defer(interaction, True)
    if not is_admin(interaction.user):
        return await interaction.followup.send("❌ Admin only", ephemeral=True)

    u = get_user(member.id)
    if not u:
        return await interaction.followup.send("⚠️ Không có sẹo", ephemeral=True)

    r = u.pop()
    save()
    await update_scar_roles(member, len(u))

    data["admin_logs"].append({
        "action":"goiseo","admin":interaction.user.name,
        "target":member.id,
        "time":datetime.now(VN_TZ).strftime("%d/%m %H:%M")
    })
    save()

    await interaction.followup.send(f"✅ Đã gỡ sẹo `{r['case']}` cho {member.mention}", ephemeral=True)

@bot.tree.command(name="resetseo")
async def resetseo(interaction, member: discord.Member):
    await safe_defer(interaction, True)
    if not is_admin(interaction.user):
        return await interaction.followup.send("❌ Admin only", ephemeral=True)

    data["users"][str(member.id)] = []
    save()
    await update_scar_roles(member, 0)

    data["admin_logs"].append({
        "action":"resetseo","admin":interaction.user.name,
        "target":member.id,
        "time":datetime.now(VN_TZ).strftime("%d/%m %H:%M")
    })
    save()

    await interaction.followup.send(f"♻️ Đã reset sẹo cho {member.mention}", ephemeral=True)

@bot.tree.command(name="xemseo")
async def xemseo(interaction):
    await safe_defer(interaction, True)
    u = get_user(interaction.user.id)
    if not u:
        return await interaction.followup.send("✨ Bạn là công dân sạch", ephemeral=True)
    p = SeoProfilePaginator(interaction.user.id)
    await interaction.followup.send(embed=p.build(interaction.guild), view=p, ephemeral=True)

@bot.tree.command(name="topseo")
async def topseo(interaction):
    await safe_defer(interaction)
    ranking = [(int(uid), len(v)) for uid,v in data["users"].items() if v]
    if not ranking:
        return await interaction.followup.send("✨ Chưa có ai bị ghi sẹo", ephemeral=True)

    ranking.sort(key=lambda x:x[1], reverse=True)
    ranking = ranking[:10]

    embed = discord.Embed(title="☠️ BẢNG TỬ HÌNH", color=0x0F0F0F)
    for i,(uid,c) in enumerate(ranking,1):
        m = interaction.guild.get_member(uid)
        embed.add_field(name=f"#{i} {m.display_name if m else uid}", value=f"{c} sẹo", inline=False)

    await interaction.followup.send(embed=embed, view=TopSeoSelectView(ranking))

@bot.tree.command(name="thongke")
async def thongke(interaction):
    await safe_defer(interaction)
    week = datetime.now(VN_TZ).isocalendar()[1]
    stats = {}
    for uid,rs in data["users"].items():
        for r in rs:
            if r["week"]==week:
                stats[uid]=stats.get(uid,0)+1
    if not stats:
        return await interaction.followup.send("✨ Tuần này không có vi phạm", ephemeral=True)

    embed = discord.Embed(title=f"📊 THỐNG KÊ TUẦN {week}", color=0xB30000)
    for uid,c in stats.items():
        m = interaction.guild.get_member(int(uid))
        embed.add_field(name=m.display_name if m else uid, value=f"{c} sẹo", inline=False)

    await interaction.followup.send(embed=embed)

@bot.tree.command(name="lichsuadmin")
async def lichsuadmin(interaction):
    await safe_defer(interaction, True)
    if not is_admin(interaction.user):
        return await interaction.followup.send("❌ Admin only", ephemeral=True)

    embed = discord.Embed(title="🧾 LỊCH SỬ ADMIN", color=0x0F0F0F)
    for l in data["admin_logs"][-10:]:
        embed.add_field(name=l["action"], value=f"{l['admin']} → {l['target']} ({l['time']})", inline=False)

    await interaction.followup.send(embed=embed, ephemeral=True)

@bot.tree.command(name="datkenhlog")
async def datkenhlog(interaction, channel: discord.TextChannel):
    await safe_defer(interaction, True)
    if not is_admin(interaction.user):
        return await interaction.followup.send("❌ Admin only", ephemeral=True)
    data["config"]["log_channel"]=channel.id
    save()
    await interaction.followup.send(f"✅ Đã đặt kênh log: {channel.mention}", ephemeral=True)

# ================= READY =================
@bot.event
async def on_ready():
    await bot.tree.sync(guild=discord.Object(id=GUILD_ID) if GUILD_ID else None)
    print(f"⚔️ CIARA BOT ONLINE: {bot.user}")

bot.run(TOKEN)
