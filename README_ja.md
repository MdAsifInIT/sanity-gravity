# Sanity-Gravity: The Antigravity Sandbox

<p align="center">
  <img src="assets/logo.jpg" alt="Sanity-Gravity Logo" width="300">
</p>

<p align="center">
  <em>Agentic AI IDE 向けに構築された最新の安全なコンテナサンドボックス環境</em>
</p>

<p align="center">
  <a href="README.md">English</a> | <a href="README_zh-TW.md">繁體中文</a> | <a href="README_ja.md">日本語</a>
</p>

---

## TL;DR

**Sanity-Gravity** は、Agentic AI ワークフローに特化して構築された、最新の「設定不要」の GUI サンドボックスです。高リスクな可能性のあるすべての操作を使い捨ての Docker コンテナ内に完全に隔離し、シームレスな XFCE4 デスクトップ体験をブラウザに直接ストリーミングします。

**AI 実験環境を数秒で起動：**

```bash
# 1. ベースイメージを構築
./sanity-cli build

# 2. 永続的なワークスペースボリュームでサンドボックスを起動
./sanity-cli up -v kasm --name my-agent-task --workspace ./ai-workspace
```

安全なデスクトップの準備が完了しました。**https://localhost:8444** にアクセスしてください！
- **ユーザー名**: `(ホスト OS の実際のユーザー名)`
- **パスワード**: `antigravity` (`--password` で設定した値)

📺 **[YouTube でデモを視聴する](https://youtu.be/x0DGKuHyx2A)**

## 目次 (Table of Contents)

- [なぜ Sanity-Gravity なのか？](#なぜ-sanity-gravity-なのか)
- [クイックスタート](#クイックスタート)
- [コマンドリファレンス (`sanity-cli`)](#コマンドリファレンス-sanity-cli)
- [高度な機能](#高度な機能)
  - [IDE の管理と安全なアップグレード](#ide-のメンテナンスと安全なアップグレード-gravity-cli)
  - [マルチインスタンスのサポート](#マルチインスタンス-multi-instance)
  - [コンテナスナップショット](#コンテナスナップショット-snapshots)
  - [SSH エージェントプロキシ](#ssh-エージェントプロキシ-agent-proxy)
  - [ランタイム設定同期 (Runtime Config Sync)](#ランタイム設定同期-runtime-config-sync)
- [バリアント (Variants)](#バリアント-variants)
- [SSH アクセス (SSH Access)](#ssh-アクセス-ssh-access)
- [プロジェクト構造 (Project Structure)](#プロジェクト構造-project-structure)
- [名前の由来 (What's in a Name?)](#名前の由来-whats-in-a-name)

---

## なぜ Sanity-Gravity なのか？

| 機能 (Feature)                   | 説明 (Description)                                                                                                                |
| :------------------------------- | :-------------------------------------------------------------------------------------------------------------------------------- |
| **🛡️ 絶対的な安全性**             | ホストを完全に保護。AI エージェントが `rm -rf /` を実行したりマルウェアをダウンロードしても、サンドボックスが破壊されるだけです。 |
| **🖥️ 完全な GUI デスクトップ**    | **Ubuntu 24.04 + XFCE4** と **KasmVNC** を内蔵。AI は人間と同じようにブラウザや GUI を操作できます。                              |
| **🚀 すぐに使える**               | **Antigravity IDE**、Google Chrome、Git などの中核パッケージが事前インストール済み。準備時間はゼロ。                              |
| **🔌 シームレスなディスク I/O**   | 現在のホスト UID/GID にスマートに対応。ボリュームマウント後にファイルが root 所有になる悲劇を防ぎます。                           |
| **🧩 マルチインスタンス**         | 隔離された環境でタスクを並行処理。システムは競合を避けてクリーンなポートを自動で割り当てます。                                    |
| **📸 凍結スナップショット**       | 現在の環境状態（インストール済みソフトウェア、ログイン情報）を新しいイメージブランチとして瞬時に凍結します。                      |
| **🔄 IDE の安全なアップグレード** | 組み込みのスクリプトで IDE を安全に管理。破壊的な `apt upgrade` の挙動を確実に回避します。                                        |
| **🔑 SSH エージェントプロキシ**   | プライベートキーをコピーすることなく、コンテナ内で安全にホストの認証情報を使って Git 操作を自由に行なえます。                     |

## クイックスタート

### システム要件
* Docker & Docker Compose (v2.0+)
* Python 3.7+ (`sanity-cli` 用)
* *(オプション)* **NVIDIA Container Toolkit** (GPU サポート用)

### インストール手順

1. このリポジトリの複製:
   ```bash
   git clone https://github.com/shiritai/sanity-gravity.git
   cd sanity-gravity
   ```

2. サンドボックスのベースイメージの構築:
   ```bash
   ./sanity-cli build
   ```

3. KasmVNC バリアントの起動 (スムーズなウェブ体験のために推奨):
   ```bash
   ./sanity-cli up -v kasm --password mysecret
   ```

4. **デスクトップへのアクセス**:
   ブラウザを開き、以下にアクセスします: **[https://localhost:8444](https://localhost:8444)**
   * **ユーザー名**: `(ホストのユーザー名)`
   * **パスワード**: `mysecret` (デフォルトは `antigravity`)

> **注意**: localhost での "自己署名証明書" の警告は完全に正常です。"詳細設定" をクリックして進んでください。

## コマンドリファレンス (`sanity-cli`)

`sanity-cli` は、中央のオーケストレーターとして以下のコマンドを提供します。

```bash
# ライフサイクル管理
./sanity-cli up -v [name]   # コンテナの起動 (以下のオプションを付加可能)
  --password [pwd]          # カスタム SSH/VNC パスワード (デフォルト: antigravity)
  --workspace [path]        # ワークスペースディレクトリの割り当て (デフォルト: ./workspace)
  --name [name]             # プロジェクト名によるインスタンスの分離 (デフォルト: sanity-gravity)
  --cpus [limit]            # CPU クォータ (例: 1.5)
  --memory [limit]          # メモリ クォータ (例: 4G)
  --gpu                     # NVIDIA GPU サポートを有効化
./sanity-cli down           # コンテナとネットワークの完全な停止と削除
./sanity-cli stop           # コンテナの一時停止 (データは保持)
./sanity-cli start          # 一時停止したコンテナの開始
./sanity-cli restart        # 実行中のコンテナの強制再起動

# 環境の監視
./sanity-cli status         # すべての実行中のインスタンスの確認
./sanity-cli shell          # コンテナシェル (zsh) へ即座にアクセス
./sanity-cli open           # デフォルトブラウザで Web VNC デスクトップを起動

# メンテナンスと同期
./sanity-cli ide <action>   # コンテナへの IDE メンテナンスのリモートデプロイ
./sanity-cli proxy <action> # SSH Proxy Daemon サービスの管理
./sanity-cli sync_config    # ホスト側設定ファイルを実行中のコンテナにプッシュ
./sanity-cli snapshot       # コンテナ状態を新しいローカライズイメージとして凍結
```

---

## 高度な機能

### 🛠️ IDE のメンテナンスと安全なアップグレード (Gravity-CLI)

Sanity-Gravity には、OS レベルの `apt upgrade` による IDE や Google Chrome ブラウザの意図しないアンインストール、権限喪失やクラッシュを防ぐ防衛メカニズムが組み込まれています。

ホスト側の管理システムとコンテナ内部のソフトウェア管理を厳密に分離しています：
- **Host (ホスト側)**：`sanity-cli` がコンテナのライフサイクルを管理します。メンテナンスコマンドを実行する際、最新の保護スクリプトを対象のコンテナに**自動的にホットインジェクト (hot-inject)** し、過去のすべてのレガシーイメージとの後方互換性を確保して修正プログラムを展開します。
- **Inside (コンテナ内部)**：`gravity-cli` (コンテナ内蔵保護スクリプト) が、OS レベルの `dpkg-divert` を介して Antigravity IDE と Google Chrome ブラウザを安全に管理し、以降の APT アップデートによって `--no-sandbox` 権限の保護が決して無効化されないことを保証します。

#### ホストから (Sanity-CLI の使用)
IDE のクラッシュ (Google Gemini の強制更新によるブラウザの I/O エラーなど) が発生した場合、またはベースとなる Antigravity コアを安全に更新したい場合は、ホストからリモートの `ide` コマンドを使用します。
> **注意**: 稼働中のインスタンスの `--name` については `./sanity-cli status` で確認してください。

```bash
# APT を利用し、安全に Antigravity IDE を最新パッケージへと更新する
./sanity-cli ide update --name sanity-gravity

# 強力な修復策：継続的なひどいクラッシュを修正するため、完全に消去してクリーンインストールを行う
./sanity-cli ide reinstall --name sanity-gravity
```
*(これらのコマンドは、対象コンテナ内で root 権限で自動的に `gravity-cli` を呼び出し、ホスト環境をクリーンに保ったまま内部のみでアップグレードを完結させます。)*

#### コンテナ内部で (Gravity-CLI の使用)
すでにコンテナのシェルにいる場合 (`./sanity-cli shell` など)、直接 `gravity-cli` ツールを呼び出せます。この場合、`root` 権限 (`sudo` を使用するなど) が必要です。

```bash
sudo gravity-cli update-ide    # 'ide update' と同等
sudo gravity-cli reinstall-ide # 'ide reinstall' と同等
```

### 🔌 SSH エージェントプロキシ (Agent Proxy)

Sanity-Gravity には、ホストとコンテナ間で SSH エージェントソケットを安全にブリッジするスマートなプロキシマネージャーが含まれています。これにより、コンテナ内部での `git push` や `git pull` の操作で、**プライベートキーをコンテナへコピーすることなく、ホストの認証情報を直接使用できます**。

通常は `./sanity-cli up` によってすべてが自動処理されます。手動による修復を行う場合：
```bash
./sanity-cli proxy status   # デーモンとアクティブな接続の確認
./sanity-cli proxy setup    # プロキシサービスの手動起動 / 修復
./sanity-cli proxy remove   # プロキシサービスの終了
```

### 🧩 マルチインスタンス (Multi-Instance)

**複数のタスクを並行処理する必要がありますか？** `--name` 引数を使用することで、無数の完全に独立したサンドボックスプロジェクトを同時に実行できます。

```bash
# 'dev-02' という名前で 2 番目のインスタンスを起動
./sanity-cli up -v core --name dev-02 --workspace /tmp/dev02
```
**競合ゼロ保証**：カスタム名を使用する場合、`sanity-cli` はホスト上の利用可能なランダムポートを自動的に検出し、割り当てます。操作時はプロジェクト名でインスタンスを指定します (例: `./sanity-cli down --name dev-02`)。

### 📸 コンテナスナップショット (Snapshots)

設定済みの環境状態 (ソフトウェアのインストール、アクティブなログイン情報など) を新しいイメージとして「凍結」し、それをベースにフォーク (分岐) させることができます。

1. **スナップショットの作成 (Freeze)**:
   ```bash
   ./sanity-cli snapshot --name my-base-env --tag my-verified-state:v1
   ```
2. **スナップショットの利用 (Fork)**:
   ```bash
   ./sanity-cli up -v kasm --name new-experiment --image my-verified-state:v1
   ```

### 🔄 ランタイム設定同期 (Runtime Config Sync)
ホストの `host_config.py` 変数を更新し、コンテナをシャットダウンすることなく適用したい場合は、`./sanity-cli sync_config` を実行するだけで稼働中のコンテナに設定が即座に同期されます。

---

## バリアント (Variants)

| バリアント (Variant) | 技術スタック     | 最適な用途                                         | アクセス方法                               |
| :------------------- | :--------------- | :------------------------------------------------- | :----------------------------------------- |
| **`kasm`**           | KasmVNC          | **最高のスムーズさを誇る Web デスクトップ (推奨)** | `https://localhost:8444`                   |
| **`vnc`**            | TigerVNC + noVNC | 従来の VNC クライアントおよび端末の直接接続        | `localhost:5901` / `http://localhost:6901` |
| **`core`**           | SSH のみサポート | ヘッドレス制御 / ターミナルオンリーの開発環境      | `ssh -p <port> developer@localhost`        |

## SSH アクセス (SSH Access)

すべてのバリアント (GUI インターフェイスを搭載したバージョンを含む) は、デフォルトで `Port 2222` を介した SSH 接続が有効になっています。これにより様々な強力な開発環境構築が可能になります。

*   **ヘッドレス制御 (Headless)**: デスクトップを開くことなく、CLI から GUI ツールをバックグラウンドで操作。
*   **ポートフォワーディング (Port Forwarding)**: `-L` を使用し、テスト用の Web アプリやデータベースをホストに向けて容易にトンネリング (例: `ssh -L 3000:localhost:3000 ...`)。
*   **リモート開発 (Remote Development)**: ローカルの VS Code や JetBrains IDE から Remote SSH 拡張機能を使用し、安全かつ最高の快適さを備えた編集体験を得る。

```bash
# 接続の例 (パスワードは設定値 または antigravity)
ssh -p 2222 developer@localhost
```

## プロジェクト構造 (Project Structure)

```text
sanity-gravity/
├── sanity-cli          # 🛠️ メインとなる管理および入力用 CLI (Python)
├── sandbox/            # 📦 Docker 構築コンテキストと設定
│   ├── variants/       #    - 各バリアント用の Dockerfiles (core, kasm, vnc)
│   └── rootfs/         #    - 共有オーバーレイファイル (スクリプトと設定情報)
├── tests/              # 🧪 Pytest 統合テストスイート
├── workspace/          # 📂 永続化された作業領域 (マウント先)
└── .github/            # 🐙 CI/CD ルールと Git バージョンテンプレート
```

## 名前の由来 (What's in a Name?)

> **"Sanity-Gravity"** は、予測不可能な **「反重力 (Antigravity)」** 人工知能エージェントの荒波に対して、確固たる **「重力 (Gravity)」** による制約を提供し、開発者たちの **「正気・理智 (Sanity)」** を守り抜くことを意味しています。

制御不能な AI による実行を使い捨てのサンドボックス空間に監視下に置くことで、`rm -rf /` のような予期せぬ破壊や、パスワード、環境情報の流出・汚染といった取り返しのつかない損害を未然に防ぎます。

## ライセンス (License)
MIT License
