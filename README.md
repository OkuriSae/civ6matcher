# Civ6 Matcher Discord Bot

`discord.py` を利用して Civilization VI のマッチングを支援する Discord Bot です。募集メッセージの作成・参加者管理・チーム分けを行う `/bo` コマンドと、動作確認用の `/ping` コマンドを提供しています。

## 必要環境

- Python 3.11 以上
- Discord Bot アカウントとトークン
- （任意）特定ギルドにのみコマンドを同期する場合はギルド ID

## セットアップ手順

1. 依存パッケージをインストールします。
   ```bash
   python -m venv .venv
   # macOS / Linux
   source .venv/bin/activate
   # Windows (PowerShell)
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```

2. `.env` ファイルを作成し、以下の内容を設定します。

   ```text
   DISCORD_BOT_TOKEN=ここにボットトークン
   # 任意設定
   DISCORD_COMMAND_PREFIX=!
   DISCORD_GUILD_ID=123456789012345678
   ```

   - `DISCORD_BOT_TOKEN` は必須です。
   - `DISCORD_COMMAND_PREFIX` を変更するとハイブリッドコマンドのプレフィックスが変わります。
   - `DISCORD_GUILD_ID` を設定すると、そのギルドにのみスラッシュコマンドを同期します（未設定の場合はグローバル同期）。

## 実行方法

```bash
python -m bot.main
```

起動後、Bot が Discord に接続すると以下のコマンドが利用できます。

## コマンド

- `/bo [募集タイトル]`
  - チャンネル名に応じて対応する募集ロールをメンションし、埋め込みメッセージを生成します。
  - 参加者は👋リアクションで参加・離脱でき、最大 12 名までの参加者一覧と補欠リストが自動更新されます。
  - ⚔️ リアクションで、チーム表示をトグルし、参加者のロールに応じた重み付けをもとにバランスの取れたチーム分けを行います。
  - P/U/7/L ボタンを利用したマップ投票ができます。（投票用なのでBotとしては何も起こりません）
  - 📢 リアクションで、現在の参加者をまとめてメンションできます。（補欠にはメンションは飛びません）

- `/ping`
  - Bot の応答時間をミリ秒単位で返します。

## 補足

- `.env` の読み込みには `python-dotenv` を利用しています。環境変数を直接設定して実行することも可能です。
- リアクションに利用するロール ID や重み付け対象ロール ID は `bot/commands/bo.py` 内で定義しています。サーバー構成に合わせて編集してください。
- リポジトリには `dockerfile` と `docker-compose.yml` が含まれていますが、現状は開発用のサンプルです。利用する場合は必要に応じて `volumes` や依存パッケージの定義を調整してください。

## ディレクトリ構成

```
civ6matcher/
├── bot/
│   ├── __init__.py
│   ├── config.py
│   ├── main.py
│   └── commands/
│       ├── __init__.py
│       ├── bo.py
│       └── ping.py
├── docker-compose.yml
├── dockerfile
├── README.md
└── requirements.txt
```

## ホスティングTIPS

以下を参考にしてください

[Dockerを用いたDiscordBOTの環境構築をGCE上でやってみた](https://zenn.dev/mixi/articles/97a39d8d6d9890)


