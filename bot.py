import discord
from discord.ext import commands, tasks
import os
import json
import time
import random


# =====================================================
# CẤU HÌNH
# =====================================================

TOKEN = os.getenv("TOKEN")
PREFIX = "?"

POINT_CHANNEL_ID = int(
    os.getenv("POINT_CHANNEL_ID", "0")
)

POINTS_FILE = "points.json"
VOICE_FILE = "voice_time.json"


# =====================================================
# CẤU HÌNH ĐIỂM
# =====================================================

# Cùng Voice đủ 5 phút → +3 điểm
VOICE_POINT_INTERVAL = 5
VOICE_POINT_AMOUNT = 3

# Tag → +1 điểm
TAG_POINT_AMOUNT = 1

# Mỗi cặp chỉ được tính tag 1 lần / 5 phút
TAG_COOLDOWN = 300


# =====================================================
# 100 GIỜ VOICE → ROLE
# =====================================================

VOICE_REWARD_ROLE_ID = 1543920448503291924

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

        with open(
            filename,
            "r",
            encoding="utf-8"
        ) as f:

            return json.load(f)

    except Exception as e:

        print(
            f"❌ Lỗi đọc {filename}: {e}"
        )

        return {}


def save_json(filename, data):

    try:

        with open(
            filename,
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                data,
                f,
                ensure_ascii=False,
                indent=4
            )

    except Exception as e:

        print(
            f"❌ Lỗi lưu {filename}: {e}"
        )


points = load_json(POINTS_FILE)
voice_time = load_json(VOICE_FILE)


# =====================================================
# CHỐNG SPAM TAG
# =====================================================

tag_cooldowns = {}


# =====================================================
# THEO DÕI VOICE CỦA TỪNG NGƯỜI
# =====================================================

voice_sessions = {}


# =====================================================
# THEO DÕI CẶP Ở CÙNG ROOM
# =====================================================

pair_voice_sessions = {}


# =====================================================
# ROLE
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

    if not roles1:
        return False

    if not roles2:
        return False

    return roles1 == roles2


def get_role_names(member):

    return [
        role.name
        for role in member.roles
        if role.id in ALLOWED_ROLE_IDS
    ]


# =====================================================
# ID CẶP
# =====================================================

def get_pair_id(user1, user2):

    ids = sorted([
        user1.id,
        user2.id
    ])

    return f"{ids[0]}-{ids[1]}"


# =====================================================
# LẤY ĐIỂM CẶP
# =====================================================

def get_pair_points(
    guild_id,
    user1,
    user2
):

    guild_id = str(guild_id)

    pid = get_pair_id(
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
    amount,
    reason
):

    if not roles_same(
        user1,
        user2
    ):

        return False

    guild_id = str(
        user1.guild.id
    )

    pid = get_pair_id(
        user1,
        user2
    )

    if guild_id not in points:

        points[guild_id] = {}

    if pid not in points[guild_id]:

        points[guild_id][pid] = 0

    points[guild_id][pid] += amount

    save_json(
        POINTS_FILE,
        points
    )

    total = points[
        guild_id
    ][pid]

    print(
        f"💖 {user1.display_name} + "
        f"{user2.display_name} "
        f"→ +{amount} "
        f"(Tổng: {total})"
    )

    # =================================================
    # THÔNG BÁO
    # =================================================

    if POINT_CHANNEL_ID == 0:

        return True

    channel = user1.guild.get_channel(
        POINT_CHANNEL_ID
    )

    if channel is None:

        return True

    role_names = get_role_names(user1)

    role_text = ", ".join(
        role_names
    )

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
# CỘNG THỜI GIAN VOICE
# =====================================================

async def add_voice_time(
    member,
    seconds
):

    guild_id = str(
        member.guild.id
    )

    user_id = str(
        member.id
    )

    if guild_id not in voice_time:

        voice_time[guild_id] = {}

    if user_id not in voice_time[guild_id]:

        voice_time[guild_id][user_id] = {
            "seconds": 0,
            "reward": False
        }

    voice_time[
        guild_id
    ][user_id]["seconds"] += seconds

    total = voice_time[
        guild_id
    ][user_id]["seconds"]

    save_json(
        VOICE_FILE,
        voice_time
    )

    reward_given = voice_time[
        guild_id
    ][user_id].get(
        "reward",
        False
    )

    if (
        total >= VOICE_REQUIRED_SECONDS
        and not reward_given
    ):

        await give_voice_reward(
            member
        )


# =====================================================
# CẤP ROLE 100 GIỜ
# =====================================================

async def give_voice_reward(member):

    guild_id = str(
        member.guild.id
    )

    user_id = str(
        member.id
    )

    role = member.guild.get_role(
        VOICE_REWARD_ROLE_ID
    )

    if role is None:

        print(
            f"❌ Không tìm thấy role "
            f"{VOICE_REWARD_ROLE_ID}"
        )

        return

    try:

        if role not in member.roles:

            await member.add_roles(
                role,
                reason="Đủ 100 giờ Voice"
            )

        if guild_id not in voice_time:

            voice_time[guild_id] = {}

        if user_id not in voice_time[guild_id]:

            voice_time[guild_id][user_id] = {
                "seconds": VOICE_REQUIRED_SECONDS,
                "reward": True
            }

        else:

            voice_time[
                guild_id
            ][user_id]["reward"] = True

        save_json(
            VOICE_FILE,
            voice_time
        )

        print(
            f"🏆 {member} đã đạt 100 giờ Voice!"
        )

        if POINT_CHANNEL_ID != 0:

            channel = member.guild.get_channel(
                POINT_CHANNEL_ID
            )

            if channel:

                await channel.send(
                    f"🏆 **CHÚC MỪNG!**\n"
                    f"🎧 {member.mention}\n"
                    f"⏱️ Đã đạt **100 giờ Voice**!\n"
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

        rooms = {}

        # =================================================
        # KIỂM TRA NGƯỜI ĐANG VOICE
        # =================================================

        for member in guild.members:

            if member.bot:
                continue

            if member.voice is None:
                continue

            if member.voice.channel is None:
                continue

            current_users.add(
                member.id
            )

            channel_id = (
                member.voice.channel.id
            )

            if channel_id not in rooms:

                rooms[channel_id] = []

            rooms[channel_id].append(
                member
            )

            # =============================================
            # THEO DÕI THỜI GIAN VOICE
            # =============================================

            key = (
                guild.id,
                member.id
            )

            if key not in voice_sessions:

                voice_sessions[key] = {
                    "channel_id": channel_id,
                    "started": now
                }

            else:

                session = voice_sessions[key]

                if (
                    session["channel_id"]
                    != channel_id
                ):

                    session["channel_id"] = (
                        channel_id
                    )

                    session["started"] = now

        # =================================================
        # CỘNG THỜI GIAN VOICE
        # =================================================

        for key in list(
            voice_sessions.keys()
        ):

            guild_id, user_id = key

            if guild_id != guild.id:
                continue

            if user_id not in current_users:

                del voice_sessions[key]

                continue

            member = guild.get_member(
                user_id
            )

            if member is None:
                continue

            session = voice_sessions[key]

            elapsed = (
                now - session["started"]
            )

            if elapsed <= 0:
                continue

            session["started"] = now

            await add_voice_time(
                member,
                int(elapsed)
            )

        # =================================================
        # CẶP CÙNG VOICE
        # =================================================

        current_pairs = set()

        for channel_id, members in rooms.items():

            if len(members) < 2:
                continue

            for i in range(
                len(members)
            ):

                for j in range(
                    i + 1,
                    len(members)
                ):

                    user1 = members[i]
                    user2 = members[j]

                    # Phải cùng bộ role
                    if not roles_same(
                        user1,
                        user2
                    ):
                        continue

                    pid = get_pair_id(
                        user1,
                        user2
                    )

                    pair_key = (
                        guild.id,
                        channel_id,
                        pid
                    )

                    current_pairs.add(
                        pair_key
                    )

                    # Cặp mới vào room
                    if pair_key not in pair_voice_sessions:

                        pair_voice_sessions[
                            pair_key
                        ] = now

                        continue

                    started = pair_voice_sessions[
                        pair_key
                    ]

                    elapsed = (
                        now - started
                    )

                    # =====================================
                    # ĐỦ 5 PHÚT → +3
                    # =====================================

                    if elapsed >= (
                        VOICE_POINT_INTERVAL * 60
                    ):

                        success = await add_pair_point(
                            user1,
                            user2,
                            VOICE_POINT_AMOUNT,
                            "🎧 Cùng Voice đủ 5 phút."
                        )

                        if success:

                            # Bắt đầu chu kỳ 5 phút mới
                            pair_voice_sessions[
                                pair_key
                            ] = now

        # =================================================
        # XÓA CẶP KHÔNG CÒN CÙNG ROOM
        # =================================================

        for key in list(
            pair_voice_sessions.keys()
        ):

            if key[0] != guild.id:
                continue

            if key not in current_pairs:

                del pair_voice_sessions[key]


# =====================================================
# TAG
# =====================================================

@bot.event
async def on_message(message):

    if message.author.bot:
        return

    if message.guild is None:

        await bot.process_commands(
            message
        )

        return

    author = message.author

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

        if (
            now - last_tag
            < TAG_COOLDOWN
        ):
            continue

        tag_cooldowns[
            cooldown_key
        ] = now

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
# GIF TƯƠNG TÁC
# =====================================================

INTERACTION_GIFS = {

    "om": [
        "https://media.giphy.com/media/od5H3PmEG5EVq/giphy.gif",
        "https://media.giphy.com/media/ArLxZ4PebH2Ug/giphy.gif",
    ],

    "thom": [
        "https://media.giphy.com/media/nyGFcsP0kAobm/giphy.gif",
    ],

    "vo": [
        "https://media.giphy.com/media/3M4NpbLCTxBqU/giphy.gif",
    ],

    "highfive": [
        "https://media.giphy.com/media/5aW5D4VfXk8jC/giphy.gif",
    ]
}


async def do_interaction(
    ctx,
    member,
    action,
    message
):

    if member is None:

        await ctx.send(
            f"❌ Dùng: `{PREFIX}{action} @người`"
        )

        return

    if member.bot:

        await ctx.send(
            "❌ Không thể tương tác với bot."
        )

        return

    if member.id == ctx.author.id:

        await ctx.send(
            "😅 Không thể tự tương tác với chính mình!"
        )

        return

    gifs = INTERACTION_GIFS.get(
        action,
        []
    )

    gif = random.choice(gifs)

    await ctx.send(
        f"{message}\n{gif}"
    )


# =====================================================
# ?OM
# =====================================================

@bot.command(
    name="om",
    aliases=["ôm"]
)
async def om(
    ctx,
    member: discord.Member = None
):

    target = (
        member.mention
        if member
        else "@người"
    )

    await do_interaction(
        ctx,
        member,
        "om",
        f"🤗 **{ctx.author.mention}** ôm **{target}**!"
    )


# =====================================================
# ?THOM
# =====================================================

@bot.command(
    name="thom",
    aliases=["thơm"]
)
async def thom(
    ctx,
    member: discord.Member = None
):

    target = (
        member.mention
        if member
        else "@người"
    )

    await do_interaction(
        ctx,
        member,
        "thom",
        f"😊 **{ctx.author.mention}** thơm má **{target}**!"
    )


# =====================================================
# ?VO
# =====================================================

@bot.command(
    name="vo",
    aliases=["vỗ"]
)
async def vo(
    ctx,
    member: discord.Member = None
):

    target = (
        member.mention
        if member
        else "@người"
    )

    await do_interaction(
        ctx,
        member,
        "vo",
        f"👏 **{ctx.author.mention}** vỗ vai **{target}**!"
    )


# =====================================================
# ?HIGHFIVE
# =====================================================

@bot.command(
    name="highfive"
)
async def highfive(
    ctx,
    member: discord.Member = None
):

    target = (
        member.mention
        if member
        else "@người"
    )

    await do_interaction(
        ctx,
        member,
        "highfive",
        f"✋ **{ctx.author.mention}** đập tay với **{target}**!"
    )


# =====================================================
# ?DIEM
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
        f"💖 **ĐIỂM CHUNG**\n\n"
        f"👤 {ctx.author.mention}\n"
        f"❤️ {member.mention}\n\n"
        f"🏆 **{score} điểm**"
    )


# =====================================================
# ?GIO
# =====================================================

@bot.command()
async def gio(ctx):

    guild_id = str(
        ctx.guild.id
    )

    user_id = str(
        ctx.author.id
    )

    data = voice_time.get(
        guild_id,
        {}
    ).get(
        user_id,
        {
            "seconds": 0,
            "reward": False
        }
    )

    seconds = data.get(
        "seconds",
        0
    )

    hours = seconds / 3600

    remaining = max(
        0,
        VOICE_REQUIRED_SECONDS - seconds
    )

    remaining_hours = (
        remaining / 3600
    )

    await ctx.send(
        f"🎧 **THỜI GIAN VOICE**\n\n"
        f"👤 {ctx.author.mention}\n"
        f"⏱️ Đã Voice: **{hours:.2f} giờ**\n"
        f"🏆 Mục tiêu: **100 giờ**\n"
        f"⌛ Còn: **{remaining_hours:.2f} giờ**"
    )


# =====================================================
# ?TOP
# ======================
