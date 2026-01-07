import discord
from discord.ext import commands
from datetime import datetime
import json, os, traceback

# ================= CONFIG =================
TOKEN = os.getenv("DISCORD_TOKEN")
DATA_FILE = "data.json"

# ================= CIARA THEME =================
CIARA_LEVEL_COLOR = {
    1: 0x8B0000,  # đỏ sẫm
    2: 0xB30000,  # đỏ máu
    3: 0x0F0F0F   # đen
}

CIARA_FOOTER = "⚔️ LORD OF CIARA | KỶ LUẬT TẠO SỨC MẠNH"
CIARA_ICON = "https://cdn-icons-png.flaticon.com/512/1695/1695213.png"

# ================= INTENTS =================
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
        return json.load(f)

def save(d):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(d, f, indent=2, ensure_ascii=False)

data = load()

def next_case_id():
    data["case_id"] += 1
    save(data)
    return f"#{data['case_id']:04d}"

# ================= HELPERS =================
def is_admin(member: discord.Member):
    # ✅ CÁCH 3: DÙNG QUYỀN ADMIN DISCORD
    return member.guild_permissions.administrator

def get_user(uid):
    uid = str(uid)
    if uid not in data["users"]:
        data["users"][uid] = []
    return data["users"][uid]

async def update_scar_roles(member, count):
    guild = member.guild
    scar_roles = data["config"]["scar_roles"]

    # gỡ role cũ
    for rname in scar_roles.values():
        role = discord.utils.get(guild.roles, name=rname)
        if role and role in member.roles:
            await member.remove_roles(role)

    # gán role mới
    if count > 0:
        level = str(min(count, 3))
        role_name = scar_roles.get(level)
        role = discord.utils.get(guild.roles, name=role_name)
        if role:
            await member.add_roles(role)

async def send_log(guild, embed):
    cid = data["config"]["log_channel"]
    if cid:
        ch = guild.get_channel(cid)
        if ch:
            await ch.send(embed=embed)

# ================= READY =================
@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"🟢 CIARA SCAR BOT ONLINE: {bot.user}")

@bot.event
async def on_error(event, *args):
    traceback.print_exc()

# ================= COMMANDS =================

@bot.tree.command(name="ghiseo", description="⚔️ Ghi sẹo cho thành viên")
async def ghiseo(interaction: discord.Interaction, member: discord.Member, ly_do: str):
    await interaction.response.defer()  # 🔴 FIX TIMEOUT

    if not is_admin(interaction.user):
        return await interaction.followup.send("❌ Bạn không có quyền", ephemeral=True)

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

    color = CIARA_LEVEL_COLOR.get(min(scar_count, 3), 0x8B0000)

    embed = discord.Embed(
        title="⚔️ GHI NHẬN SẸO – LORD OF CIARA",
        description="🩸 **Một vết sẹo đã được khắc lên hồ sơ kỷ luật**",
        color=color
    )
    embed.add_field(name="🧾 Case ID", value=f"`{case_id}`", inline=True)
    embed.add_field(name="👤 Thành viên", value=member.mention, inline=False)
    embed.add_field(name="📌 Lý do", value=f"```{ly_do}```", inline=False)
    embed.add_field(name="☠️ Tổng sẹo", value=f"**{scar_count}**", inline=True)
    embed.set_footer(text=CIARA_FOOTER, icon_url=CIARA_ICON)

    await interaction.followup.send(embed=embed)
    await send_log(interaction.guild, embed)

@bot.tree.command(name="goiseo", description="➖ Gỡ 1 sẹo cho thành viên")
async def goiseo(interaction: discord.Interaction, member: discord.Member):
    await interaction.response.defer()  # 🔴 FIX TIMEOUT

    if not is_admin(interaction.user):
        return await interaction.followup.send("❌ Bạn không có quyền", ephemeral=True)

    u = get_user(member.id)
    if not u:
        return await interaction.followup.send("⚠️ Thành viên không có sẹo")

    u.pop()
    save(data)
    await update_scar_roles(member, len(u))

    embed = discord.Embed(
        title="🔥 GIẢM SẸO – CIARA XÁC NHẬN",
        description="🥀 **Một vết sẹo đã được xoá khỏi hồ sơ**",
        color=0x1ABC9C
    )
    embed.add_field(name="👤 Thành viên", value=member.mention)
    embed.add_field(name="⚖️ Sẹo còn lại", value=f"**{len(u)}**")
    embed.set_footer(text=CIARA_FOOTER, icon_url=CIARA_ICON)

    await interaction.followup.send(embed=embed)
    await send_log(interaction.guild, embed)

@bot.tree.command(name="resetseo", description="♻️ Xoá sạch sẹo thành viên")
async def resetseo(interaction: discord.Interaction, member: discord.Member):
    await interaction.response.defer()  # 🔴 FIX TIMEOUT

    if not is_admin(interaction.user):
        return await interaction.followup.send("❌ Bạn không có quyền", ephemeral=True)

    data["users"][str(member.id)] = []
    save(data)
    await update_scar_roles(member, 0)

    embed = discord.Embed(
        title="🏴‍☠️ ÂN XÁ CIARA",
        description="✨ **Hồ sơ vi phạm đã được làm sạch**",
        color=0xC9A227
    )
    embed.add_field(name="👤 Thành viên", value=member.mention)
    embed.set_footer(text=CIARA_FOOTER, icon_url=CIARA_ICON)

    await interaction.followup.send(embed=embed)
    await send_log(interaction.guild, embed)

@bot.tree.command(name="topseo", description="🏆 Bảng xếp hạng vi phạm")
async def topseo(interaction: discord.Interaction):
    await interaction.response.defer()  # 🔴 an toàn

    ranked = sorted(
        data["users"].items(),
        key=lambda x: len(x[1]),
        reverse=True
    )[:10]

    desc = "\n".join(
        f"🥀 <@{uid}> — **{len(v)} sẹo**"
        for uid, v in ranked if len(v) > 0
    ) or "✨ Server hiện không có vi phạm"

    embed = discord.Embed(
        title="🏆 BẢNG ĐEN CIARA – TOP SẸO",
        description=desc,
        color=0xC9A227
    )
    embed.set_footer(text=CIARA_FOOTER, icon_url=CIARA_ICON)

    await interaction.followup.send(embed=embed)

@bot.tree.command(name="xemseo", description="👁️ Xem sẹo & vi phạm của bạn")
async def xemseo(interaction: discord.Interaction):
    u = get_user(interaction.user.id)
    if not u:
        return await interaction.response.send_message(
            "✨ Bạn là công dân sạch của **LORD OF CIARA**",
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
    embed.add_field(name="☠️ Tổng sẹo", value=f"**{len(u)}**")
    embed.set_footer(text=CIARA_FOOTER, icon_url=CIARA_ICON)

    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="datkenhlog", description="📥 Đặt kênh log sẹo")
async def datkenhlog(interaction: discord.Interaction, channel: discord.TextChannel):
    await interaction.response.defer()  # 🔴 FIX TIMEOUT

    if not interaction.user.guild_permissions.administrator:
        return await interaction.followup.send("❌ Chỉ Admin server", ephemeral=True)

    data["config"]["log_channel"] = channel.id
    save(data)

    await interaction.followup.send(f"✅ Đã đặt kênh log sẹo tại {channel.mention}")

# ================= START =================
if __name__ == "__main__":
    if not TOKEN:
        print("❌ DISCORD_TOKEN chưa được thiết lập")
    else:
        bot.run(TOKEN)
