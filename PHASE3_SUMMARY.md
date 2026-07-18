# Phase 3：輔導紀錄與稽核總結

> 最後更新：2026-07-18。所有後續實作開始前都必須先閱讀本文件與 `AGENTS.md`；完成後須更新本文件、驗證、提交並推送。

## 目的

Phase 3 建立校內可追蹤的輔導紀錄流程，而非單純的 CRUD。重點是以學生關係控制可見範圍、限制作者修改權、由特教組長進行審核，並保存高價值的稽核事件。

## 已完成內容

### 資料、狀態與稽核

- `CounselingRecord` 已建立，欄位包含學生、學年度、日期、參與人員、事件、內容概要敘述、處遇方式、記錄人員、審核意見與時間戳記。
- 狀態流程為 `draft → submitted → returned → reviewed → locked`。作者只能修改自己的草稿或退回紀錄。
- 審核意見僅特教組長／superuser 可填，且為非必填。
- `AuditEvent` 記錄建立、送審、退回、審核與鎖定；稽核頁唯讀，且不複製完整敏感內文。
- migration 為 `0018_phase3_counseling_audit` 與 `0019_counseling_record_fields`。不可修改已套用 migration；後續資料模型調整必須新增 migration。

### 權限與多重身分

- 特教組長／superuser：可查看全部紀錄、建立紀錄及審核。
- 個管教師：可查看個案學生的全部紀錄；也可為任課學生新增紀錄，但對非個案學生只會看到自己撰寫的紀錄。
- 班級導師：可查看班級學生的全部紀錄、為班級學生新增紀錄；只能修改自己撰寫的草稿或退回紀錄。
- 任課教師：可為授課學生新增紀錄，且只可查看及修改自己撰寫的紀錄。
- 判斷以實際有效的學生教師指派與授課關係為準，不可只依 `User.role`；這是多重身分帳號的必要規則。

### Admin 導覽與欄位

輔導紀錄採三層導覽：

1. 根頁先列出目前使用者可見或可新增的學生。
2. 點選學生後，列出該生可見紀錄的摘要表；欄位為日期、參與人員、事件、內容概要敘述、處遇方式、記錄人員。
3. 點選日期或事件後，進入單筆詳細頁。

學生頁保留送審、退回、審核、鎖定 actions；新增連結會預選該學生。

目前表單規格：

- 參與人員核取：本人、家長、原班導師、個管老師、資優任課；另有獨立「其他參與人員」文字欄。
- 處遇方式核取：轉介二級、協同導師、定期晤談、持續觀察；另有獨立「其他處遇方式」文字欄。
- 既有的舊文字資料保留，並在表單中呈現於對應的「其他」文字欄。

### 相關改善

- 2026-07-18 Phase 4 新增資優類別、學期學校／年級／班級、教育轉銜、評量分量表、四段綜合評析、IGP 會議與最多兩筆重新安置紀錄，migration 為 `0021_igpplan_affective_analysis_igpplan_strength_language_and_more`。
- 主 IGP 可帶入會議、重新安置與同學年度輔導摘要；新增獨立 A4 會議 DOCX 範本與私有文件匯出。Phase 3 的學生可見範圍、輔導紀錄狀態、作者修改與主管審核規則均未變更。
- Windows LibreOffice 渲染改由 `scripts/convert_docx_to_pdf.ps1` 產生標準 `file:///C:/...` profile URI，避免錯誤顯示 `bootstrap.ini` 損壞。
- IGP DOCX assessment, award, and counseling tables now expand to the actual record count, repeat header rows across pages, and keep individual data rows together. This does not affect Phase 3 permissions, counseling states, or migrations.
- 學生教師指派頁在重複指派現任個管時，會在儲存前顯示「學生已是某教師的個案」，而非觸發資料庫 `IntegrityError`。
- 課程計畫的可見學生範圍採個案學生與授課學生聯集；授課可見不等於可修改非個案學生的資料。
- `seed_demo_data` 已包含各狀態的合成輔導紀錄與稽核事件，僅可用於測試。

## 驗證基準

- 最近完整驗證：2026-07-18 已通過 `manage.py check`、`manage.py makemigrations --check --dry-run` 與 68 項 `manage.py test`；另以 LibreOffice 逐頁檢查 11 頁完整 IGP 與 1 頁會議紀錄。
- 每次變更權限、Admin 路由、表單或資料模型時，都要補足 `accounts/tests.py` 的回歸測試。
- 權限測試至少覆蓋：列表、單一學生頁、詳細頁、直接 URL、建立、修改、送審與審核。

## 目前不納入的範圍

- 輔導附件、公開學生／家長入口、REST API、即時通知與 DOCX 完整報表。
- SQLite 不是跨電腦共享的正式資料庫；Git 只同步程式、migration 與合成測試資料。真實學生資料、SQLite 資料庫、media、備份與 `.env` 不可提交。

## 後續工作程序

1. 開始前閱讀本文件與 `AGENTS.md`，確認是否影響 Phase 3 權限、狀態或 migration。
2. 以集中 policy、model constraint 與 Admin queryset 實作權限，不要只靠前端隱藏按鈕。
3. 完成後更新本文件，記錄功能、權限／migration 影響與驗證結果。
4. 執行 `manage.py check`、`manage.py test`；模型變更另執行 `makemigrations --check --dry-run`。
5. 檢查 diff，僅提交本次範圍，然後推送 GitHub。
