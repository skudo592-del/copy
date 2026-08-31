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

# Kênh thông báo điểm
POINT_CHANNEL_ID = int(
    os.getenv("POINT_CHANNEL_ID", "0")
)

# Database điểm
POINTS_FILE = "points.json"


# =====================================================
# CẤU HÌNH ĐIỂM VOICE
# =====================================================

# Cùng Voice đủ 5 phút → +3 điểm
VOICE_POINT_INTERVAL = 5 * 60
VOICE_POINT_AMOUNT = 3


# =====================================================
# CẤU HÌNH TAG
# =====================================================

# Tag → +1 điểm
TAG_POINT_AMOUNT = 1

# Mỗi cặp chỉ được tính tag 1 lần / 5 phút
TAG_COOLDOWN = 5 * 60


# =====================================================
# CẤU HÌNH 100 GIỜ LIÊN TỤC
# =====================================================

# Role nhận khi đủ 100 giờ
VOICE_REWARD_ROLE_ID = 1543920448503291924

# 100 giờ = 360000 giây
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
# GIF API
# =====================================================

async def get_anime_gif(reaction: str):

    url = (
        "https://api.otakugifs.xyz/gif"
        f"?reaction={reaction}"
    )

    try:

        async with aiohttp.ClientSession() as session:

            async with session.get(
                url,
                timeout=5
            ) as response:

                if response.status == 200:

                    data = await response.json()

                    return data.get("url")

    except Exception as e:

        print(
            f"❌ Lỗi lấy GIF {reaction}: {e}"
        )

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

        with open(
            filename,
            "r",
            encoding="utf-8"
        ) as file:

            return json.load(file)

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
        ) as file:

            json.dump(
                data,
                file,
                ensure_ascii=False,
                indent=4
            )

    except Exception as e:

        print(
            f"❌ Lỗi lưu {filename}: {e}"
        )


points = load_json(
    POINTS_FILE
)


# =====================================================
# SESSION
# =====================================================

# Theo dõi phiên Voice 100 giờ
#
# key:
# (guild_id, user_id)
#
# value:
# {
#     "channel_id": ID room,
#     "started": timestamp
# }
#
voice_sessions = {}


# Theo dõi cặp cùng Voice
#
# key:
# (guild_id, channel_id, user_id_1, user_id_2)
#
# value:
# {
#     "started": timestamp,
#     "last_point": timestamp
# }
#
pair_voice_sessions = {}


# Chống spam tag
#
# key:
# guild_id:user1-user2
#
tag_cooldowns = {}


# =====================================================
# HELPER
# =====================================================

def get_allowed_roles(member):

    return tuple(
        sorted(
            role.id
            for role in member.roles
            if role.id in ALLOWED_ROLE_IDS
        )
    )


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


def get_pair_id(user1, user2):

    ids = sorted(
        [
            user1.id,
            user2.id
        ]
    )

    return f"{ids[0]}-{ids[1]}"


def get_pair_points(
    guild_id,
    user1,
    user2
):

    guild_id = str(guild_id)

    pair_id = get_pair_id(
        user1,
        user2
    )

    return points.get(
        guild_id,
        {}
    ).get(
        pair_id,
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

    pair_id = get_pair_id(
        user1,
        user2
    )

    if guild_id not in points:

        points[guild_id] = {}

    if pair_id not in points[guild_id]:

        points[guild_id][pair_id] = 0

    points[guild_id][pair_id] += amount

    save_json(
        POINTS_FILE,
        points
    )

    total = points[guild_id][pair_id]

    print(
        f"💖 {user1.display_name} + "
        f"{user2.display_name} "
        f"→ +{amount} "
        f"| Tổng: {total}"
    )

    # Không bật thông báo nếu không có channel
    if POINT_CHANNEL_ID == 0:
        return True

    channel = user1.guild.get_channel(
        POINT_CHANNEL_ID
    )

    if channel is None:
        return True

    role_names = get_role_names(
        user1
    )

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
# CẤP ROLE 100 GIỜ
# =====================================================

async def give_voice_reward(member):

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
                reason=(
                    "Đã ở Voice liên tục "
                    "đủ 100 giờ"
                )
            )

            print(
                f"🏆 {member.display_name} "
                f"đã nhận role 100 giờ!"
            )

            # Gửi thông báo
            if POINT_CHANNEL_ID != 0:

                channel = member.guild.get_channel(
                    POINT_CHANNEL_ID
                )

                if channel:

                    await channel.send(
                        f"🏆 **CHÚC MỪNG!**\n"
                        f"🎧 {member.mention}\n"
                        f"⏱️ Đã ở Voice "
                        f"**liên tục đủ 100 giờ**!\n"
                        f"🎖️ Đã nhận role "
                        f"{role.mention}"
                    )

        else:

            print(
                f"ℹ️ {member.display_name} "
                f"đã có role 100 giờ."
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

        # =============================================
        # LẤY TẤT CẢ NGƯỜI ĐANG Ở VOICE
        # =============================================

        voice_users = []

        for member in guild.members:

            if member.bot:
                continue

            if member.voice is None:
                continue

            if member.voice.channel is None:
                continue

            voice_users.append(member)

        current_users = {
            member.id
            for member in voice_users
        }

        # =============================================
        # THEO DÕI 100 GIỜ LIÊN TỤC
        # =============================================

        for member in voice_users:

            key = (
                guild.id,
                member.id
            )

            channel_id = (
                member.voice.channel.id
            )

            # -----------------------------------------
            # KIỂM TRA ROLE
            # -----------------------------------------

            reward_role = guild.get_role(
                VOICE_REWARD_ROLE_ID
            )

            # Nếu đã có role thì không cần tính nữa
            if (
                reward_role is not None
                and reward_role in member.roles
            ):

                if key in voice_sessions:
                    del voice_sessions[key]

                continue

            # -----------------------------------------
            # NGƯỜI MỚI VÀO VOICE
            # -----------------------------------------

            if key not in voice_sessions:

                voice_sessions[key] = {
                    "channel_id": channel_id,
                    "started": now
                }

                print(
                    f"🎧 {member.display_name} "
                    f"bắt đầu tính 100 giờ."
                )

                continue

            session = voice_sessions[key]

            # -----------------------------------------
            # ĐỔI ROOM → RESET
            # -----------------------------------------

            if (
                session["channel_id"]
                != channel_id
            ):

                voice_sessions[key] = {
                    "channel_id": channel_id,
                    "started": now
                }

                print(
                    f"🔄 {member.display_name} "
                    f"đổi Voice Room "
                    f"→ RESET 100 giờ."
                )

                continue

            # -----------------------------------------
            # TÍNH THỜI GIAN LIÊN TỤC
            # -----------------------------------------

            continuous_time = (
                now - session["started"]
            )

            # -----------------------------------------
            # ĐỦ 100 GIỜ
            # -----------------------------------------

            if (
                continuous_time
                >= VOICE_REQUIRED_SECONDS
            ):

                await give_voice_reward(
                    member
                )

                if key in voice_sessions:
                    del voice_sessions[key]

                print(
                    f"🏆 {member.display_name} "
                    f"hoàn thành 100 giờ liên tục!"
                )

        # =============================================
        # NGƯỜI RỜI VOICE → RESET
        # =============================================

        for key in list(
            voice_sessions.keys()
        ):

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
                        f"rời Voice "
                        f"→ RESET 100 giờ."
                    )

                del voice_sessions[key]

        # =============================================
        # TẠO DANH SÁCH TỪNG ROOM
        # =============================================

        rooms = {}

        for member in voice_users:

            channel_id = (
                member.voice.channel.id
            )

            if channel_id not in rooms:
                rooms[channel_id] = []

            rooms[channel_id].append(
                member
            )

        # =============================================
        # TÍNH ĐIỂM CẶP CÙNG VOICE
        # =============================================

        active_pair_keys = set()

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

                    ids = sorted(
                        [
                            user1.id,
                            user2.id
                        ]
                    )

                    pair_key = (
                        guild.id,
                        channel_id,
                        ids[0],
                        ids[1]
                    )

                    active_pair_keys.add(
                        pair_key
                    )

                    # ---------------------------------
                    # CẶP MỚI VÀO CÙNG ROOM
                    # ---------------------------------

                    if (
                        pair_key
                        not in pair_voice_sessions
                    ):

                        pair_voice_sessions[
                            pair_key
                        ] = {
                            "started": now,
                            "last_point": now
                        }

                        continue

                    pair_session = (
                        pair_voice_sessions[
                            pair_key
                        ]
                    )

                    elapsed = (
                        now
                        - pair_session[
                            "last_point"
                        ]
                    )

                    # ---------------------------------
                    # ĐỦ 5 PHÚT → +3
                    # ---------------------------------

                    if (
                        elapsed
                        >= VOICE_POINT_INTERVAL
                    ):

                        intervals = int(
                            elapsed
                            // VOICE_POINT_INTERVAL
                        )

                        pair_session[
                            "last_point"
                        ] += (
                            intervals
                            * VOICE_POINT_INTERVAL
                        )

                        amount = (
                            intervals
                            * VOICE_POINT_AMOUNT
                        )

                        await add_pair_point(
                            user1,
                            user2,
                            amount,
                            "🎧 Cùng Voice Room đủ 5 phút."
                        )

        # =============================================
        # XÓA CẶP KHÔNG CÒN CÙNG ROOM
        # =============================================

        for pair_key in list(
            pair_voice_sessions.keys()
        ):

            if (
                pair_key
                not in active_pair_keys
            ):

                del pair_voice_sessions[
                    pair_key
                ]


# =====================================================
# MESSAGE
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

    # =============================================
    # TAG → +1 ĐIỂM
    # =============================================

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

        pair_id = get_pair_id(
            author,
            target
        )

        cooldown_key = (
            f"{message.guild.id}:"
            f"{pair_id}"
        )

        now = time.time()

        last_tag = tag_cooldowns.get(
            cooldown_key,
            0
        )

        # Chưa đủ 5 phút
        if (
            now - last_tag
            < TAG_COOLDOWN
        ):

            print(
                f"🛑 Tag cooldown: "
                f"{author.display_name} → "
                f"{target.display_name}"
            )

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


# ==========================
