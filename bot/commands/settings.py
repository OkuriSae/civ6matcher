"""設定管理コマンド。"""

from __future__ import annotations

import json
from typing import Optional

try:
    import discord
    from discord import app_commands
    from discord.ext import commands
except ModuleNotFoundError as exc:
    raise ModuleNotFoundError(
        "discord.py がインストールされていません。仮想環境を有効化し、"
        "`pip install -r requirements.txt` を実行してください。"
    ) from exc

from ..config import role_settings_manager


class SettingsManager(commands.Cog):
    """設定管理を行う Cog。"""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="settings", description="Bot の設定を管理します")
    @app_commands.describe(
        action="実行するアクション (show: 表示, set: 設定, clear: クリア, reload: 再読み込み)",
        key="設定キー (channel_role_map または role_weights)",
        value="設定値 (JSON形式の文字列)",
    )
    @app_commands.choices(action=[
        app_commands.Choice(name="show - 現在の設定を表示", value="show"),
        app_commands.Choice(name="set - 設定を上書き", value="set"),
        app_commands.Choice(name="clear - すべてのオーバーライドをクリア", value="clear"),
        app_commands.Choice(name="reload - ファイルから再読み込み", value="reload"),
    ])
    @app_commands.choices(key=[
        app_commands.Choice(name="channel_role_map - チャンネル名とロールIDのマッピング", value="channel_role_map"),
        app_commands.Choice(name="role_weights - ロールIDと重みのマッピング", value="role_weights"),
    ])
    async def settings_command(
        self,
        interaction: discord.Interaction,
        action: str,
        key: Optional[str] = None,
        value: Optional[str] = None,
    ) -> None:
        """設定管理コマンドのハンドラ。"""
        if action == "show":
            await self._handle_show(interaction)
        elif action == "set":
            await self._handle_set(interaction, key, value)
        elif action == "clear":
            await self._handle_clear(interaction)
        elif action == "reload":
            await self._handle_reload(interaction)
        else:
            await interaction.response.send_message(
                f"不明なアクション: {action}",
                ephemeral=True,
            )

    async def _handle_show(self, interaction: discord.Interaction) -> None:
        """現在の設定を表示する。"""
        current_settings = role_settings_manager.get_settings()
        settings_json = json.dumps(current_settings, ensure_ascii=False, indent=2)

        embed = discord.Embed(
            title="現在の設定",
            description=f"```json\n{settings_json}\n```",
            color=discord.Color.blue(),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def _handle_set(
        self,
        interaction: discord.Interaction,
        key: Optional[str],
        value: Optional[str],
    ) -> None:
        """設定を上書きする。"""
        if key is None:
            await interaction.response.send_message(
                "設定キー (key) を指定してください。",
                ephemeral=True,
            )
            return

        if value is None:
            await interaction.response.send_message(
                "設定値 (value) を指定してください。",
                ephemeral=True,
            )
            return

        try:
            parsed_value = json.loads(value)
        except json.JSONDecodeError as e:
            await interaction.response.send_message(
                f"JSON のパースに失敗しました: {e}",
                ephemeral=True,
            )
            return

        role_settings_manager.set_override(key, parsed_value)

        embed = discord.Embed(
            title="設定を更新しました",
            description=f"キー: `{key}`\n値:\n```json\n{json.dumps(parsed_value, ensure_ascii=False, indent=2)}\n```",
            color=discord.Color.green(),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def _handle_clear(self, interaction: discord.Interaction) -> None:
        """すべてのオーバーライドをクリアする。"""
        role_settings_manager.clear_overrides()

        embed = discord.Embed(
            title="設定をクリアしました",
            description="すべてのオーバーライドがクリアされ、ファイルの設定に戻りました。",
            color=discord.Color.orange(),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def _handle_reload(self, interaction: discord.Interaction) -> None:
        """ファイルから設定を再読み込みする。"""
        try:
            role_settings_manager.reload_from_file()
            embed = discord.Embed(
                title="設定を再読み込みしました",
                description="settings.json から設定を再読み込みしました。",
                color=discord.Color.green(),
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception as e:
            embed = discord.Embed(
                title="再読み込みに失敗しました",
                description=f"エラー: {e}",
                color=discord.Color.red(),
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(SettingsManager(bot))
