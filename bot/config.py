"""環境変数から Bot 設定を読み込むモジュール。"""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
from typing import Dict, Optional

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


def load_role_settings() -> Dict:
    """settings.json からロール設定を読み込む。"""
    settings_path = Path(__file__).parent / "settings.json"
    if not settings_path.exists():
        raise FileNotFoundError(f"設定ファイルが見つかりません: {settings_path}")

    with open(settings_path, "r", encoding="utf-8") as f:
        return json.load(f)


class RoleSettingsManager:
    """ロール設定を管理するクラス。メモリ内での設定変更をサポート。"""

    def __init__(self) -> None:
        self._base_settings = load_role_settings()
        self._runtime_overrides: Dict = {}

    def get_settings(self) -> Dict:
        """現在の設定を取得する（オーバーライドを適用した状態）。"""
        # runtime_overridesが空でない場合は、それを優先して返す
        if self._runtime_overrides:
            return self._runtime_overrides.copy()
        return self._base_settings.copy()

    def set_override(self, key: str, value) -> None:
        """ランタイムでの設定オーバーライドを設定する。"""
        self._runtime_overrides[key] = value

    def set_all_settings(self, settings: Dict) -> None:
        """設定全体をオーバーライドする。"""
        self._runtime_overrides = settings.copy()

    def clear_overrides(self) -> None:
        """すべてのオーバーライドをクリアする。"""
        self._runtime_overrides.clear()

    def reload_from_file(self) -> None:
        """ファイルから設定を再読み込みする。"""
        self._base_settings = load_role_settings()


# グローバルな設定マネージャーのインスタンス
role_settings_manager = RoleSettingsManager()


