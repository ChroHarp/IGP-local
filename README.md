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

Admin 的「課程文件」可上傳課程計畫或課表。只接受 15 MB 以下的 PDF 或 DOCX；檔案不會公開提供，必須登入並通過角色檢查才可下載。課程、個管與導師可閱讀；上傳、修改與刪除限特教組長／主管。
