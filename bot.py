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
VOICE_POINT_INTERVAL = 5 * 60
VOICE_POINT_AMOUNT = 3

# Tag → +1 điểm
TAG_POINT_AMOUNT = 1

# Tương tác → +1 điểm
INTERACTION_POINT_AMOUNT = 1

# Cooldown tag: 5 phút / cặp
TAG_COOLDOWN = 300

# Cooldown tương tác: 30 giây / cặp
INTERACTION_COOLDOWN = 30


# =====================================================
# CẤU HÌNH 100 GIỜ
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
# GIF
# =====================================================

GIFS = {

    "om": [
        "https://media.giphy.com/media/od5H3PmEG5EVq/giphy.gif",
        "https://media.giphy.com/media/ArLxZ4PebH2Ug/giphy.gif",
    ],

    "hon": [
        "https://media.giphy.com/media/G3va31oEEnIkM/giphy.gif",
        "https://media.giphy.com/media/KH1CTZtw1NoPe/giphy.gif",
    ],

    "thom": [
        "https://media.giphy.com/media/nyGFcsP0kAobm/giphy.gif",
        "https://media.giphy.com/media/11rWoZNpAKw8w/giphy.gif",
    ]
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


points = load_json(POINTS_FILE)

voice_time = load_json(VOICE_FILE)


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


# =====================================================
# COOLDOWN
# =====================================================

tag_cooldowns = {}

interaction_cooldowns = {}


# =====================================================
# VOICE SESSION
# =====================================================

voice_sessions = {}


# =====================================================
# LẤY ROLE ĐƯỢC CHỈ ĐỊNH
# =====================================================

def get_allowed_roles(member):

    return tuple(sorted(
        role.id
        for role in member.roles
        if role.id in ALLOWED_ROLE_IDS
    ))


# =====================================================
# KIỂM TRA ROLE GIỐNG NHAU
# =====================================================

def roles_same(member1, member2):

    roles1 = get_allowed_roles(member1)
    roles2 = get_allowed_roles(member2)

    if not roles1:
        return False

    if not roles2:
        return False

    return roles1 == roles2


# =====================================================
# TÊN ROLE
# =====================================================

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
# CỘNG ĐIỂM CHUNG
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
            f"👤 {user1.mention} "
            f"<:azumeo_y:1538431979165589505> "
            f"<:azumeo_e:1538431708481847379> "
            f"<:azumeo_u:1538431970260946956> "
            f"{user2.mention}\n"
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

    # =================================================
    # KIỂM TRA 100 GIỜ
    # =================================================

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
            f"❌ Không tìm thấy Role "
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
# THEO DÕI VOICE
# =====================================================

@tasks.loop(seconds=60)
async def voice_tracker():

    now = time.time()

    for guild in bot.guilds:

        current_users = set()

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

            key = (
                guild.id,
                member.id
            )

            if key not in voice_sessions:

                voice_sessions[key] = {
                    "channel_id":
                        member.voice.channel.id,
                    "started":
                        now,
                    "point_seconds":
                        0
                }

            else:

                session = voice_sessions[key]

                # Đổi room
                if (
                    session["channel_id"]
                    != member.voice.channel.id
                ):

                    session["channel_id"] = (
                        member.voice.channel.id
                    )

                    session["started"] = now

                    session["point_seconds"] = 0

        # =================================================
        # XỬ LÝ SESSION
        # =================================================

        for key in list(
            voice_sessions.keys()
        ):

            key_guild_id, user_id = key

            if key_guild_id != guild.id:
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

            elapsed = now - session["started"]

            if elapsed <= 0:
                continue

            session["started"] = now

            # =================================================
            # CỘNG THỜI GIAN VOICE
            # =================================================

            await add_voice_time(
                member,
                int(elapsed)
            )

            # =================================================
            # TÍNH TIẾN ĐỘ CỘNG ĐIỂM 5 PHÚT
            # =================================================

            session["point_seconds"] += elapsed

        # =================================================
        # TÌM CÁC CẶP CÙNG ROOM
        # =================================================

        rooms = {}

        for member in guild.members:

            if member.bot:
                continue

            if member.voice is None:
                continue

            if member.voice.channel is None:
                continue

            channel_id = (
                member.voice.channel.id
            )

            if channel_id not in rooms:

                rooms[channel_id] = []

            rooms[channel_id].append(
                member
            )

        # =================================================
        # CỘNG ĐIỂM ĐÚNG MỖI 5 PHÚT
        # =================================================

        for members in rooms.values():

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

                    if not roles_same(
                        user1,
                        user2
                    ):
                        continue

                    key1 = (
                        guild.id,
                        user1.id
                    )

                    key2 = (
                        guild.id,
                        user2.id
                    )

                    if (
                        key1 not in voice_sessions
                        or key2 not in voice_sessions
                    ):
                        continue

                    session1 = voice_sessions[key1]
                    session2 = voice_sessions[key2]

                    # Hai người phải ở cùng room
                    if (
                        session1["channel_id"]
                        != session2["channel_id"]
                    ):
                        continue

                    # Lấy thời gian nhỏ hơn
                    # để đảm bảo cả hai đã ở room
                    # đủ thời gian
                    available_seconds = min(
                        session1["point_seconds"],
                        session2["point_seconds"]
                    )

                    if available_seconds >= VOICE_POINT_INTERVAL:

                        times = int(
                            available_seconds
                            // VOICE_POINT_INTERVAL
                        )

                        # Reset phần đã dùng
                        used_seconds = (
                            times
                            * VOICE_POINT_INTERVAL
                        )

                        session1[
                            "point_seconds"
                        ] -= used_seconds

                        session2[
                            "point_seconds"
                        ] -= used_seconds

                        for _ in range(times):

                            await add_pair_point(
                                user1,
                                user2,
                                VOICE_POINT_AMOUNT,
                                "🎧 Cùng Voice đủ 5 phút."
                            )


# =====================================================
# LỆNH TƯƠNG TÁC
# =====================================================

async def interaction(
    ctx,
    member,
    action
):

    if member is None:

        await ctx.send(
            f"❌ Dùng: `?{action} @người`"
        )

        return

    if member.bot:

        await ctx.send(
            "❌ Không thể tương tác với bot."
        )

        return

    if member.id == ctx.author.id:

        await ctx.send(
            "😅 Bạn không thể tự tương tác với chính mình!"
        )

        return

    # =================================================
    # ROLE
    # =================================================

    if not roles_same(
        ctx.author,
        member
    ):

        await ctx.send(
            "❌ Hai người không có "
            "bộ role giống nhau."
        )

        return

    # =================================================
    # COOLDOWN
    # =================================================

    pair_id = get_pair_id(
        ctx.author,
        member
    )

    cooldown_key = (
        f"{ctx.guild.id}:{pair_id}"
    )

    now = time.time()

    last = interaction_cooldowns.get(
        cooldown_key,
        0
    )

    remaining = (
        INTERACTION_COOLDOWN
        - (now - last)
    )

    if remaining > 0:

        await ctx.send(
            f"⏳ Hai bạn đang cooldown. "
            f"Thử lại sau **{remaining:.0f} giây**."
        )

        return

    interaction_cooldowns[
        cooldown_key
    ] = now

    # =================================================
    # GIF
    # =================================================

    gif = random.choice(
        GIFS[action]
    )

    messages = {

        "om":
            f"🤗 **{ctx.author.mention}** "
            f"đã ôm **{member.mention}**!",

        "hon":
            f"💋 **{ctx.author.mention}** "
            f"đã gửi một nụ hôn tới **{member.mention}**!",

        "thom":
            f"😊 **{ctx.author.mention}** "
            f"đã thơm má **{member.mention}**!"
    }

    # =================================================
    # CỘNG ĐIỂM
    # =================================================

    await add_pair_point(
        ctx.author,
        member,
        INTERACTION_POINT_AMOUNT,
        f"💞 Tương tác: {action}"
    )

    # =================================================
    # GỬI GIF
    # =================================================

    await ctx.send(
        f"{messages[action]}\n{gif}"
    )


# =====================================================
# ?ÔM
# =====================================================

@bot.command(
    name="ôm"
)
async def om(
    ctx,
    member: discord.Member = None
):

    await interaction(
        ctx,
        member,
        "om"
    )


# =====================================================
# ?HÔN
# =====================================================

@bot.command(
    name="hôn"
)
async def hon(
    ctx,
    member: discord.Member = None
):

    await interaction(
        ctx,
        member,
        "hon"
    )


# =====================================================
# ?THƠM
# =====================================================

@bot.command(
    name="thơm"
)
async def thom(
    ctx,
    member: discord.Member = None
):

    await interaction(
        ctx,
        member,
        "thom"
    )


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
            f"{message.guild.id}:{pid
