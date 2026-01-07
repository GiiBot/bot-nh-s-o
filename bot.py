import discord
from discord.ext import commands
from datetime import datetime
import json, os, traceback

# ================= ENV =================
TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID", "0"))
DATA_FILE = "data.json"

# ================= CIARA THEME =================
CIARA_LEVEL_COLOR = {
    1: 0x8B0000,
    2: 0xB30000,
    3: 0x0F0F0F
}

CIARA_FOOTER = "⚔️ LORD OF CIARA | KỶ LUẬT TẠO SỨC MẠNH"
CIARA_ICON = "https://cdn-icons-png.flaticon.com/512/1695/1695213.png"

CIARA_BANNER_BY_LEVEL = {
    1: "https://i.imgur.com/RED_LV1.png",
    2: "https://i.imgur.com/RED_LV2.png",
    3: "https://i.imgur.com/BLACK_LV3.png"
}

# ================= BOT =================
intents = discord.Intents.default()
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# ================= DATA =================
def load():
    if not os.path.exists(DATA_FILE):
        return {
            "config": {
                "log_channel": None,
                "scar_roles": {
                    "1": "Sẹo 1",
                    "2": "Sẹo 2",
                    "3": "Sẹo 3"
                }
            },
            "case_id": 0,
            "users": {}
        }
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    if "case_id" not in data:
        data["case_id"] = 0
    return data

def save(d):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(d, f, indent=2, ensure_ascii=False)

data = load()

def next_case_id():
    if "case_id" not in data:
        data["case_id"] = 0
    data["case_id"] += 1
    save(data)
    return f"#{data['case_id']:04d}"

def get_user(uid):
    uid = str(uid)
    if uid not in data["users"]:
        data["users"][uid] = []
    return data["users"][uid]

# ================= HELPERS =================
class SeoProfilePaginator(discord.ui.View):
    def __init__(self, user_id: int, page: int = 0):
        super().__init__(timeout=120)
        self.user_id = user_id
        self.page = page

    def build_embed(self, guild):
        records = data["users"].get(str(self.user_id), [])
        total = len(records)
        records = records[::-1]  # mới -> cũ

        member = guild.get_member(self.user_id)
        name = member.display_name if member else f"ID {self.user_id}"
        avatar = member.display_avatar.url if member else None

        r = records[self.page]

        embed = discord.Embed(
            title=f"🧬 HỒ SƠ SẸO – {name}",
            description=f"🧾 **Case `{r['case']}`**",
            color=CIARA_LEVEL_COLOR.get(min(total, 3), 0x8B0000)
        )

        embed.add_field(name="📌 Lý do", value=f"```{r['reason']}```", inline=False)
        embed.add_field(name="👤 Ghi bởi", value=r["by"])
        embed.add_field(name="🕒 Thời gian", value=r["time"])
        embed.add_field(name="☠️ Tổng sẹo", value=str(total), inline=False)

        if avatar:
            embed.set_thumbnail(url=avatar)

        banner = get_ciara_banner(total)
        if banner:
            embed.set_image(url=banner)

        embed.set_footer(
            text=f"{CIARA_FOOTER} • Trang {self.page + 1}/{total}",
            icon_url=CIARA_ICON
        )
        return embed

    @discord.ui.button(label="⬅️ Prev", style=discord.ButtonStyle.secondary)
    async def prev(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.page > 0:
            self.page -= 1
            await interaction.response.edit_message(
                embed=self.build_embed(interaction.guild),
                view=self
            )
        else:
            await interaction.response.defer()

    @discord.ui.button(label="➡️ Next", style=discord.ButtonStyle.secondary)
    async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
        records = data["users"].get(str(self.user_id), [])
        if self.page < len(records) - 1:
            self.page += 1
            await interaction.response.edit_message(
                embed=self.build_embed(interaction.guild),
                view=self
            )
        else:
            await interaction.response.defer()


class SeoProfileEntryView(discord.ui.View):
    def __init__(self, user_id: int):
        super().__init__(timeout=60)
        self.user_id = user_id

    @discord.ui.button(label="📄 Xem hồ sơ sẹo", style=discord.ButtonStyle.danger)
    async def open(self, interaction: discord.Interaction, button: discord.ui.Button):
        records = data["users"].get(str(self.user_id), [])
        if not records:
            return await interaction.response.send_message(
                "✨ Thành viên này không có hồ sơ sẹo.",
                ephemeral=True
            )

        paginator = SeoProfilePaginator(self.user_id)
        embed = paginator.build_embed(interaction.guild)

        await interaction.response.send_message(
            embed=embed,
            view=paginator,
            ephemeral=True
        )

def is_admin(member: discord.Member):
    return member.guild_permissions.administrator

def get_ciara_banner(scar_count: int):
    if scar_count >= 3:
        return CIARA_BANNER_BY_LEVEL[3]
    return CIARA_BANNER_BY_LEVEL.get(scar_count)

async def update_scar_roles(member, count):
    try:
        guild = member.guild
        scar_roles = data["config"]["scar_roles"]

        for rname in scar_roles.values():
            role = discord.utils.get(guild.roles, name=rname)
            if role and role in member.roles:
                await member.remove_roles(role)

        if count > 0:
            level = str(min(count, 3))
            role = discord.utils.get(guild.roles, name=scar_roles[level])
            if role:
                await member.add_roles(role)
    except Exception as e:
        print("❌ ROLE ERROR:", e)

async def safe_followup(interaction, **kwargs):
    try:
        await interaction.followup.send(**kwargs)
    except Exception as e:
        print("❌ FOLLOWUP ERROR:", e)

async def send_log(guild, embed):
    try:
        cid = data["config"].get("log_channel")
        if not cid:
            return
        ch = guild.get_channel(cid)
        if ch:
            await ch.send(embed=embed)
    except Exception as e:
        print("❌ LOG ERROR:", e)

async def send_dm_scar(member, embed):
    try:
        await member.send(embed=embed)
    except Exception:
        print("⚠️ User tắt DM")

# ================= READY (CLEAR + SYNC) =================
@bot.event
async def on_ready():
    try:
        if GUILD_ID:
            guild = discord.Object(id=GUILD_ID)
            await bot.tree.sync(guild=guild)
            print(f"🟢 Slash commands synced to guild {GUILD_ID}")
        else:
            await bot.tree.sync()
            print("🟢 Slash commands synced globally")
    except Exception as e:
        print("❌ SYNC ERROR:", e)

    print(f"🟢 CIARA SCAR BOT ONLINE: {bot.user}")


@bot.event
async def on_error(event, *args):
    traceback.print_exc()

# ================= MODAL =================
class GhiSeoModal(discord.ui.Modal, title="⚔️ GHI SẸO – LORD OF CIARA"):
    ly_do = discord.ui.TextInput(
        label="📌 Lý do vi phạm",
        style=discord.TextStyle.paragraph,
        placeholder="Nhập lý do ghi sẹo...",
        max_length=300,
        required=True
    )

    def __init__(self, member: discord.Member):
        super().__init__()
        self.member = member

    async def on_submit(self, interaction: discord.Interaction):
        await ghiseo_core(interaction, self.member, self.ly_do.value)

# ================= CORE =================
async def ghiseo_core(interaction, member, ly_do):
    await interaction.response.defer(ephemeral=False)

    if not is_admin(interaction.user):
        return await safe_followup(interaction, content="❌ Bạn không có quyền", ephemeral=True)

    u = get_user(member.id)
    case_id = next_case_id()

    u.append({
        "case": case_id,
        "reason": ly_do,
        "by": interaction.user.name,
        "time": datetime.now().strftime("%d/%m/%Y %H:%M")
    })
    save(data)

    scar_count = len(u)
    await update_scar_roles(member, scar_count)

    # ===== PUBLIC =====
    public_embed = discord.Embed(
        title="⚔️ GHI NHẬN SẸO – LORD OF CIARA",
        description="🩸 **Vết sẹo đã được ghi vào hồ sơ**",
        color=CIARA_LEVEL_COLOR.get(min(scar_count, 3), 0x8B0000)
    )
    public_embed.add_field(name="🧾 Case ID", value=case_id)
    public_embed.add_field(name="👤 Thành viên", value=member.mention, inline=False)
    public_embed.add_field(name="📌 Lý do", value=f"```{ly_do}```", inline=False)
    public_embed.add_field(name="☠️ Tổng sẹo", value=str(scar_count))
    public_embed.set_footer(text=CIARA_FOOTER, icon_url=CIARA_ICON)

    await safe_followup(
        interaction,
        content=f"@everyone ⚠️ {member.mention}",
        embed=public_embed
    )

    # ===== LOG =====
    log_embed = discord.Embed(
        title="📥 LOG SẸO – CIARA",
        color=CIARA_LEVEL_COLOR.get(min(scar_count, 3), 0x8B0000),
        timestamp=datetime.now()
    )
    log_embed.add_field(name="🧾 Case ID", value=case_id)
    log_embed.add_field(name="👤 Thành viên", value=f"{member} ({member.id})", inline=False)
    log_embed.add_field(name="✍️ Ghi bởi", value=interaction.user.mention)
    log_embed.add_field(name="📌 Lý do", value=f"```{ly_do}```", inline=False)
    log_embed.add_field(name="☠️ Tổng sẹo", value=str(scar_count))

    banner = get_ciara_banner(scar_count)
    if banner:
        log_embed.set_image(url=banner)

    log_embed.set_footer(text="CIARA | LOG HỆ THỐNG", icon_url=CIARA_ICON)
    await send_log(interaction.guild, log_embed)

    # ===== DM =====
    dm_embed = discord.Embed(
        title="⚔️ THÔNG BÁO KỶ LUẬT – CIARA",
        description="Bạn đã bị ghi nhận **1 vết sẹo**",
        color=CIARA_LEVEL_COLOR.get(min(scar_count, 3), 0x8B0000)
    )
    dm_embed.add_field(name="🧾 Case ID", value=case_id)
    dm_embed.add_field(name="📌 Lý do", value=f"```{ly_do}```", inline=False)
    dm_embed.add_field(name="☠️ Tổng sẹo", value=str(scar_count))
    dm_embed.set_footer(text=CIARA_FOOTER, icon_url=CIARA_ICON)

    await send_dm_scar(member, dm_embed)

# ================= COMMANDS =================
@bot.tree.command(name="ghiseo", description="⚔️ Ghi sẹo cho thành viên")
async def ghiseo(interaction: discord.Interaction, member: discord.Member):
    if not is_admin(interaction.user):
        return await interaction.response.send_message("❌ Bạn không có quyền", ephemeral=True)
    await interaction.response.send_modal(GhiSeoModal(member))

@bot.tree.command(name="goiseo", description="➖ Gỡ 1 sẹo")
async def goiseo(interaction: discord.Interaction, member: discord.Member):
    await interaction.response.defer()

    if not is_admin(interaction.user):
        return await safe_followup(interaction, content="❌ Bạn không có quyền", ephemeral=True)

    u = get_user(member.id)
    if not u:
        return await safe_followup(interaction, content="⚠️ Thành viên không có sẹo")

    u.pop()
    save(data)
    await update_scar_roles(member, len(u))
    await safe_followup(interaction, content=f"✅ Đã gỡ 1 sẹo cho {member.mention}")

@bot.tree.command(name="resetseo", description="♻️ Xoá sạch sẹo")
async def resetseo(interaction: discord.Interaction, member: discord.Member):
    await interaction.response.defer()

    if not is_admin(interaction.user):
        return await safe_followup(interaction, content="❌ Bạn không có quyền", ephemeral=True)

    data["users"][str(member.id)] = []
    save(data)
    await update_scar_roles(member, 0)
    await safe_followup(interaction, content=f"♻️ Đã reset sẹo cho {member.mention}")

@bot.tree.command(name="xemseo", description="👁️ Xem sẹo của bạn")
async def xemseo(interaction: discord.Interaction):
    u = get_user(interaction.user.id)
    if not u:
        return await interaction.response.send_message(
            "✨ Bạn là thành viên trong sạch của **LORD OF CIARA**",
            ephemeral=True
        )

    desc = "\n".join(
        f"🧾 `{v['case']}` | ⚠️ {v['reason']} _(by {v['by']})_"
        for v in u
    )

    embed = discord.Embed(
        title="👁️ HỒ SƠ SẸO CÁ NHÂN",
        description=desc,
        color=0x2980B9
    )
    embed.add_field(name="☠️ Tổng sẹo", value=str(len(u)))
    embed.set_footer(text=CIARA_FOOTER, icon_url=CIARA_ICON)

    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="datkenhlog", description="📥 Đặt kênh log sẹo")
async def datkenhlog(interaction: discord.Interaction, channel: discord.TextChannel):
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("❌ Chỉ Admin server", ephemeral=True)

    data["config"]["log_channel"] = channel.id
    save(data)
    await interaction.response.send_message(f"✅ Đã đặt kênh log tại {channel.mention}")
    @bot.tree.command(name="topseo", description="☠️ Bảng tử hình – BXH thành viên nhiều sẹo nhất")
async def topseo(interaction: discord.Interaction):
    try:
        ranking = []
        for uid, records in data["users"].items():
            if records:
                ranking.append((int(uid), len(records)))

        if not ranking:
            return await interaction.response.send_message(
                "✨ Hiện chưa có ai bị ghi sẹo.",
                ephemeral=True
            )

        ranking.sort(key=lambda x: x[1], reverse=True)
        ranking = ranking[:10]

        embed = discord.Embed(
            title="☠️ BẢNG TỬ HÌNH – LORD OF CIARA",
            color=0x0F0F0F
        )

        for i, (uid, count) in enumerate(ranking, start=1):
            member = interaction.guild.get_member(uid)
            name = member.display_name if member else f"ID {uid}"
            emoji = "☠️" if count >= 3 else "🩸"

            embed.add_field(
                name=f"#{i} {emoji} {name}",
                value=f"`{count}` sẹo",
                inline=False
            )

        embed.set_footer(text=CIARA_FOOTER, icon_url=CIARA_ICON)

        # 🔴 Button xem hồ sơ (TOP 1)
        view = SeoProfileEntryView(ranking[0][0])

        await interaction.response.send_message(embed=embed, view=view)

    except Exception as e:
        print("❌ TOPSEO ERROR:", e)
        await interaction.response.send_message(
            "⚠️ Không thể tạo bảng tử hình.",
            ephemeral=True
        )


# ================= START =================
if __name__ == "__main__":
    if not TOKEN:
        print("❌ DISCORD_TOKEN chưa được thiết lập")
    else:
        bot.run(TOKEN)
