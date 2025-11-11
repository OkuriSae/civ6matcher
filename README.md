# Civ6 Matcher Discord Bot テンプレート

Python と `discord.py` を利用した Discord Bot のテンプレートです。`civ6matcher` プロジェクト用に最小限の構成を用意しています。

## 前提条件

- Python 3.11 以上
- Discord Bot アカウントとトークン

## セットアップ

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp env.example .env
```

`.env` 内の `DISCORD_BOT_TOKEN` を Bot のトークンで置き換えてください。必要に応じてギルド ID やプレフィックスも変更できます。

## 実行

```bash
source .venv/bin/activate
python -m bot.main
```

Bot が起動し、`!ping` コマンドに反応して `Pong!` と返信します。

## ディレクトリ構成

```
civ6matcher/
├── bot/
│   ├── __init__.py
│   ├── config.py
│   ├── main.py
│   └── commands/
│       ├── __init__.py
│       └── ping.py
├── env.example
├── README.md
└── requirements.txt
```


