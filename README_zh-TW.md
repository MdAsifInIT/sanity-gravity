# Sanity-Gravity: The Antigravity Sandbox

<p align="center">
  <img src="assets/logo.jpg" alt="Sanity-Gravity Logo" width="300">
</p>

<p align="center">
  <em>專為 Agentic AI IDEs 打造的現代化安全容器沙箱環境</em>
</p>

<p align="center">
  <a href="README.md">English</a> | <a href="README_zh-TW.md">繁體中文</a> | <a href="README_ja.md">日本語</a>
</p>

---

## TL;DR

**Sanity-Gravity** 是一個專為 Agentic AI 工作流程量身打造的現代化「零設定」GUI 沙箱。它能將所有潛在的高風險動作徹底限制在用完即棄的 Docker 容器中，並同時順暢地將完整的 XFCE4 桌面體驗串流至您的瀏覽器。

**在數秒內啟動安全的 AI 實驗場地：**

```bash
# 1. 建置基底映像檔
./sanity-cli build

# 2. 啟動沙箱並無縫掛載持久化工作目錄
./sanity-cli up -v kasm --name my-agent-task --workspace ./ai-workspace
```

您的安全桌面已就緒，請前往 **https://localhost:8444**！
- **登入帳號**: `(您主機上的實際 User 名稱)`
- **登入密碼**: `antigravity` (或是您透過 `--password` 所設定的密碼)

📺 **[進入觀看實際展示 (YouTube Demo)](https://youtu.be/x0DGKuHyx2A)**

## 目錄 (Table of Contents)

- [Sanity-Gravity: The Antigravity Sandbox](#sanity-gravity-the-antigravity-sandbox)
  - [TL;DR](#tldr)
  - [目錄 (Table of Contents)](#目錄-table-of-contents)
  - [為什麼選擇 Sanity-Gravity？](#為什麼選擇-sanity-gravity)
  - [快速開始](#快速開始)
    - [系統需求](#系統需求)
    - [安裝步驟](#安裝步驟)
  - [指令參考 (`sanity-cli`)](#指令參考-sanity-cli)
  - [進階功能](#進階功能)
    - [🛠️ IDE 維護與安全升級 (Gravity-CLI)](#️-ide-維護與安全升級-gravity-cli)
      - [從宿主機 (使用 Sanity-CLI)](#從宿主機-使用-sanity-cli)
      - [在容器內 (使用 Gravity-CLI)](#在容器內-使用-gravity-cli)
    - [🔌 SSH 代理穿透 (Agent Proxy)](#-ssh-代理穿透-agent-proxy)
    - [🧩 多重實例 (Multi-Instance)](#-多重實例-multi-instance)
    - [📸 容器快照 (Snapshots)](#-容器快照-snapshots)
    - [🔄 動態設定同步 (Runtime Config Sync)](#-動態設定同步-runtime-config-sync)
  - [版本選擇 (Variants)](#版本選擇-variants)
  - [SSH 存取 (SSH Access)](#ssh-存取-ssh-access)
  - [專案結構 (Project Structure)](#專案結構-project-structure)
  - [名稱的意義 (What's in a Name?)](#名稱的意義-whats-in-a-name)
  - [Licence](#licence)

---

## 為什麼選擇 Sanity-Gravity？

| 核心特色 (Feature) | 設計對應的好處 (Description)                                                                     |
| :----------------- | :----------------------------------------------------------------------------------------------- |
| **🛡️ 絕對安全隔離** | 徹底保護主機本身。即使 AI 代理執行 `rm -rf /` 下載了危險程式碼，只有沙箱會被破壞，主機百毒不侵。 |
| **🖥️ 完整圖形桌面** | 內置 **Ubuntu 24.04 + XFCE4** 與高效 **KasmVNC**。AI 代理能如同人類一樣操作瀏覽器及 GUI 介面。   |
| **🚀 開箱即用基底** | 預裝 **Antigravity IDE**、Google Chrome、Git 等關鍵核心套件，零準備時間。                        |
| **🔌 無縫磁碟 I/O** | 智慧對應主機目前的 UID/GID，不再有 Volume 掛載後檔案變為 root 擁有權的災難發生。                 |
| **🧩 多開獨立實例** | 可平行建立各種任務環境，支援隔離多專案且系統自動分配乾淨 Port，永不衝突。                        |
| **📸 凍結還原快照** | 將目前環境狀態（如已安裝軟體、登入狀態）瞬間凍結為新映像檔分叉。                                 |
| **🔄 IDE 安全升級** | 透過 `sanity-cli ide` 進行遠端安全升級與修復，內建防護層能確保更新不崩潰。                       |
| **🔑 SSH 代理穿透** | 不需複製任何私鑰，就能在沙箱內安全地使用主機憑證自由執行 Git 操作。                              |

## 快速開始

### 系統需求
* Docker & Docker Compose (v2.0+)
* Python 3.7+ (用於驅動 `sanity-cli`)
* *(選用)* **NVIDIA Container Toolkit** (以支援 GPU 加速)

### 安裝步驟

1. 複製本專案庫:
   ```bash
   git clone https://github.com/shiritai/sanity-gravity.git
   cd sanity-gravity
   ```

2. 建置您專屬的沙箱基底映像檔:
   ```bash
   ./sanity-cli build
   ```

3. 啟動 KasmVNC 變體版本 (推薦使用該版本以獲得網頁流暢體驗):
   ```bash
   ./sanity-cli up -v kasm --password mysecret
   ```

4. **存取您的桌面**:
   打開瀏覽器並前往: **[https://localhost:8444](https://localhost:8444)**
   * **使用者名稱**: `(您主機上的實際 User 名稱)`
   * **密碼**: `mysecret` (預設為 `antigravity`)

> **注意**: 如果遇到「自簽署憑證」警告，這在本地端為正常現象，請點選「進階」並繼續前往。

## 指令參考 (`sanity-cli`)

`sanity-cli` 作為管理沙箱群生命週期的中央調度器，提供下列操作：

```bash
# 生命周期管理
./sanity-cli up -v [name]   # 建立並啟動容器 (附帶以下選用引數)
  --password [pwd]          # 自訂 SSH/VNC 密碼 (預設: antigravity)
  --workspace [path]        # 指派專案的工作區 (預設: ./workspace)
  --name [name]             # 指定全域辨識的專案名稱 (預設: sanity-gravity)
  --cpus [limit]            # 啟用 CPU 配額 (例: 1.5)
  --memory [limit]          # 限制記憶體用量 (例: 4G)
  --gpu                     # 啟用 NVIDIA GPU 支援
./sanity-cli down           # 停止並完全刪除容器與網路
./sanity-cli stop           # 僅暫停容器 (保留運行資料)
./sanity-cli start          # 將已暫停的容器重新喚醒
./sanity-cli restart        # 強制重啟運行中的容器

# 狀態與環境監控
./sanity-cli status         # 查看所有線上實例與 Health 狀態
./sanity-cli shell          # 一鍵進入容器內部的 Shell (zsh)
./sanity-cli open           # 以預設瀏覽器打開桌面 VNC 介面

# 維護與網路同步
./sanity-cli ide <action>   # 自動派送容器內部 IDE 的系統更新與維修
./sanity-cli proxy <action> # 管理核心 SSH Proxy Daemon 狀態
./sanity-cli sync_config    # 將主機最新設定推送至正在運行的容器中
./sanity-cli snapshot       # 將當前狀態凍結為新映像檔
```

---

## 進階功能

### 🛠️ IDE 維護與安全升級 (Gravity-CLI)

Sanity-Gravity 內建了針對 OS 等級 `apt upgrade` 導致 IDE 或 Google Chrome 瀏覽器解除安裝、喪失特權，進而引發崩潰的嚴密防護機制。

我們將宿主機管理與容器內部軟體管理進行了嚴格的切割：
- **Host (宿主機)**：`sanity-cli` 負責管理所有容器的生命週期。當執行維護指令時，它會 **自動將最新版的防護腳本熱注入 (hot-inject)** 到目標容器中，確保向後相容過往所有的舊版容器映像檔，並自動佈署修補措施。
- **Inside (容器內)**：`gravity-cli` (容器內建守護腳本) 負責安全地管理 Antigravity IDE 以及 Google Chrome 瀏覽器，透過底層封裝 (`dpkg-divert`) 確保它們的 `--no-sandbox` 啟動特權與捷徑不會被任何後續的 APT 更新給洗清或破壞。

#### 從宿主機 (使用 Sanity-CLI)
如果您遇到 IDE 崩潰 (例如 Google Gemini 強制更新以及其引發的瀏覽器 I/O Error) 或者只是想安全地將 IDE 更新到最新版，請在宿主機使用對接的 `ide` 指令。
> **注意**: `--name` 參數用於指定目標實例 (預設為 `sanity-gravity`)。若您同時運行多套隔離環境，請透過 `./sanity-cli status` 確認名稱。

```bash
# 安全地透過 apt 將 Antigravity IDE 更新至最新版
./sanity-cli ide update --name sanity-gravity

# 核彈級修復：徹底清除並重新乾淨安裝 IDE 以解決持續性的極端崩潰問題
./sanity-cli ide reinstall --name sanity-gravity
```
*(這些指令會自動在目標容器內部以 root 身分呼叫 `gravity-cli` 腳本，所有的防護升級都在容器內完美收束，保持您的宿主基底環境乾淨無染。)*

#### 在容器內 (使用 Gravity-CLI)
如果您已經身處容器的 shell 中 (例如透過 `./sanity-cli shell`)，您可以直接無縫呼叫 `gravity-cli` 工具。請注意，您必須以 `root` 身分 (例如加掛 `sudo`) 來執行這些指令。

```bash
sudo gravity-cli update-ide    # 等同於 'sanity-cli ide update'
sudo gravity-cli reinstall-ide # 等同於 'sanity-cli ide reinstall'
```

### 🔌 SSH 代理穿透 (Agent Proxy)

Sanity-Gravity 包含了一個智慧型的 Proxy 管理器，用於在主機與容器之間建立安全橋接的 SSH Agent Socket。這允許容器內部的 `git push` 或 `git pull` 操作，能夠**直接使用您主機上的憑證與私鑰，而不需要複製任何私鑰進容器**。

一般而言，`./sanity-cli up` 會妥善為您包辦一切。如遇異常需要手動重啟：
```bash
./sanity-cli proxy status   # 檢查連線以及守護行程 (Daemon) 狀態
./sanity-cli proxy setup    # 手動啟動/修復 Proxy 服務
./sanity-cli proxy remove   # 終止 Proxy 服務
```

### 🧩 多重實例 (Multi-Instance)

**需要並行處理多個任務？** Sanity-Gravity 支援透過 `--name` 參數同時運行無數個完全物理隔離的沙箱專案。

```bash
# 啟動名為 'dev-02' 的第二個實例
./sanity-cli up -v core --name dev-02 --workspace /tmp/dev02
```
**零衝突保證**：當使用自訂名稱時，`sanity-cli` 會自動偵測並為您分配主機端可用的隨機連線埠。後續操作時只需加上對應名稱標籤 (例: `./sanity-cli down --name dev-02`)。

### 📸 容器快照 (Snapshots)

您可以將當前環境（例如精心調整安裝完的背景環境、已經登入認證過的服務）凍結起來建立一個**快照映像檔**，並以此作為分支創建新的隔離區。

1. **建立快照 (Freeze)**:
   ```bash
   ./sanity-cli snapshot --name my-base-env --tag my-verified-state:v1
   ```
2. **基於快照建立新區塊 (Fork)**:
   ```bash
   ./sanity-cli up -v kasm --name my-new-project --image my-verified-state:v1
   ```

### 🔄 動態設定同步 (Runtime Config Sync)
若是您變更了 `host_config.py` 但不想停機，只需要執行 `./sanity-cli sync_config` 即可熱更新這些變數進正在運轉的容器。

---

## 版本選擇 (Variants)

| 版本 (Variant) | 技術堆疊         | 最佳用途                                 | 存取方式                                   |
| :------------- | :--------------- | :--------------------------------------- | :----------------------------------------- |
| **`kasm`**     | KasmVNC          | **順暢度最高之 Web 網頁桌面 (推薦使用)** | `https://localhost:8444`                   |
| **`vnc`**      | TigerVNC + noVNC | 傳統舊版 VNC 方案及終端軟體直接連線      | `localhost:5901` / `http://localhost:6901` |
| **`core`**     | 僅支援 SSH       | 背景調度 / 純終端機開發情境              | `ssh -p <port> developer@localhost`        |

## SSH 存取 (SSH Access)

所有的變體 (Variants)，**包含所有具備 GUI 的映像版本**，預設將會對外開放 `Port 2222` 作為 SSH 訪問用途。為這套環境解除了各種進階開發框架的封印：

*   **無頭控制 (Headless)**：結合 CLI 於背景操作 GUI 工具而不開啟桌面介面。
*   **本機穿隧 (Port Forwarding)**：透過 `-L` 輕易透傳測試用的 Web Apps 與 Database (例: `ssh -L 3000:localhost:3000 ...`)。
*   **異地開發 (Remote Development)**：使用本地端的 VS Code 或 JetBrains IDE 掛上 Remote SSH 套件，獲得全地球最舒適安全的本地編輯體驗。

```bash
# 連線範例 (密碼採用設定密碼或 antigravity)
ssh -p 2222 developer@localhost
```

## 專案結構 (Project Structure)

```text
sanity-gravity/
├── sanity-cli          # 🛠️ Main CLI 管理中樞入口
├── sandbox/            # 📦 Docker 建置環境檔
│   ├── variants/       #    - 變體描述與專用 Dockerfiles (core, kasm, vnc)
│   └── rootfs/         #    - 共用系統重疊覆寫區塊 (所有安全腳本及環境變數)
├── tests/              # 🧪 專案的全面 Pytest 整合測試套件
├── workspace/          # 📂 預設綁定的持久化工作熱區
└── .github/            # 🐙 CI/CD 與原始碼管理工具
```

## 名稱的意義 (What's in a Name?)

> **"Sanity-Gravity"** 象徵著：在這個充滿失控與危險的 **「反重力 (Antigravity)」** 人工智慧代理時代，替予您最大的引力約束 **「重力 (Gravity)」** 與保全開發人員心理底線的 **「理智 (Sanity)」**。

將所有狂野、未經檢驗的 AI 測試拘禁於可拋式 Sandbox 中，徹底拔除意外的 `rm -rf /` 及憑證劫持等不可逆傷害。

## Licence
MIT License
