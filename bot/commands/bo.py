"""募集ロールへのメンションコマンド。"""

from __future__ import annotations

import random
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

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


def get_role_mapping() -> Dict[str, int]:
    """現在のロールマッピング設定を取得する。"""
    settings = role_settings_manager.get_settings()
    return settings.get("channel_role_map", {})


def get_role_weights() -> Dict[str, int]:
    """現在のロール重み設定を取得する。"""
    settings = role_settings_manager.get_settings()
    return settings.get("role_weights", {})


def resolve_role_mention(channel_name: str) -> Optional[str]:
    """チャンネル名に応じてメンション対象ロールを決定する。"""
    role_mapping = get_role_mapping()
    for keyword, role_id in role_mapping.items():
        if keyword in channel_name:
            return f"<@&{role_id}>"
    return None


def parse_user_mention(mention: str) -> Optional[int]:
    """ユーザーメンション形式（<@123456789> または <@!123456789>）からユーザーIDを抽出する。"""
    match = re.match(r"<@!?(\d+)>", mention.strip())
    if match:
        try:
            return int(match.group(1))
        except ValueError:
            return None
    return None


# ここから下は既存コードの続き
@dataclass
class ParticipantEntry:
    key: str
    user_id: Optional[int]
    label: str
    is_dummy: bool = False


@dataclass
class WeightedEntry:
    entry: ParticipantEntry
    weight: int


@dataclass
class TrackedMessage:
    guild_id: int
    channel_id: int
    join_emoji: str
    check_emoji: Optional[str]
    dummy_emoji: Optional[str]
    notify_emoji: Optional[str]
    recruit_emoji: Optional[str]
    participants: List[ParticipantEntry] = field(default_factory=list)
    team_one: List[str] = field(default_factory=list)
    team_two: List[str] = field(default_factory=list)
    dummy_count: int = 0
    teams_visible: bool = False
    is_disbanded: bool = False


class BoManager(commands.Cog):
    """募集 Embed の管理を行う Cog。"""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.tracked_messages: Dict[int, TrackedMessage] = {}
        self.command: Optional[app_commands.Command] = None
        self._register_command()

    def cog_unload(self) -> None:
        if self.command is not None:
            self.bot.tree.remove_command(self.command.name, type=discord.AppCommandType.chat_input)
        self.tracked_messages.clear()

    def _register_command(self) -> None:
        tree = self.bot.tree
        existing = tree.get_command("bo", type=discord.AppCommandType.chat_input)
        if existing is not None:
            tree.remove_command(existing.name, type=existing.type)

        @tree.command(name="bo", description="対応するロールをメンションして募集をかけます。")
        @app_commands.describe(
            start="募集タイトル",
            remove_user="削除するユーザーのメンション（例: <@123456789>）",
            close_game="終了する募集のID",
        )
        async def bo_command(
            interaction: discord.Interaction,
            start: Optional[str] = None,
            remove_user: Optional[str] = None,
            close_game: Optional[str] = None,
        ) -> None:
            await self._handle_bo(interaction, start, remove_user, close_game)

        self.command = bo_command

    async def _handle_bo(
        self,
        interaction: discord.Interaction,
        start: Optional[str],
        remove_user: Optional[str] = None,
        close_game: Optional[str] = None,
    ) -> None:
        # ゲーム終了モード
        if close_game is not None:
            await self._handle_close_game(interaction, close_game)
            return

        # ユーザー削除モード
        if remove_user is not None:
            await self._handle_remove_user(interaction, remove_user)
            return

        channel = interaction.channel
        channel_name = getattr(channel, "name", "") if channel else ""
        role_mention = resolve_role_mention(channel_name)

        if role_mention is None:
            response = "未対応のチャンネルです"
            await interaction.response.send_message(response, ephemeral=True)
            return

        body = start.strip() if start else "募集"
        embed = discord.Embed(
            title=body,
            color=discord.Color.gold(),
        )
        embed.add_field(name="参加者", value="なし", inline=False)

        content = role_mention

        await interaction.response.send_message(
            content=content,
            embed=embed,
            allowed_mentions=discord.AllowedMentions(roles=True),
        )
        sent_message = await interaction.original_response()
        if sent_message is None or interaction.guild_id is None:
            return

        plus_one = discord.PartialEmoji(name="👋")
        try:
            await sent_message.add_reaction(plus_one)
        except discord.HTTPException:
            plus_one = discord.PartialEmoji(name="+1")
            try:
                await sent_message.add_reaction(plus_one)
            except discord.HTTPException:
                plus_one = None

        check = discord.PartialEmoji(name="⚔️")
        try:
            await sent_message.add_reaction(check)
        except discord.HTTPException:
            check = None

        extra_reactions = [
            discord.PartialEmoji(name="🇵"),
            discord.PartialEmoji(name="🇺"),
            discord.PartialEmoji(name="7️⃣"),
            discord.PartialEmoji(name="🇱"),
        ]
        for reaction in extra_reactions:
            try:
                await sent_message.add_reaction(reaction)
            except discord.HTTPException:
                continue

        notify = discord.PartialEmoji(name="📢")
        try:
            await sent_message.add_reaction(notify)
        except discord.HTTPException:
            notify = None

        recruit = discord.PartialEmoji(name="♻️")
        try:
            await sent_message.add_reaction(recruit)
        except discord.HTTPException:
            recruit = None

        participants: List[ParticipantEntry] = []
        if interaction.user and interaction.guild_id:
            # 実行ユーザーを事前に fetch してキャッシュに保存
            guild = self.bot.get_guild(interaction.guild_id)
            if guild is not None:
                try:
                    await guild.fetch_member(interaction.user.id)
                except discord.HTTPException:
                    try:
                        await self.bot.fetch_user(interaction.user.id)
                    except discord.HTTPException:
                        pass
            
            participants.append(
                ParticipantEntry(
                    key=f"user:{interaction.user.id}",
                    user_id=interaction.user.id,
                    label="",
                    is_dummy=False,
                )
            )

        tracked = TrackedMessage(
            guild_id=interaction.guild_id,
            channel_id=sent_message.channel.id,
            join_emoji=plus_one.name if plus_one else "👋",
            check_emoji=check.name if check else None,
            dummy_emoji="➕",
            notify_emoji=notify.name if notify else "📢",
            recruit_emoji=recruit.name if recruit else "♻️",
            participants=participants,
        )
        self.tracked_messages[sent_message.id] = tracked

        if participants:
            await self._update_embed(sent_message.id)

        # ここでの埋め込み再編集は不要（_update_embed 側でIDを常時追記）

    async def _handle_remove_user(
        self,
        interaction: discord.Interaction,
        remove_user: str,
    ) -> None:
        """参加者からユーザーを削除する。"""
        # ユーザーメンション形式をパース
        user_id = parse_user_mention(remove_user)
        if user_id is None:
            await interaction.response.send_message(
                "無効なユーザーメンション形式です。例: <@123456789>",
                ephemeral=True,
            )
            return

        # チャンネル内の最新の募集メッセージを探す
        channel = interaction.channel
        if channel is None:
            await interaction.response.send_message(
                "チャンネル情報を取得できませんでした。",
                ephemeral=True,
            )
            return

        # 同じチャンネルの tracked_messages を探す
        channel_tracked = [
            (msg_id, data)
            for msg_id, data in self.tracked_messages.items()
            if data.channel_id == channel.id
        ]

        if not channel_tracked:
            await interaction.response.send_message(
                "このチャンネルに募集メッセージが見つかりませんでした。",
                ephemeral=True,
            )
            return

        # 最新のメッセージを取得（メッセージIDが大きいもの）
        latest_msg_id, data = max(channel_tracked, key=lambda x: x[0])

        # 参加者リストから該当ユーザーを削除
        entry_index = next(
            (
                index
                for index, entry in enumerate(data.participants)
                if entry.user_id == user_id
            ),
            None,
        )

        if entry_index is None:
            await interaction.response.send_message(
                f"<@{user_id}> は参加者リストに登録されていません。",
                ephemeral=True,
            )
            return

        removed_entry = data.participants.pop(entry_index)
        # チーム分けからも削除
        data.team_one = [key for key in data.team_one if key != removed_entry.key]
        data.team_two = [key for key in data.team_two if key != removed_entry.key]

        # Embed を更新
        await interaction.response.send_message(
            f"<@{user_id}> を参加者リストから削除しました。",
            ephemeral=True,
        )
        await self._update_embed(latest_msg_id)

    async def _handle_close_game(
        self,
        interaction: discord.Interaction,
        close_game: str,
    ) -> None:
        """ゲーム募集を終了する。"""
        # メッセージID（数値）のみを受け付ける
        try:
            message_id = int(close_game.strip())
        except (TypeError, ValueError):
            await interaction.response.send_message(
                "無効なメッセージIDです。数値のみを入力してください。",
                ephemeral=True,
            )
            return

        # tracked_messages から該当メッセージを取得
        data = self.tracked_messages.get(message_id)
        if data is None:
            await interaction.response.send_message(
                "指定されたメッセージIDの募集が見つかりませんでした。",
                ephemeral=True,
            )
            return

        # 既に終了済みかチェック
        if data.is_disbanded:
            await interaction.response.send_message(
                "この募集は既に終了しています。",
                ephemeral=True,
            )
            return

        # チャンネルを取得
        channel = self.bot.get_channel(data.channel_id)
        if channel is None:
            try:
                channel = await self.bot.fetch_channel(data.channel_id)
            except discord.HTTPException:
                await interaction.response.send_message(
                    "チャンネル情報を取得できませんでした。",
                    ephemeral=True,
                )
                return

        # メッセージを取得
        try:
            message = await channel.fetch_message(message_id)
        except discord.HTTPException:
            await interaction.response.send_message(
                "メッセージを取得できませんでした。",
                ephemeral=True,
            )
            return

        # Embed の色を赤に変更し、タイトルに【解散】を追加
        if message.embeds:
            embed = message.embeds[0]
            new_embed = discord.Embed.from_dict(embed.to_dict())
            new_embed.color = discord.Color.red()
            # タイトルに【解散】を追加（既に追加されていない場合）
            if new_embed.title and not new_embed.title.startswith("【解散】"):
                new_embed.title = f"【解散】{new_embed.title}"
            elif not new_embed.title:
                new_embed.title = "【解散】"
            try:
                await message.edit(embed=new_embed)
            except discord.HTTPException:
                pass

        # 参加者にメンションして解散メッセージを送信
        participant_user_ids = [
            entry.user_id
            for entry in data.participants
            if not entry.is_dummy and entry.user_id is not None
        ]

        if participant_user_ids:
            # 参加者を事前に fetch してキャッシュに保存
            if data.guild_id:
                guild = self.bot.get_guild(data.guild_id)
                if guild is not None:
                    for user_id in participant_user_ids:
                        try:
                            await guild.fetch_member(user_id)
                        except discord.HTTPException:
                            try:
                                await self.bot.fetch_user(user_id)
                            except discord.HTTPException:
                                pass

            mentions = await self._resolve_display_mentions(data.guild_id, participant_user_ids)
            mention_text = " ".join(mentions)
            content = f"{mention_text} 解散しました"

            try:
                await channel.send(
                    content,
                    allowed_mentions=discord.AllowedMentions(users=True, roles=False, everyone=False),
                )
            except discord.HTTPException:
                pass

        # 終了フラグを設定（リアクションイベントが発火しないようにする）
        data.is_disbanded = True

        await interaction.response.send_message(
            "ゲーム募集を終了しました。",
            ephemeral=True,
        )

    @commands.Cog.listener(name="on_raw_reaction_add")
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent) -> None:
        data = self.tracked_messages.get(payload.message_id)
        if data is None or payload.guild_id is None:
            return
        if payload.user_id == self.bot.user.id:
            return
        # 終了済みの募集ではイベントを発火しない
        if data.is_disbanded:
            return

        if self._is_tracked_emoji(payload.emoji, data.join_emoji):
            if not any(entry.user_id == payload.user_id for entry in data.participants):
                # ユーザー情報を事前に fetch してキャッシュに保存
                guild = self.bot.get_guild(payload.guild_id)
                if guild is not None:
                    try:
                        await guild.fetch_member(payload.user_id)
                    except discord.HTTPException:
                        try:
                            await self.bot.fetch_user(payload.user_id)
                        except discord.HTTPException:
                            pass
                
                entry = ParticipantEntry(
                    key=f"user:{payload.user_id}",
                    user_id=payload.user_id,
                    label="",
                    is_dummy=False,
                )
                data.participants.append(entry)
                await self._update_embed(payload.message_id)
            return

        if self._is_tracked_emoji(payload.emoji, data.check_emoji):
            data.teams_visible = True
            await self._assign_teams(payload.message_id)
            return

        if self._is_tracked_emoji(payload.emoji, data.dummy_emoji):
            await self._handle_dummy_reaction(payload)
            return

        if self._is_tracked_emoji(payload.emoji, data.notify_emoji):
            await self._handle_notify_reaction(payload)
            return

        if self._is_tracked_emoji(payload.emoji, data.recruit_emoji):
            await self._handle_recruit_reaction(payload)
            return

    @commands.Cog.listener(name="on_raw_reaction_remove")
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent) -> None:
        data = self.tracked_messages.get(payload.message_id)
        if data is None or payload.guild_id is None:
            return
        if payload.user_id == self.bot.user.id:
            return
        # 終了済みの募集ではイベントを発火しない
        if data.is_disbanded:
            return

        if not self._is_tracked_emoji(payload.emoji, data.join_emoji):
            return

        entry_index = next(
            (index for index, entry in enumerate(data.participants) if entry.user_id == payload.user_id),
            None,
        )
        if entry_index is not None:
            removed_entry = data.participants.pop(entry_index)
            data.team_one = [key for key in data.team_one if key != removed_entry.key]
            data.team_two = [key for key in data.team_two if key != removed_entry.key]
            await self._update_embed(payload.message_id)

    async def _assign_teams(self, message_id: int) -> None:
        data = self.tracked_messages.get(message_id)
        if data is None or not data.participants:
            return

        main_entries = data.participants[:12]
        if not main_entries:
            return

        if len(main_entries) % 2 != 0:
            data.team_one.clear()
            data.team_two.clear()
            await self._update_embed(message_id)
            return

        weighted_entries = await self._with_weights(main_entries, data.guild_id)
        team_one, team_two = self._balanced_split(weighted_entries)
        team_one, team_two = self._auto_balance_sizes(team_one, team_two)
        data.team_one = [item.entry.key for item in team_one]
        data.team_two = [item.entry.key for item in team_two]
        await self._update_embed(message_id)

    async def _update_embed(self, message_id: int) -> None:
        data = self.tracked_messages.get(message_id)
        if data is None:
            return

        channel = self.bot.get_channel(data.channel_id)
        if channel is None:
            try:
                channel = await self.bot.fetch_channel(data.channel_id)
            except discord.HTTPException:
                self.tracked_messages.pop(message_id, None)
                return

        try:
            message = await channel.fetch_message(message_id)
        except discord.HTTPException:
            self.tracked_messages.pop(message_id, None)
            return

        if not message.embeds:
            return

        base_embed = message.embeds[0]
        new_embed = discord.Embed.from_dict(base_embed.to_dict())
        main_entries = data.participants[:12]
        reserve_entries = data.participants[12:]

        # 参加者ユーザーを事前に fetch してキャッシュに保存
        if data.guild_id:
            guild = self.bot.get_guild(data.guild_id)
            if guild is not None:
                all_user_ids = [
                    entry.user_id
                    for entry in data.participants
                    if not entry.is_dummy and entry.user_id is not None
                ]
                for user_id in all_user_ids:
                    try:
                        await guild.fetch_member(user_id)
                    except discord.HTTPException:
                        try:
                            await self.bot.fetch_user(user_id)
                        except discord.HTTPException:
                            pass

        participant_mentions = await self._format_entries(
            data.guild_id,
            main_entries,
            include_order=True,
            start_index=1,
        )
        has_participants = bool(participant_mentions)

        field_value = "\n".join(participant_mentions) if has_participants else "なし"
        field_index = self._find_participant_field_index(new_embed.fields)
        if field_index is None:
            new_embed.add_field(name="参加者", value=field_value, inline=False)
        else:
            new_embed.set_field_at(field_index, name="参加者", value=field_value, inline=False)

        # 補欠情報
        reserve_mentions = await self._format_entries(
            data.guild_id,
            reserve_entries,
            include_order=True,
            start_index=len(main_entries) + 1,
        )
        self._set_embed_field(new_embed, "補欠", reserve_mentions, empty_value="なし", remove_if_empty=True)

        if data.teams_visible:
            # チーム情報を最新化（先頭12名のみ対象）
            main_keys = {entry.key for entry in main_entries}
            data.team_one = [key for key in data.team_one if key in main_keys]
            data.team_two = [key for key in data.team_two if key in main_keys]

            team_one_entries = self._entries_from_keys(data, data.team_one)
            team_two_entries = self._entries_from_keys(data, data.team_two)

            team_one_mentions = await self._format_entries(
                data.guild_id,
                team_one_entries,
                include_order=False,
            )
            team_two_mentions = await self._format_entries(
                data.guild_id,
                team_two_entries,
                include_order=False,
            )

            self._set_embed_field(
                new_embed,
                "チーム1",
                team_one_mentions,
                empty_value="未割り当て",
                joiner=", ",
            )
            self._set_embed_field(
                new_embed,
                "チーム2",
                team_two_mentions,
                empty_value="未割り当て",
                joiner=", ",
            )
        else:
            # チーム欄を削除
            self._remove_field(new_embed, "チーム1")
            self._remove_field(new_embed, "チーム2")

        # フィールド順序を固定
        order = ["参加者", "補欠"]
        if data.teams_visible:
            order.extend(["チーム1", "チーム2"])
        self._reorder_fields(new_embed, order)

        # タイトル直下にメッセージIDを常時表示
        new_embed.description = f"`ID: {message_id}`"

        await message.edit(embed=new_embed, allowed_mentions=discord.AllowedMentions.none())

    async def _handle_dummy_reaction(self, payload: discord.RawReactionActionEvent) -> None:
        data = self.tracked_messages.get(payload.message_id)
        if data is None:
            return

        data.dummy_count += 1
        label = f"ダミー{data.dummy_count}"
        entry = ParticipantEntry(
            key=f"dummy:{data.dummy_count}",
            user_id=None,
            label=label,
            is_dummy=True,
        )
        data.participants.append(entry)
        await self._update_embed(payload.message_id)
        await self._remove_user_reaction(payload)

    async def _handle_notify_reaction(self, payload: discord.RawReactionActionEvent) -> None:
        data = self.tracked_messages.get(payload.message_id)
        if data is None:
            await self._remove_user_reaction(payload)
            return

        main_entries = data.participants[:12]
        target_entries = [entry for entry in main_entries if not entry.is_dummy and entry.user_id is not None]
        if not target_entries:
            await self._remove_user_reaction(payload)
            return

        user_ids = [entry.user_id for entry in target_entries if entry.user_id is not None]
        
        # 参加者ユーザーを事前に fetch してキャッシュに保存
        if payload.guild_id:
            guild = self.bot.get_guild(payload.guild_id)
            if guild is not None:
                for user_id in user_ids:
                    try:
                        await guild.fetch_member(user_id)
                    except discord.HTTPException:
                        try:
                            await self.bot.fetch_user(user_id)
                        except discord.HTTPException:
                            pass

        mentions = await self._resolve_display_mentions(payload.guild_id, user_ids) if payload.guild_id else []
        if not mentions:
            await self._remove_user_reaction(payload)
            return

        channel = self.bot.get_channel(payload.channel_id)
        if channel is None:
            try:
                channel = await self.bot.fetch_channel(payload.channel_id)
            except discord.HTTPException:
                await self._remove_user_reaction(payload)
                return

        # 発火ユーザーを事前に fetch してキャッシュに保存
        if payload.guild_id:
            guild = self.bot.get_guild(payload.guild_id)
            if guild is not None:
                try:
                    await guild.fetch_member(payload.user_id)
                except discord.HTTPException:
                    try:
                        await self.bot.fetch_user(payload.user_id)
                    except discord.HTTPException:
                        pass

        trigger_mention = ""
        if payload.guild_id:
            trigger_mentions = await self._resolve_display_mentions(payload.guild_id, [payload.user_id])
            if trigger_mentions:
                trigger_mention = f" (by {trigger_mentions[0]})"
        if not trigger_mention:
            trigger_mention = f" (by <@{payload.user_id}>)"

        message = " ".join(mentions) + trigger_mention
        try:
            await channel.send(message, allowed_mentions=discord.AllowedMentions(users=True, roles=False, everyone=False))
        except discord.HTTPException:
            pass

        await self._remove_user_reaction(payload)

    async def _handle_recruit_reaction(self, payload: discord.RawReactionActionEvent) -> None:
        data = self.tracked_messages.get(payload.message_id)
        if data is None:
            await self._remove_user_reaction(payload)
            return

        channel = self.bot.get_channel(payload.channel_id)
        if channel is None:
            try:
                channel = await self.bot.fetch_channel(payload.channel_id)
            except discord.HTTPException:
                await self._remove_user_reaction(payload)
                return

        channel_name = getattr(channel, "name", "")
        role_mention = resolve_role_mention(channel_name)
        if role_mention is None:
            await self._remove_user_reaction(payload)
            return

        main_entries = data.participants[:12]
        participant_entries = [entry for entry in main_entries if not entry.is_dummy and entry.user_id is not None]
        participant_count = len(participant_entries)

        if participant_count <= 8:
            min_needed = 8 - participant_count
            max_needed = 12 - participant_count
            message_range = f"@{min_needed}-{max_needed}"
        elif participant_count in (9, 10):
            min_needed = 10 - participant_count
            max_needed = 12 - participant_count
            message_range = f"@{min_needed}-{max_needed}"
        elif participant_count == 11:
            message_range = "@1"
        else:
            await self._remove_user_reaction(payload)
            return

        # 発火ユーザーを事前に fetch してキャッシュに保存
        if payload.guild_id:
            guild = self.bot.get_guild(payload.guild_id)
            if guild is not None:
                try:
                    await guild.fetch_member(payload.user_id)
                except discord.HTTPException:
                    try:
                        await self.bot.fetch_user(payload.user_id)
                    except discord.HTTPException:
                        pass

        trigger_mention = ""
        if payload.guild_id:
            trigger_mentions = await self._resolve_display_mentions(payload.guild_id, [payload.user_id])
            if trigger_mentions:
                trigger_mention = trigger_mentions[0]
        if not trigger_mention:
            trigger_mention = f"<@{payload.user_id}>"

        message = f"{trigger_mention} to {role_mention} {message_range}"
        try:
            await channel.send(
                message,
                allowed_mentions=discord.AllowedMentions(users=True, roles=True, everyone=False),
            )
        except discord.HTTPException:
            pass

        await self._remove_user_reaction(payload)

    async def _remove_user_reaction(self, payload: discord.RawReactionActionEvent) -> None:
        channel = self.bot.get_channel(payload.channel_id)
        if channel is None:
            try:
                channel = await self.bot.fetch_channel(payload.channel_id)
            except discord.HTTPException:
                return

        try:
            message = await channel.fetch_message(payload.message_id)
        except discord.HTTPException:
            return

        try:
            await message.remove_reaction(payload.emoji, discord.Object(id=payload.user_id))
        except discord.HTTPException:
            return

    def _entries_from_keys(self, data: TrackedMessage, keys: Sequence[str]) -> List[ParticipantEntry]:
        entries: List[ParticipantEntry] = []
        for key in keys:
            entry = next((item for item in data.participants if item.key == key), None)
            if entry is not None:
                entries.append(entry)
        return entries

    async def _format_entries(
        self,
        guild_id: int,
        entries: Sequence[ParticipantEntry],
        *,
        include_order: bool,
        start_index: int = 1,
    ) -> List[str]:
        user_entries = [entry for entry in entries if not entry.is_dummy and entry.user_id is not None]
        mentions_map: Dict[int, str] = {}
        if user_entries:
            user_ids = [entry.user_id for entry in user_entries if entry.user_id is not None]
            mentions = await self._resolve_display_mentions(guild_id, user_ids)
            for entry, mention in zip(user_entries, mentions):
                if entry.user_id is not None:
                    mentions_map[entry.user_id] = mention

        formatted: List[str] = []
        for index, entry in enumerate(entries):
            if entry.is_dummy:
                display = entry.label
            elif entry.user_id is not None:
                display = mentions_map.get(entry.user_id, f"<@{entry.user_id}>")
            else:
                display = entry.label

            if include_order:
                prefix = f"{start_index + index}. "
                formatted.append(f"{prefix}{display}")
            else:
                formatted.append(display)
        return formatted

    async def _resolve_display_mentions(self, guild_id: int, user_ids: Sequence[int]) -> List[str]:
        guild = self.bot.get_guild(guild_id)
        mentions: List[str] = []

        # 事前にすべてのユーザー情報を fetch してキャッシュに保存
        for user_id in user_ids:
            if guild is not None:
                try:
                    # ギルドメンバーとして fetch（キャッシュに保存される）
                    await guild.fetch_member(user_id)
                except discord.HTTPException:
                    # ギルドメンバーでない場合は、ユーザー情報のみ fetch
                    try:
                        await self.bot.fetch_user(user_id)
                    except discord.HTTPException:
                        pass

        # キャッシュから取得してメンションを生成
        for user_id in user_ids:
            mention: Optional[str] = None

            if guild is not None:
                member = guild.get_member(user_id)
                if member is not None:
                    mention = member.mention

            if mention is None:
                user = self.bot.get_user(user_id)
                if user is not None:
                    mention = getattr(user, "mention", None)
                    if mention is None:
                        mention = f"<@{user_id}>"

            mentions.append(mention or f"<@{user_id}>")

        return mentions

    @staticmethod
    def _find_participant_field_index(fields: Sequence[discord.EmbedField]) -> Optional[int]:
        for index, field in enumerate(fields):
            if field.name == "参加者":
                return index
        return None

    @staticmethod
    def _is_tracked_emoji(emoji: discord.PartialEmoji, target: str) -> bool:
        if target is None:
            return False
        if emoji.id is not None:
            return False
        return emoji.name == target

    @staticmethod
    def _set_embed_field(
        embed: discord.Embed,
        name: str,
        names: Sequence[str],
        *,
        empty_value: str = "未割り当て",
        remove_if_empty: bool = False,
        joiner: str = "\n",
    ) -> None:
        has_values = bool(names)
        if not has_values and remove_if_empty:
            index_list = [index for index, field in enumerate(embed.fields) if field.name == name]
            if index_list:
                embed.remove_field(index_list[0])
            return

        value = joiner.join(names) if has_values else empty_value
        field_indices = [index for index, field in enumerate(embed.fields) if field.name == name]
        if field_indices:
            embed.set_field_at(field_indices[0], name=name, value=value, inline=False)
        else:
            embed.add_field(name=name, value=value, inline=False)

    @staticmethod
    def _remove_field(embed: discord.Embed, name: str) -> None:
        index_list = [index for index, field in enumerate(embed.fields) if field.name == name]
        if index_list:
            embed.remove_field(index_list[0])

    @staticmethod
    def _reorder_fields(embed: discord.Embed, order: Sequence[str]) -> None:
        field_map = {field.name: field for field in embed.fields}
        embed.clear_fields()
        for name in order:
            field = field_map.get(name)
            if field is not None:
                embed.add_field(name=field.name, value=field.value, inline=field.inline)

    async def _with_weights(
        self,
        entries: Sequence[ParticipantEntry],
        guild_id: int,
    ) -> List[WeightedEntry]:
        weighted: List[WeightedEntry] = []
        guild = self.bot.get_guild(guild_id)

        async def resolve_weight(user_id: Optional[int]) -> int:
            role_weights = get_role_weights()
            if user_id is None:
                return role_weights.get("default", 1)
            member = None
            if guild is not None:
                member = guild.get_member(user_id)
                if member is None:
                    try:
                        member = await guild.fetch_member(user_id)
                    except discord.HTTPException:
                        member = None
            if member is None:
                return role_weights.get("default", 1)
            role_ids = {str(role.id) for role in member.roles}
            # role_weights から該当するロールの重みを取得（優先度の高い順）
            for role_id_str, weight in sorted(role_weights.items(), key=lambda x: x[1], reverse=True):
                if role_id_str == "default":
                    continue
                if role_id_str in role_ids:
                    return weight
            return role_weights.get("default", 1)

        for entry in entries:
            weight = await resolve_weight(entry.user_id)
            weighted.append(WeightedEntry(entry=entry, weight=weight))
        return weighted

    @staticmethod
    def _balanced_split(entries: Sequence[WeightedEntry]) -> Tuple[List[WeightedEntry], List[WeightedEntry]]:
        team_one: List[WeightedEntry] = []
        team_two: List[WeightedEntry] = []
        weight_one = 0
        weight_two = 0

        sorted_entries = sorted(
            entries,
            key=lambda item: (item.weight, random.random()),
            reverse=True,
        )

        for entry in sorted_entries:
            weight = entry.weight
            if weight_one <= weight_two:
                team_one.append(entry)
                weight_one += weight
            else:
                team_two.append(entry)
                weight_two += weight

        return team_one, team_two

    @staticmethod
    def _auto_balance_sizes(
        team_one: List[WeightedEntry],
        team_two: List[WeightedEntry],
    ) -> Tuple[List[WeightedEntry], List[WeightedEntry]]:
        while abs(len(team_one) - len(team_two)) > 0:
            larger, smaller = (team_one, team_two) if len(team_one) > len(team_two) else (team_two, team_one)
            if not larger:
                break
            candidate_index = min(range(len(larger)), key=lambda i: larger[i].weight)
            candidate = larger.pop(candidate_index)
            smaller.append(candidate)
        return team_one, team_two


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(BoManager(bot))


