import os
import io
import asyncio
import discord
from discord.ext import commands

TOKEN = os.getenv("TOKEN")

intents = discord.Intents.default()

bot = commands.Bot(
    command_prefix="!",
    intents=intents
)


@bot.event
async def on_ready():
    print(f"Bot đã đăng nhập: {bot.user}")
    try:
        synced = await bot.tree.sync()
        print(f"Đã sync {len(synced)} slash commands")
    except Exception as e:
        print(f"Lỗi sync command: {e}")


@bot.tree.command(
    name="copyemoji",
    description="Copy toàn bộ emoji từ server nguồn vào server hiện tại"
)
async def copyemoji(interaction: discord.Interaction, server_id: str):

    # Kiểm tra quyền người dùng
    if not interaction.user.guild_permissions.manage_guild:
        await interaction.response.send_message(
            "❌ Bạn cần quyền **Manage Server** để sử dụng lệnh này.",
            ephemeral=True
        )
        return

    # Kiểm tra server đích
    destination = interaction.guild

    # Tìm server nguồn
    try:
        source = bot.get_guild(int(server_id))
    except ValueError:
        await interaction.response.send_message(
            "❌ Server ID không hợp lệ.",
            ephemeral=True
        )
        return

    if source is None:
        await interaction.response.send_message(
            "❌ Bot chưa được thêm vào server nguồn.\n"
            "Hãy thêm bot vào cả server nguồn và server đích.",
            ephemeral=True
        )
        return

    await interaction.response.defer()

    emojis = source.emojis

    if not emojis:
        await interaction.followup.send(
            "❌ Server nguồn không có emoji."
        )
        return

    copied = 0
    failed = 0
    skipped = 0

    # Lấy tên emoji hiện có ở server đích
    existing_names = {
        emoji.name.lower()
        for emoji in destination.emojis
    }

    for emoji in emojis:

        # Bỏ qua nếu trùng tên
        if emoji.name.lower() in existing_names:
            skipped += 1
            continue

        try:
            # Tải emoji
            data = await emoji.read()

            # Tạo emoji mới
            await destination.create_custom_emoji(
                name=emoji.name,
                image=data,
                reason=f"Copy emoji từ {source.name}"
            )

            copied += 1
            existing_names.add(emoji.name.lower())

            # Tránh gửi request quá nhanh
            await asyncio.sleep(1)

        except discord.HTTPException as e:
            failed += 1
            print(
                f"Không copy được {emoji.name}: {e}"
            )

        except Exception as e:
            failed += 1
            print(
                f"Lỗi {emoji.name}: {e}"
            )

    await interaction.followup.send(
        f"✅ **Hoàn tất copy emoji!**\n\n"
        f"📥 Server nguồn: **{source.name}**\n"
        f"📤 Server đích: **{destination.name}**\n\n"
        f"✅ Đã copy: **{copied}**\n"
        f"⏭️ Bỏ qua: **{skipped}**\n"
        f"❌ Lỗi: **{failed}**"
    )


bot.run(TOKEN)
