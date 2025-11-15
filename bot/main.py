"""Discord Bot のエントリーポイント。"""

from __future__ import annotations

import asyncio
import logging

try:
    import discord
    from discord.ext import commands
except ModuleNotFoundError as exc:
    raise ModuleNotFoundError(
        "discord.py がインストールされていません。仮想環境を有効化し、"
        "`pip install -r requirements.txt` を実行してください。"
    ) from exc

from .config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)


COMMAND_EXTENSIONS = (
    "bot.commands.ping",
    "bot.commands.bo",
)


class Civ6MatcherBot(commands.Bot):
    """civ6matcher 向けの Bot クラス。"""

    async def setup_hook(self) -> None:
        for extension in COMMAND_EXTENSIONS:
            await self.load_extension(extension)
            logger.info("拡張機能 %s を読み込みました。", extension)

        if settings.guild_id is not None:
            guild = discord.Object(id=settings.guild_id)
            await self.tree.sync(guild=guild)
            logger.info("スラッシュコマンドをギルド %s に同期しました。", settings.guild_id)
        else:
            await self.tree.sync()
            logger.info("スラッシュコマンドを全体に同期しました。")


def create_bot() -> Civ6MatcherBot:
    intents = discord.Intents.default()
    intents.message_content = True
    intents.members = True  # Server Members Intent を有効化
    bot = Civ6MatcherBot(
        command_prefix=settings.command_prefix,
        intents=intents,
    )
    return bot


async def start_bot() -> None:
    bot = create_bot()
    async with bot:
        await bot.start(settings.token)


def run_bot() -> None:
    """同期コンテキストから Bot を起動する。"""
    try:
        asyncio.run(start_bot())
    except KeyboardInterrupt:
        logger.info("Bot を終了します。")


if __name__ == "__main__":
    run_bot()


