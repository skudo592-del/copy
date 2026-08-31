import discord
from discord.ext import commands, tasks
import os
import json


# =====================================================
# CẤU HÌNH
# =====================================================

TOKEN = os.getenv("TOKEN")
PREFIX = "?"

# ID kênh bot gửi thông báo cộng điểm
POINT_CHANNEL_ID = int(os.getenv("POINT_CHANNEL_ID", "0"))

# File lưu điểm
DATA_FILE = "points.json"


# =====================================================
# ROLE ĐƯỢC PHÉP TÍNH ĐIỂM
# =====================================================
#
# CHỈ ROLE CÓ ID Ở ĐÂY MỚI ĐƯỢC TÍNH.
#
# Ví dụ:
#
# Gamer       = 111111111111111111
# Player      = 222222222222222222
#
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
# LOAD DATABASE
# =====================================================

def load_data():

    if not os.path.exists(DATA_FILE):
        return {}

    try:

        with open(
            DATA_FILE,
            "r",
            encoding="utf-8"
        ) as file:

            return json.load(file)

    except Exception:

        return {}


points = load_data()


# =====================================================
# SAVE DATABASE
# =====================================================

def save_data():

    with open(
        DATA_FILE,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            points,
            file,
            ensure_ascii=False,
            indent=4
        )


# =====================================================
# LẤY ROLE ĐƯỢC CHỈ ĐỊNH
# =====================================================

def get_roles(member):

    roles = []

    for role in member.roles:

        if role.id in ALLOWED_ROLE_IDS:

            roles.append(role.id)

    return tuple(sorted(roles))


# =====================================================
# KIỂM TRA 2 NGƯỜI CÓ ROLE GIỐNG NHAU
# =====================================================

def roles_same(member1, member2):

    roles1 = get_roles(member1)
    roles2 = get_roles(member2)

    # Không có role được chỉ định
    if len(roles1) == 0:
        return False

    if len(roles2) == 0:
        return False

    # PHẢI GIỐNG 100%
    return roles1 == roles2


# =====================================================
# TẠO ID CẶP
# =====================================================

def pair_id(user1, user2):

    ids = sorted([
        user1.id,
        user2.id
    ])

    return f"{ids[0]}-{ids[1]}"


# =====================================================
# LẤY ĐIỂM CẶP
# =====================================================

def get_pair_points(guild_id, user1, user2):

    guild_id = str(guild_id)

    pid = pair_id(
        user1,
        user2
    )

    return points.get(
        guild_id,
        {}
    ).get(
        pid,
        0
    )


# =====================================================
# CỘNG ĐIỂM CẶP
# =====================================================

async def add_pair_point(
    user1,
    user2,
    amount=1,
    reason=""
):

    # Role phải giống
    if not roles_same(
        user1,
        user2
    ):
        return False

    guild_id = str(
        user1.guild.id
    )

    pid = pair_id(
        user1,
        user2
    )

    if guild_id not in points:

        points[guild_id] = {}

    if pid not in points[guild_id]:

        points[guild_id][pid] = 0

    points[guild_id][pid] += amount

    save_data()

    total = points[
        guild_id
    ][pid]

    print(
        f"[POINT] "
        f"{user1.display_name} + "
        f"{user2.display_name} "
        f"= {total}"
    )

    # =================================================
    # THÔNG BÁO
    # =================================================

    if POINT_CHANNEL_ID != 0:

        channel = user1.guild.get_channel(
            POINT_CHANNEL_ID
        )

        if channel:

            try:

                await channel.send(
                    f"💖 **CẶP ĐƯỢC CỘNG ĐIỂM!**\n"
                    f"👤 {user1.mention} ❤️ {user2.mention}\n"
                    f"➕ **+{amount} điểm**\n"
                    f"🏆 Điểm chung: **{total}**\n"
                    f"📌 {reason}"
                )

            except Exception as e:

                print(
                    f"Lỗi gửi thông báo: {e}"
                )

    return True


# =====================================================
# CỘNG ĐIỂM VOICE
# =====================================================

@tasks.loop(minutes=1)
async def voice_points():

    print("🔄 Đang kiểm tra Voice Room...")

    for guild in bot.guilds:

        rooms = {}

        # ---------------------------------------------
        # Tìm người trong từng room
        # ---------------------------------------------

        for member in guild.members:

            if member.bot:
                continue

            if member.voice is None:
                continue

            if member.voice.channel is None:
                continue

            channel_id = member.voice.channel.id

            if channel_id not in rooms:

                rooms[channel_id] = []

            rooms[channel_id].append(member)

        # ---------------------------------------------
        # Kiểm tra từng room
        # ---------------------------------------------

        for members in rooms.values():

            if len(members) < 2:
                continue

            # -----------------------------------------
            # Kiểm tra từng cặp
            # -----------------------------------------

            for i in range(
                len(members)
            ):

                for j in range(
                    i + 1,
                    len(members)
                ):

                    user1 = members[i]
                    user2 = members[j]

                    if roles_same(
                        user1,
                        user2
                    ):

                        await add_pair_point(
                            user1,
                            user2,
                            1,
                            "🎧 Cùng Voice Room 1 phút."
                        )


# =====================================================
# TAG
# =====================================================

@bot.event
async def on_message(message):

    # Bỏ qua bot
    if message.author.bot:
        return

    # Tin nhắn DM
    if message.guild is None:

        await bot.process_commands(message)

        return

    # ---------------------------------------------
    # Xử lý tag
    # ---------------------------------------------

    for target in message.mentions:

        if target.bot:
            continue

        if roles_same(
            message.author,
            target
        ):

            await add_pair_point(
                message.author,
                target,
                1,
                "🏷️ Tag nhau."
            )

    # Cho phép command hoạt động
    await bot.process_commands(
        message
    )


# =====================================================
# ?DIEM @NGƯỜI
# =====================================================

@bot.command()
async def diem(
    ctx,
    member: discord.Member = None
):

    if member is None:

        await ctx.send(
            "❌ Dùng đúng:\n"
            "`?diem @người`"
        )

        return

    if member.bot:

        await ctx.send(
            "❌ Không thể xem điểm với bot."
        )

        return

    # Role không giống
    if not roles_same(
        ctx.author,
        member
    ):

        await ctx.send(
            "❌ Hai người không có "
            "bộ role giống nhau."
        )

        return

    score = get_pair_points(
        ctx.guild.id,
        ctx.author,
        member
    )

    await ctx.send(
        f"💖 **ĐIỂM CẶP**\n\n"
        f"👤 {ctx.author.mention}\n"
        f"❤️ {member.mention}\n\n"
        f"🏆 **Điểm chung: {score}**"
    )


# =====================================================
# ?TOP
# =====================================================

@bot.command()
async def top(ctx):

    guild_id = str(
        ctx.guild.id
    )

    data = points.get(
        guild_id,
        {}
    )

    if not data:

        await ctx.send(
            "📊 Chưa có cặp nào có điểm."
        )

        return

    ranking = sorted(
        data.items(),
        key=lambda x: x[1],
        reverse=True
    )

    ranking = ranking[:10]

    text = "🏆 **TOP CẶP ĐIỂM**\n\n"

    for index, (
        pid,
        score
    ) in enumerate(
        ranking,
        1
    ):

        try:

            id1, id2 = pid.split("-")

            member1 = ctx.guild.get_member(
                int(id1)
            )

            member2 = ctx.guild.get_member(
                int(id2)
            )

            name1 = (
                member1.display_name
                if member1
                else id1
            )

            name2 = (
                member2.display_name
                if member2
                else id2
            )

            text += (
                f"**{index}.** "
                f"{name1} ❤️ {name2} "
                f"— **{score} điểm**\n"
            )

        except Exception:

            continue

    await ctx.send(text)


# =====================================================
# ?RESETDIEM
# =====================================================
# Chỉ Admin mới dùng được
# =====================================================

@bot.command()
@commands.has_permissions(administrator=True)
async def resetdiem(ctx):

    guild_id = str(
        ctx.guild.id
    )

    points[guild_id] = {}

    save_data()

    await ctx.send(
        "🗑️ Đã reset toàn bộ điểm của server."
    )


# =====================================================
# LỖI COMMAND
# =====================================================

@bot.event
async def on_command_error(
    ctx,
    error
):

    if isinstance(
        error,
        commands.MissingPermissions
    ):

        await ctx.send(
            "❌ Bạn không có quyền dùng lệnh này."
        )

        return

    if isinstance(
        error,
        commands.MemberNotFound
    ):

        await ctx.send(
            "❌ Không tìm thấy người dùng."
        )

        return

    if isinstance(
        error,
        commands.CommandNotFound
    ):

        return

    print(
        f"Command error: {error}"
    )


# =====================================================
# BOT ONLINE
# =====================================================

@bot.event
async def on_ready():

    print("=" * 40)

    print(
        f"✅ BOT ONLINE: {bot.user}"
    )

    print(
        f"🏠 Server: {len(bot.guilds)}"
    )

    print(
        f"🎭 Role được tính: "
        f"{len(ALLOWED_ROLE_IDS)}"
    )

    print("=" * 40)

    if not voice_points.is_running():

        voice_points.start()


# =====================================================
# KIỂM TRA TOKEN
# =====================================================

if not TOKEN:

    raise RuntimeError(
        "❌ Chưa có TOKEN trong Railway Variables!"
    )


# =====================================================
# CHẠY
# =====================================================

bot.run(TOKEN)
