# IGP Local

Local-first IGP writing and management system for gifted education classes.

## Development setup

Requires Python 3.13 and [uv](https://docs.astral.sh/uv/).

```powershell
$env:UV_CACHE_DIR = "$PWD\.uv-cache"
uv sync
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py runserver
```

Run checks:

```powershell
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py test
```

## Phase 1 local administration

The built-in Django Admin is the current local management interface:

```powershell
.\.venv\Scripts\python.exe manage.py createsuperuser
```

Then open `http://127.0.0.1:8000/admin/`. The initial superuser is a break-glass account with full data access; keep it offline and use normal, approved staff accounts for daily work.

- 特教組長／主管：可管理全校學生資料。
- 個管教師：只能看到被指派的學生。
- 任課教師與技術系統管理員：預設看不到學生主檔。
- 技術系統管理員可管理帳號，但不因技術角色自動取得學生資料權限。

## Google sign-in preparation

Google sign-in is installed but inactive until the school creates its own OAuth web client. Put `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` in the service environment, set the exact callback URL in Google Cloud, then pre-create and approve each teacher's local account with the same Google email.

The system requests only `profile` and `email`; it does not request Gmail, Drive, or offline access. Unknown, inactive, or unapproved accounts are blocked from automatic signup.

Do not place real student data, OAuth secrets, generated files, logs, or backups in Git.

## Production HTTPS note

Production settings enable HTTPS and HSTS for the configured IGP hostname. Django will warn until the school explicitly decides whether every subdomain is HTTPS-only and eligible for browser preload. Do not enable HSTS subdomain coverage or preload merely to silence that warning.
## 批次匯入與課程文件

特教組長／主管登入 Admin 後，在「學生」列表右上角選擇「匯入基礎資料」。先按「預覽」，確認結果後重新選擇同一個 `.xlsx` 檔並按「確認寫入」。匯入只會建立尚不存在的學生；有學號時以學號辨識，沒有學號時以姓名與出生日期辨識，遇到歧義或 Excel 內重複列會停止寫入。

也可在本機命令列預覽：

```powershell
.\.venv\Scripts\python.exe manage.py import_students "C:\path\students.xlsx"
.\.venv\Scripts\python.exe manage.py import_students "C:\path\students.xlsx" --apply
```

Admin 的「課程文件」可上傳課程計畫或課表。只接受 15 MB 以下的 PDF 或 DOCX；檔案不會公開提供，必須登入並通過角色檢查才可下載。課程、個管與導師可閱讀一般文件；與學生關聯的 IGP 文件只開放特教組長及該生個管教師。上傳、修改與刪除限特教組長／主管。

在「IGP 年度計畫」開啟個別計畫後，可按「產生 IGP DOCX」。系統會先檢查年度目標、學期計畫、學期目標及課程目標；若有缺漏會列出待補欄位。輸出以去識別化的 `114-7AB-IGP` Word 範本為底，保留原始頁面、表格、合併儲存格、註解與字型，填入學生、家庭、評量、年度分析、課程及輔導紀錄；課程頁數會依實際課程增減。產出的 DOCX 仍可由教師在 Word 中直接編修，並保存為該生的私有文件及留下稽核事件。

## 在另一台 Windows 電腦建置

以下步驟適合在校內另一台全新的 Windows 電腦建立**開發／測試環境**。它會使用新的本機 SQLite 資料庫；學生資料、已上傳文件、帳號與既有資料庫不會隨 Git 一起帶過去。

### 1. 安裝必要工具

- 安裝 [Git for Windows](https://git-scm.com/download/win)。
- 安裝 Python **3.13**（安裝時勾選「Add Python to PATH」）。
- 在 PowerShell 安裝 uv：

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

關閉並重新開啟 PowerShell 後，確認：

```powershell
git --version
python --version
uv --version
```

### 2. 下載專案與安裝套件

```powershell
git clone https://github.com/ChroHarp/IGP-local.git
cd IGP-local
$env:UV_CACHE_DIR = "$PWD\.uv-cache"
uv sync
```

### 3. 建立本機資料庫與管理帳號

```powershell
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py createsuperuser
```

輸入管理員帳號、Email 與密碼後，啟動網站：

```powershell
.\.venv\Scripts\python.exe manage.py runserver
```

在同一台電腦開啟 <http://127.0.0.1:8000/admin/>，以剛建立的管理員登入。

### 4. 每次更新程式

先停止伺服器（在 PowerShell 按 `Ctrl+C`），再執行：

```powershell
git pull
$env:UV_CACHE_DIR = "$PWD\.uv-cache"
uv sync
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py check
```

接著重新執行 `runserver`。只要更新包含 migration，就一定要執行 `migrate`。

### 資料庫 migration 與交接

Migration 是資料庫結構與資料轉換的正式紀錄，會隨程式碼一起版本控制；Django 會在資料庫的 `django_migrations` 表記錄已套用項目，因此同一個轉換不會重複執行。

接手既有資料庫或拉取新版本後，依序執行：

```powershell
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py showmigrations accounts
```

執行資料 migration 前，先私下備份 `db.sqlite3`，但不得提交備份檔至 Git。以 2026-07 的課程範本調整為例，`0016_course_plan_templates` 與 `0017_populate_course_plan_templates` 會將既有課程轉成「課程範本＋學生個別版本」；升級後應確認 `showmigrations` 顯示兩者均為 `[X]`。

### 5. 帶入既有校務資料（重要）

若這台電腦要接手既有系統，不能只複製程式碼。請在原電腦停止服務後，由資訊人員安全複製下列資料，且不要提交到 Git：

- `db.sqlite3`：所有系統資料與帳號。
- `media\`：已上傳的課程文件。
- 生產環境的 `DJANGO_SECRET_KEY`、Google OAuth 設定與其他服務環境變數。

複製前先備份；複製完成後，在新電腦執行 `migrate` 與 `check`，再啟動服務。若只是測試，不要使用真實學生資料。

### 校內正式運作

`runserver` 只適合測試。校內正式使用時，請依學校資訊安全規範由資訊人員配置固定或保留 IP、HTTPS、備份、Windows 開機後自動啟動與校外 VPN 存取；不要直接將 Django 開發伺服器公開到網際網路。
