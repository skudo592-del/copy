import discord
from discord.ext import commands, tasks
import os
import json
import time
import aiohttp

# =====================================================
# CẤU HÌNH
# =====================================================

TOKEN = os.getenv("TOKEN")
PREFIX = "?"

POINT_CHANNEL_ID = int(os.getenv("POINT_CHANNEL_ID", "0"))

POINTS_FILE = "points.json"
VOICE_FILE = "voice_time.json"


# =====================================================
# CẤU HÌNH ĐIỂM
# =====================================================

# Cùng Voice đủ 5 phút → +3 điểm
VOICE_POINT_INTERVAL = 5 * 60
VOICE_POINT_AMOUNT = 3

# Tag → +1 điểm
TAG_POINT_AMOUNT = 1

# Chống spam tag: 5 phút / cặp
TAG_COOLDOWN = 300


# =====================================================
# CẤU HÌNH 100 GIỜ LIÊN TỤC
# =====================================================

VOICE_REWARD_ROLE_ID = 1543920448503291924

# 100 giờ
VOICE_REQUIRED_SECONDS = 100 * 60 * 60


# =====================================================
# ROLE ĐƯỢC PHÉP TÍNH ĐIỂM
# =====================================================

ALLOWED_ROLE_IDS = {
    1538841659708547082,
    1539216628980392027,
    1539223863328514160,
    1539223921839046696,
    1539223988646051850,
    1539224042362642432,
    1539224100046635098,
    1539224192531038278,
}


# =====================================================
# LẤY GIF
# =====================================================

async def get_anime_gif(reaction: str):
    url = f"https://api.otakugifs.xyz/gif?reaction={reaction}"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=5) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("url")

    except Exception as e:
        print(f"❌ Lỗi lấy GIF ({reaction}): {e}")

    return None


# =====================================================
# INTENTS
# =====================================================

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.voice_states = True

bot = commands.Bot(
    command_prefix=PREFIX,
    intents=intents
)


# =====================================================
# DATABASE
# =====================================================

def load_json(filename):
    if not os.path.exists(filename):
        return {}

    try:
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)

    except Exception as e:
        print(f"❌ Lỗi đọc {filename}: {e}")
        return {}


def save_json(filename, data):
    try:
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(
                data,
                f,
                ensure_ascii=False,
                indent=4
            )

    except Exception as e:
        print(f"❌ Lỗi lưu {filename}: {e}")


points = load_json(POINTS_FILE)

# File này vẫn giữ để không mất dữ liệu cũ
voice_time = load_json(VOICE_FILE)


# =====================================================
# THEO DÕI
# =====================================================

tag_cooldowns = {}

# Phiên Voice hiện tại
#
# key = (guild_id, user_id)
#
# {
#     "channel_id": ID room,
#     "started": timestamp,
#     "last_point": timestamp
# }
#
voice_sessions = {}


# =====================================================
# HELPER
# =====================================================

def get_allowed_roles(member):
    return tuple(sorted(
        role.id
        for role in member.roles
        if role.id in ALLOWED_ROLE_IDS
    ))


def roles_same(member1, member2):
    roles1 = get_allowed_roles(member1)
    roles2 = get_allowed_roles(member2)

    if not roles1 or not roles2:
        return False

    return roles1 == roles2


def get_role_names(member):
    return [
        role.name
        for role in member.roles
        if role.id in ALLOWED_ROLE_IDS
    ]


def get_pair_id(user1, user2):
    ids = sorted([user1.id, user2.id])
    return f"{ids[0]}-{ids[1]}"


def get_pair_points(guild_id, user1, user2):
    guild_id = str(guild_id)
    pid = get_pair_id(user1, user2)

    return points.get(guild_id, {}).get(pid, 0)


# =====================================================
# CỘNG ĐIỂM CẶP
# =====================================================

async def add_pair_point(user1, user2, amount, reason):

    if not roles_same(user1, user2):
        return False

    guild_id = str(user1.guild.id)
    pid = get_pair_id(user1, user2)

    if guild_id not in points:
        points[guild_id] = {}

    if pid not in points[guild_id]:
        points[guild_id][pid] = 0

    points[guild_id][pid] += amount

    save_json(
        POINTS_FILE,
        points
    )

    total = points[guild_id][pid]

    print(
        f"💖 {user1.display_name} + "
        f"{user2.display_name} → "
        f"+{amount} | Tổng: {total}"
    )

    if POINT_CHANNEL_ID == 0:
        return True

    channel = user1.guild.get_channel(
        POINT_CHANNEL_ID
    )

    if channel is None:
        return True

    role_names = get_role_names(user1)
    role_text = ", ".join(role_names)

    try:
        await channel.send(
            f"💖 **CẶP ĐƯỢC CỘNG ĐIỂM!**\n"
            f"👤 {user1.mention} ❤️ {user2.mention}\n"
            f"🎭 Role: `{role_text}`\n"
            f"➕ **+{amount} điểm**\n"
            f"🏆 Điểm chung: **{total}**\n"
            f"📌 {reason}"
        )

    except Exception as e:
        print(
            f"❌ Lỗi gửi thông báo: {e}"
        )

    return True


# =====================================================
# CẤP ROLE 100 GIỜ
# =====================================================

async def give_voice_reward(member):

    role = member.guild.get_role(
        VOICE_REWARD_ROLE_ID
    )

    if role is None:
        print(
            f"❌ Không tìm thấy Role "
            f"{VOICE_REWARD_ROLE_ID}"
        )
        return

    try:

        if role not in member.roles:

            await member.add_roles(
                role,
                reason="Ngồi Voice liên tục đủ 100 giờ"
            )

        print(
            f"🏆 {member.display_name} "
            f"đã ngồi Voice liên tục 100 giờ!"
        )

        if POINT_CHANNEL_ID != 0:

            channel = member.guild.get_channel(
                POINT_CHANNEL_ID
            )

            if channel:

                await channel.send(
                    f"🏆 **CHÚC MỪNG!**\n"
                    f"🎧 {member.mention}\n"
                    f"⏱️ Đã ngồi **Voice liên tục đủ 100 giờ**!\n"
                    f"🎖️ Đã nhận role {role.mention}"
                )

    except discord.Forbidden:

        print(
            "❌ Bot không có quyền cấp role."
        )

    except Exception as e:

        print(
            f"❌ Lỗi cấp role: {e}"
        )


# =====================================================
# VOICE TRACKER
# =====================================================

@tasks.loop(seconds=60)
async def voice_tracker():

    now = time.time()

    for guild in bot.guilds:

        current_users = set()

        # ---------------------------------------------
        # KIỂM TRA NGƯỜI ĐANG Ở VOICE
        # ---------------------------------------------

        for member in guild.members:

            if member.bot:
                continue

            if (
                member.voice is None
                or member.voice.channel is None
            ):
                continue

            current_users.add(member.id)

            key = (
                guild.id,
                member.id
            )

            channel_id = member.voice.channel.id

            # -----------------------------------------
            # NGƯỜI MỚI VÀO ROOM
            # -----------------------------------------

            if key not in voice_sessions:

                voice_sessions[key] = {
                    "channel_id": channel_id,
                    "started": now,
                    "last_point": now
                }

                print(
                    f"🎧 {member.display_name} "
                    f"bắt đầu phiên 100 giờ."
                )

                continue

            session = voice_sessions[key]

            # -----------------------------------------
            # ĐỔI ROOM → RESET 100 GIỜ
            # -----------------------------------------

            if session["channel_id"] != channel_id:

                voice_sessions[key] = {
                    "channel_id": channel_id,
                    "started": now,
                    "last_point": now
                }

                print(
                    f"🔄 {member.display_name} "
                    f"đổi room → RESET 100 giờ."
                )

                continue

            # -----------------------------------------
            # TÍNH ĐIỂM VOICE
            # -----------------------------------------

            elapsed_point = (
                now - session["last_point"]
            )

            if elapsed_point >= VOICE_POINT_INTERVAL:

                # Số mốc 5 phút đã trôi qua
                intervals = int(
                    elapsed_point //
                    VOICE_POINT_INTERVAL
                )

                session["last_point"] += (
                    intervals *
                    VOICE_POINT_INTERVAL
                )

                # Tìm người cùng room
                room_members = [
                    m
                    for m in guild.members
                    if (
                        not m.bot
                        and m.voice
                        and m.voice.channel
                        and m.voice.channel.id == channel_id
                    )
                ]

                for other in room_members:

                    if other.id == member.id:
                        continue

                    await add_pair_point(
                        member,
                        other,
                        VOICE_POINT_AMOUNT *
                        intervals,
                        "🎧 Cùng Voice Room đủ 5 phút."
                    )

            # -----------------------------------------
            # KIỂM TRA 100 GIỜ LIÊN TỤC
            # -----------------------------------------

            continuous_time = (
                now - session["started"]
            )

            if continuous_time >= VOICE_REQUIRED_SECONDS:

                await give_voice_reward(member)

                # Không tính tiếp phiên này
                del voice_sessions[key]

                print(
                    f"🏆 {member.display_name} "
                    f"đã hoàn thành 100 giờ liên tục."
                )

        # ---------------------------------------------
        # AI ĐÃ RỜI VOICE → RESET
        # ---------------------------------------------

        for key in list(voice_sessions.keys()):

            guild_id, user_id = key

            if guild_id != guild.id:
                continue

            if user_id not in current_users:

                member = guild.get_member(
                    user_id
                )

                if member:

                    print(
                        f"🚪 {member.display_name} "
                        f"rời Voice → RESET 100 giờ."
                    )

                del voice_sessions[key]


# =====================================================
# MESSAGE
# =====================================================

@bot.event
async def on_message(message):

    if (
        message.author.bot
        or message.guild is None
    ):

        await bot.process_commands(message)
        return

    author = message.author

    # ---------------------------------------------
    # TAG → +1 ĐIỂM
    # ---------------------------------------------

    for target in message.mentions:

        if target.bot:
            continue

        if target.id == author.id:
            continue

        if not roles_same(
            author,
            target
        ):
            continue

        pid = get_pair_id(
            author,
            target
        )

        cooldown_key = (
            f"{message.guild.id}:{pid}"
        )

        now = time.time()

        last_tag = tag_cooldowns.get(
            cooldown_key,
            0
        )

        if now - last_tag < TAG_COOLDOWN:

            print(
                f"🛑 Tag spam: "
                f"{author.display_name} → "
                f"{target.display_name}"
            )

            continue

        tag_cooldowns[cooldown_key] = now

        await add_pair_point(
            author,
            target,
            TAG_POINT_AMOUNT,
            "🏷️ Tag nhau."
        )

    await bot.process_commands(
        message
    )


# =====================================================
# ?om
# =====================================================

@bot.command(
    name="om",
    aliases=["hug"]
)
async def hug(
    ctx,
    member: discord.Member = None
):

    if member is None:

        await ctx.send(
            "❌ Bạn cần tag người muốn ôm!\n"
            "Ví dụ: `?om @user`"
        )

        return

    if member.id == ctx.author.id:

        await ctx.send(
            f"**{ctx.author.display_name}** "
            f"tự ôm lấy chính mình... ❤️"
        )

        return

    gif_url = await get_anime_gif(
        "hug"
    )

    embed = discord.Embed(
        description=(
            f"🤗 **{ctx.author.display_name}** "
            f"đã ôm **{member.display_name}**!"
        ),
        color=discord.Color.pink()
    )

    if gif_url:
        embed.set_image(
            url=gif_url
        )

    await ctx.send(
        embed=embed
    )


# =====================================================
# ?hon
# =====================================================

@bot.command(
    name="hon",
    aliases=["kiss"]
)
async def kiss(
    ctx,
    member: discord.Member = None
):

    if member is None:

        await ctx.send(
            "❌ Bạn cần tag người muốn hôn!\n"
            "Ví dụ: `?hon @user`"
        )

        return

    if member.id == ctx.author.id:

        await ctx.send(
            f"**{ctx.author.display_name}** "
            f"tự hôn vào gương... 😳"
        )

        return

    gif_url = await get_anime_gif(
        "kiss"
    )

    embed = discord.Embed(
        description=(
            f"💋 **{ctx.author.display_name}** "
            f"đã gửi một nụ hôn cho "
            f"**{member.display_name}**!"
        ),
        color=discord.Color.red()
    )

    if gif_url:
        embed.set_image(
            url=gif_url
        )

    await ctx.send(
        embed=embed
    )


# =====================================================
# ?xoadau
# =====================================================

@bot.command(
    name="xoadau",
    aliases=["pat"]
)
async def pat(
    ctx,
    member: discord.Member = None
):

    if member is None:

        await ctx.send(
            "❌ Bạn cần tag người muốn xoa đầu!\n"
            "Ví dụ: `?xoadau @user`"
        )

        return

    if member.id == ctx.author.id:

        await ctx.send(
            f"**{ctx.author.display_name}** "
            f"tự xoa đầu mình... 🫳"
        )

        return

    gif_url = await get_anime_gif(
        "pat"
    )

    embed = discord.Embed(
        description=(
            f"🫳 **{ctx.author.display_name}** "
            f"xoa đầu **{member.display_name}**!"
        ),
        color=discord.Color.light_grey()
    )

    if gif_url:
        embed.set_image(
            url=gif_url
        )

    await ctx.send(
        embed=embed
    )


# =====================================================
# ?thomma
# =====================================================

@bot.command(
    name="thomma",
    aliases=["cheek"]
)
async def cheek(
    ctx,
    member: discord.Member = None
):

    if member is None:

        await ctx.send(
            "❌ Bạn cần tag người muốn thơm má!\n"
            "Ví dụ: `?thomma @user`"
        )

        return

    if member.id == ctx.author.id:

        await ctx.send(
            f"**{ctx.author.display_name}** "
            f"tự thơm vào tay... 💕"
        )

        return

    gif_url = await get_anime_gif(
        "kiss"
    )

    embed = discord.Embed(
        description=(
            f"😚 **{ctx.author.display_name}** "
            f"thơm má **{member.display_name}**!"
        ),
        color=discord.Color.purple()
    )

    if gif_url:
        embed.set_image(
            url=gif_url
        )

    await ctx.send(
        embed=embed
    )


# =====================================================
# ?canyeu
# =====================================================

@bot.command(
    name="canyeu",
    aliases=["bite"]
)
async def bite(
    ctx,
    member: discord.Member = None
):

    if member is None:

        await ctx.send(
            "❌ Bạn cần tag người muốn cắn yêu!\n"
            "Ví dụ: `?canyeu @user`"
        )

        return

    if member.id == ctx.author.id:

        await ctx.send(
            f"**{ctx.author.display_name}** "
            f"tự cắn vào tay mình... 😬"
        )

        return

    gif_url = await get_anime_gif(
        "bite"
    )

    embed = discord.Embed(
        description=(
            f"🦷 **{ctx.author.display_name}** "
            f"cắn nhẹ **{member.display_name}**!"
        ),
        color=discord.Color.orange()
    )

    if gif_url:
        embed.set_image(
            url=gif_url
        )

    await ctx.send(
        embed=embed
    )


# =====================================================
# ?diem
# =====================================================

@bot.command()
async def diem(
    ctx,
    member: discord.Member = None
):

    if member is None:

        await ctx.send(
            "❌ Dùng: `?diem @người`"
        )

        return

    if member.bot:

        await ctx.send(
            "❌ Không thể xem điểm với bot."
        )

        return

    if not roles_same(
        ctx.author,
        member
    ):

        await ctx.send(
            "❌ Hai người không có bộ role giống nhau."
        )

        return

    score = get_pair_points(
        ctx.guild.id,
        ctx.author,
        member
    )

    await ctx.send(
        f"💖 **ĐIỂM CHUNG**\n\n"
        f"👤 {ctx.author.mention}\n"
        f"❤️ {member.mention}\n\n"
        f"🏆 **{score} điểm**"
    )


# =====================================================
# ?gio
# =====================================================

@bot.command()
async def gio(ctx):

    key = (
        ctx.guild.id,
        ctx.author.id
    )

    # Chỉ hiển thị phiên hiện tại
    if key in voice_sessions:

        session = voice_sessions[key]

        elapsed = max(
            0,
            time.time() - session["started"]
        )

        hours = elapsed / 3600

        remaining = max(
            0,
            VOICE_REQUIRED_SECONDS - elapsed
        )

        remaining_hours = (
            remaining / 3600
        )

        channel = ctx.guild.get_channel(
            session["channel_id"]
        )

        channel_name = (
            channel.name
            if channel
            else "Không xác định"
        )

        await ctx.send(
            f"🎧 **VOICE LIÊN TỤC**\n\n"
            f"👤 {ctx.author.mention}\n"
            f"🔊 Room: **{channel_name}**\n"
            f"⏱️ Phiên hiện tại: "
            f"**{hours:.2f} giờ**\n"
            f"🏆 Mục tiêu: **100 giờ liên tục**\n"
            f"⌛ Còn: **{remaining_hours:.2f} giờ**"
        )

    else:

        await ctx.send(
            f"🎧 **VOICE LIÊN TỤC**\n\n"
            f"👤 {ctx.author.mention}\n"
            f"⏱️ Bạn chưa có phiên Voice.\n"
            f"🏆 Vào một room để bắt đầu "
            f"tính 100 giờ liên tục."
        )


# =====================================================
# ?top
# =====================================================

@bot.com
