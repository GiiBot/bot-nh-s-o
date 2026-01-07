import discord
from discord.ext import commands, tasks
from datetime import datetime, timedelta, timezone
import json
import os

# ================= ENV =================
TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID", "0"))
DATA_FILE = "data.json"
VN_TZ = timezone(timedelta(hours=7))
DEADLINE_DAYS = 7

# ================= THEME =================
COLOR = {
    1: 0xFF6B6B,  # Đỏ nhạt - cảnh cáo đầu
    2: 0xFF4757,  # Đỏ vừa - cảnh cáo lần 2
    3: 0xEE5A6F   # Đỏ đậm - nghiêm trọng
}
FOOTER = "⚔️ LORD OF CIARA | KỶ LUẬT TẠO SỨC MẠNH"
ICON = "https://i.imgur.com/sword.png"

# ================= PENALTY =================
PENALTY = {
    1: "⚠️ Cảnh cáo lần 1",
    2: "💰 Đóng quỹ 500.000 VNĐ",
    3: "💸 Đóng quỹ 1.000.000 VNĐ",
    4: "🚨 Cảnh cáo nghiêm khắc",
    5: "👢 Kick khỏi crew",
    6: "🔨 Ban tạm thời",
    7: "⛔ Ban vĩnh viễn"
}

# ================= BOT SETUP =================
intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# ================= DATA MANAGEMENT =================
def load():
    if not os.path.exists(DATA_FILE):
        return {
            "config": {"log_channel": None}, 
            "case_id": 0, 
            "users": {}, 
            "admin_logs": []
        }
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ Lỗi load data: {e}")
        return {"config": {"log_channel": None}, "case_id": 0, "users": {}, "admin_logs": []}

def save():
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"❌ Lỗi save data: {e}")

data = load()

# ================= UTILS =================
def is_admin(member):
    """Check nếu user là admin"""
    return member.guild_permissions.administrator

def next_case():
    """Tạo case ID mới"""
    data["case_id"] += 1
    save()
    return f"#{data['case_id']:04d}"

def get_user(uid):
    """Lấy thông tin user từ database"""
    uid = str(uid)
    if uid not in data["users"]:
        data["users"][uid] = []
        save()
    return data["users"][uid]

def countdown(deadline):
    """Tính thời gian còn lại"""
    now = datetime.now(VN_TZ)
    diff = deadline - now
    if diff.total_seconds() <= 0:
        return "🔴 **ĐÃ QUÁ HẠN**"
    d = diff.days
    h = diff.seconds // 3600
    m = (diff.seconds % 3600) // 60
    return f"⏳ Còn **{d} ngày {h} giờ {m} phút**"

def ciara_embed(title, desc, color):
    """Tạo embed với theme CIARA"""
    e = discord.Embed(
        title=f"# {title}",
        description=desc,
        color=color,
        timestamp=datetime.now(VN_TZ)
    )
    e.set_footer(text=FOOTER, icon_url=ICON)
    return e

# ================= AUTO PING TASK =================
@tasks.loop(hours=6)
async def auto_ping_unpaid():
    """Tự động nhắc nhở người chưa đóng phạt"""
    guild = bot.get_guild(GUILD_ID)
    if not guild:
        return

    for uid, records in data["users"].items():
        member = guild.get_member(int(uid))
        if not member:
            continue
        
        for r in records:
            if not r["paid"]:
                try:
                    deadline = datetime.fromisoformat(r["deadline"])
                    time_left = deadline - datetime.now(VN_TZ)
                    
                    # Chỉ ping nếu còn dưới 24 giờ
                    if 0 < time_left.total_seconds() < 86400:
                        await member.send(
                            f"# 🔔 NHẮC NHỞ ĐÓNG PHẠT\n\n"
                            f"📋 **Case:** `{r['case']}`\n"
                            f"📌 **Lý do:** {r['reason']}\n"
                            f"{countdown(deadline)}\n\n"
                            f"⚠️ *Vui lòng liên hệ Admin để xác nhận thanh toán!*"
                        )
                except Exception as e:
                    print(f"❌ Lỗi ping user {uid}: {e}")

@auto_ping_unpaid.before_loop
async def before_auto_ping():
    await bot.wait_until_ready()

# ================= CONFIRM VIEW =================
class ConfirmPaidView(discord.ui.View):
    def __init__(self, member, record):
        super().__init__(timeout=300)
        self.member = member
        self.record = record

    @discord.ui.button(label="✅ XÁC NHẬN ĐÃ ĐÓNG", style=discord.ButtonStyle.success, emoji="💰")
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_admin(interaction.user):
            return await interaction.response.send_message("❌ Chỉ Admin mới có quyền này!", ephemeral=True)
        
        self.record["paid"] = True
        self.record["paid_at"] = datetime.now(VN_TZ).isoformat()
        self.record["paid_by"] = interaction.user.name
        self.record["paid_note"] = "Đã xác nhận thanh toán đầy đủ"
        save()
        
        embed = ciara_embed(
            "✅ HOÀN TẤT THANH TOÁN",
            f"## {self.member.mention} đã hoàn thành hình phạt!\n\n"
            f"📋 **Case:** `{self.record['case']}`\n"
            f"✅ **Xác nhận bởi:** {interaction.user.mention}\n"
            f"📅 **Thời gian:** {datetime.now(VN_TZ).strftime('%d/%m/%Y %H:%M')}",
            0x27AE60
        )
        
        await interaction.response.edit_message(embed=embed, view=None)
        
        try:
            await self.member.send(
                f"# ✅ THANH TOÁN THÀNH CÔNG\n\n"
                f"Hình phạt `{self.record['case']}` của bạn đã được xác nhận thanh toán!\n"
                f"Cảm ơn bạn đã tuân thủ kỷ luật crew."
            )
        except:
            pass

    @discord.ui.button(label="❌ HỦY BỎ", style=discord.ButtonStyle.danger, emoji="🚫")
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(
            content="❌ Đã hủy xác nhận thanh toán",
            embed=None,
            view=None
        )

# ================= SLASH COMMANDS =================

@bot.tree.command(name="ghiseo", description="⚔️ Ghi sẹo vi phạm cho thành viên")
async def ghiseo(interaction: discord.Interaction, member: discord.Member, lydo: str):
    """Ghi nhận vi phạm cho thành viên"""
    if not is_admin(interaction.user):
        return await interaction.response.send_message("❌ Chỉ Admin mới có quyền sử dụng lệnh này!", ephemeral=True)

    user_records = get_user(member.id)
    violation_count = len(user_records) + 1
    
    record = {
        "case": next_case(),
        "reason": lydo,
        "by": interaction.user.name,
        "created_at": datetime.now(VN_TZ).isoformat(),
        "deadline": (datetime.now(VN_TZ) + timedelta(days=DEADLINE_DAYS)).isoformat(),
        "paid": False,
        "paid_note": "",
        "violation_number": violation_count
    }
    
    user_records.append(record)
    save()

    penalty_text = PENALTY.get(violation_count, "⛔ Xử lý đặc biệt")
    color = COLOR.get(min(violation_count, 3), 0xFF0000)
    
    embed = ciara_embed(
        "⚔️ CIARA DISCIPLINE REPORT",
        f"## 👤 Thành viên: {member.mention}\n\n"
        f"📋 **Case ID:** `{record['case']}`\n"
        f"🔢 **Vi phạm lần:** {violation_count}\n"
        f"📌 **Lý do:**\n```\n{record['reason']}\n```\n"
        f"🚨 **Hình phạt:** {penalty_text}\n"
        f"👮 **Ghi nhận bởi:** {interaction.user.mention}\n"
        f"📅 **Hạn đóng phạt:** {datetime.fromisoformat(record['deadline']).strftime('%d/%m/%Y %H:%M')}\n\n"
        f"{countdown(datetime.fromisoformat(record['deadline']))}",
        color
    )
    
    await interaction.response.send_message(
        content=f"@everyone\n# ⚠️ THÔNG BÁO VI PHẠM\n{member.mention}",
        embed=embed
    )
    
    try:
        await member.send(
            f"# ⚠️ THÔNG BÁO VI PHẠM CIARA\n\n"
            f"Bạn đã nhận được cảnh cáo vi phạm:\n\n"
            f"📋 **Case:** `{record['case']}`\n"
            f"📌 **Lý do:** {record['reason']}\n"
            f"🚨 **Hình phạt:** {penalty_text}\n"
            f"📅 **Hạn thanh toán:** {datetime.fromisoformat(record['deadline']).strftime('%d/%m/%Y %H:%M')}\n\n"
            f"Vui lòng liên hệ Admin để thanh toán trước hạn!"
        )
    except:
        pass

@bot.tree.command(name="xemseo", description="🔍 Xem sẹo vi phạm của bạn")
async def xemseo(interaction: discord.Interaction, member: discord.Member = None):
    """Xem lịch sử vi phạm"""
    target = member if member and is_admin(interaction.user) else interaction.user
    
    user_records = get_user(target.id)
    
    if not user_records:
        return await interaction.response.send_message(
            f"✨ {'Thành viên này' if member else 'Bạn'} không có vi phạm nào!",
            ephemeral=True
        )
    
    violations_text = ""
    unpaid_count = 0
    
    for idx, r in enumerate(user_records, 1):
        status = "✅ Đã đóng" if r["paid"] else "❌ Chưa đóng"
        if not r["paid"]:
            unpaid_count += 1
        
        violations_text += (
            f"\n### {idx}. `{r['case']}` {status}\n"
            f"📌 {r['reason']}\n"
            f"📅 {datetime.fromisoformat(r['created_at']).strftime('%d/%m/%Y')}\n"
        )
    
    color = COLOR.get(min(len(user_records), 3), 0x3498DB)
    
    embed = ciara_embed(
        f"🧬 HỒ SƠ VI PHẠM - {target.display_name}",
        f"## Tổng quan\n"
        f"📊 **Tổng vi phạm:** {len(user_records)}\n"
        f"❌ **Chưa thanh toán:** {unpaid_count}\n"
        f"✅ **Đã thanh toán:** {len(user_records) - unpaid_count}\n\n"
        f"## Chi tiết vi phạm\n{violations_text}",
        color
    )
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="xacnhanphat", description="💰 Xác nhận thành viên đã đóng phạt")
async def xacnhanphat(interaction: discord.Interaction, member: discord.Member):
    """Xác nhận thanh toán phạt"""
    if not is_admin(interaction.user):
        return await interaction.response.send_message("❌ Chỉ Admin mới có quyền sử dụng lệnh này!", ephemeral=True)
    
    user_records = get_user(member.id)
    
    if not user_records:
        return await interaction.response.send_message("⚠️ Thành viên này không có vi phạm nào!", ephemeral=True)
    
    unpaid = [r for r in user_records if not r["paid"]]
    
    if not unpaid:
        return await interaction.response.send_message("✅ Thành viên này đã thanh toán hết!", ephemeral=True)
    
    latest_unpaid = unpaid[-1]
    
    embed = ciara_embed(
        "💰 XÁC NHẬN THANH TOÁN",
        f"## {member.mention}\n\n"
        f"📋 **Case:** `{latest_unpaid['case']}`\n"
        f"📌 **Lý do:** {latest_unpaid['reason']}\n"
        f"📅 **Hạn:** {datetime.fromisoformat(latest_unpaid['deadline']).strftime('%d/%m/%Y %H:%M')}\n\n"
        f"⚠️ Vui lòng xác nhận đã nhận đủ tiền phạt!",
        0xF1C40F
    )
    
    await interaction.response.send_message(
        embed=embed,
        view=ConfirmPaidView(member, latest_unpaid)
    )

@bot.tree.command(name="dashboard", description="📊 Xem thống kê tổng quan")
async def dashboard(interaction: discord.Interaction):
    """Xem dashboard tổng quan của crew"""
    
    total_case = sum(len(v) for v in data["users"].values())
    unpaid = sum(1 for v in data["users"].values() for r in v if not r["paid"])
    paid = total_case - unpaid
    total_members = len(data["users"])
    
    top_violators = sorted(
        data["users"].items(),
        key=lambda x: len(x[1]),
        reverse=True
    )[:5]
    
    top_text = ""
    for uid, records in top_violators:
        try:
            member = await interaction.guild.fetch_member(int(uid))
            top_text += f"• {member.mention}: **{len(records)}** vi phạm\n"
        except:
            top_text += f"• User {uid}: **{len(records)}** vi phạm\n"
    
    embed = ciara_embed(
        "📊 DASHBOARD CIARA",
        f"## Thống kê tổng quan\n\n"
        f"👥 **Tổng thành viên có hồ sơ:** {total_members}\n"
        f"📁 **Tổng số case:** {total_case}\n"
        f"✅ **Đã thanh toán:** {paid}\n"
        f"❌ **Chưa thanh toán:** {unpaid}\n"
        f"📈 **Tỷ lệ tuân thủ:** {(paid/total_case*100 if total_case > 0 else 0):.1f}%\n\n"
        f"## 🏆 Top vi phạm nhiều nhất\n{top_text if top_text else '*Chưa có dữ liệu*'}",
        0x3498DB
    )
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="xoaseo", description="🗑️ Xóa một sẹo vi phạm")
async def xoaseo(interaction: discord.Interaction, member: discord.Member, case_id: str):
    """Xóa vi phạm (Admin only)"""
    if not is_admin(interaction.user):
        return await interaction.response.send_message("❌ Chỉ Admin mới có quyền sử dụng lệnh này!", ephemeral=True)
    
    user_records = get_user(member.id)
    
    for i, r in enumerate(user_records):
        if r["case"] == case_id:
            deleted = user_records.pop(i)
            save()
            
            embed = ciara_embed(
                "🗑️ ĐÃ XÓA VI PHẠM",
                f"## {member.mention}\n\n"
                f"📋 **Case:** `{deleted['case']}`\n"
                f"📌 **Lý do:** {deleted['reason']}\n"
                f"👮 **Xóa bởi:** {interaction.user.mention}",
                0xE74C3C
            )
            
            return await interaction.response.send_message(embed=embed)
    
    await interaction.response.send_message(f"❌ Không tìm thấy case `{case_id}` cho {member.mention}!", ephemeral=True)

@bot.tree.command(name="help", description="❓ Hướng dẫn sử dụng bot")
async def help_command(interaction: discord.Interaction):
    """Hiển thị hướng dẫn sử dụng"""
    
    embed = ciara_embed(
        "❓ HƯỚNG DẪN SỬ DỤNG",
        f"## Lệnh cho mọi người\n"
        f"• `/xemseo` - Xem hồ sơ vi phạm của bạn\n"
        f"• `/dashboard` - Xem thống kê tổng quan\n"
        f"• `/help` - Xem hướng dẫn này\n\n"
        f"## Lệnh Admin\n"
        f"• `/ghiseo @member [lý do]` - Ghi nhận vi phạm\n"
        f"• `/xacnhanphat @member` - Xác nhận đã đóng phạt\n"
        f"• `/xoaseo @member [case_id]` - Xóa vi phạm\n\n"
        f"## Hệ thống hình phạt\n"
        f"{chr(10).join(f'**{k}.** {v}' for k, v in PENALTY.items())}",
        0x9B59B6
    )
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

# ================= EVENTS =================
@bot.event
async def on_ready():
    """Khi bot online"""
    print(f"✅ {bot.user.name} đã online!")
    print(f"📊 Guilds: {len(bot.guilds)}")
    print(f"👥 Users: {len(bot.users)}")
    
    try:
        if GUILD_ID:
            guild = discord.Object(id=GUILD_ID)
            bot.tree.clear_commands(guild=guild)
            synced = await bot.tree.sync(guild=guild)
            print(f"✅ Đã sync {len(synced)} lệnh cho guild {GUILD_ID}")
        else:
            synced = await bot.tree.sync()
            print(f"✅ Đã sync {len(synced)} lệnh global")
        
        if not auto_ping_unpaid.is_running():
            auto_ping_unpaid.start()
            print("✅ Đã bật auto ping")
        
        print("⚔️ CIARA BOT SẴN SÀNG CHIẾN ĐẤU!")
        
    except Exception as e:
        print(f"❌ Lỗi khi sync: {e}")

@bot.event
async def on_command_error(ctx, error):
    """Handle errors"""
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ Bạn không có quyền sử dụng lệnh này!")
    elif isinstance(error, commands.MemberNotFound):
        await ctx.send("❌ Không tìm thấy thành viên!")
    else:
        print(f"❌ Lỗi: {error}")

# ================= RUN BOT =================
if __name__ == "__main__":
    if not TOKEN:
        print("❌ Thiếu DISCORD_TOKEN trong environment variables!")
    else:
        try:
            bot.run(TOKEN)
        except Exception as e:
            print(f"❌ Lỗi khởi động bot: {e}")
