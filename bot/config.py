"""環境変数から Bot 設定を読み込むモジュール。"""

from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Optional

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    token: str
    command_prefix: str = "!"
    guild_id: Optional[int] = None


def load_settings() -> Settings:
    """環境変数から Bot 設定を読み込む。"""
    token = os.getenv("DISCORD_BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError(
            "環境変数 DISCORD_BOT_TOKEN が設定されていません。"
        )

    command_prefix = os.getenv("DISCORD_COMMAND_PREFIX", "!").strip() or "!"

    guild_id_raw = os.getenv("DISCORD_GUILD_ID", "").strip()
    guild_id = int(guild_id_raw) if guild_id_raw.isdigit() else None

    return Settings(
        token=token,
        command_prefix=command_prefix,
        guild_id=guild_id,
    )


settings = load_settings()


