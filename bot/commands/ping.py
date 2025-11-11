"""基本的な Ping コマンド。"""

from __future__ import annotations

from discord.ext import commands


class Ping(commands.Cog):
    """遅延確認用コマンド。"""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.hybrid_command(name="ping", description="Pong! を返します。")
    async def ping(self, ctx: commands.Context) -> None:
        """Bot の応答性を確認する。"""
        latency_ms = round(self.bot.latency * 1000)
        await ctx.reply(f"Pong! {latency_ms}ms")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Ping(bot))


