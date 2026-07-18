# Phase 4：匯入完善與文件輸出總結

> 最後更新：2026-07-18。本文件記錄 Phase 4 的資料欄位、Admin 流程、DOCX 範本與版面驗證結果。

## 目的

Phase 4 將校方既有的學生資料匯入與 IGP 文件輸出流程落地。系統保存結構化資料，以可編輯 Word 範本輸出固定欄位與不同筆數的表格；校方仍可直接在 Word 調整字型、欄寬、頁首頁尾及其他版面。

## 已完成內容

### Excel 匯入

- Admin 匯入流程保留「預覽」與「確認寫入」兩步，格式錯誤、歧義與 Excel 內重複列會逐列彙整，整批資料不會部分寫入。
- 有學號時以學號辨識；沒有學號時以姓名與出生日期辨識。
- `manage.py import_students` 保留預覽與 `--apply` 寫入模式；測試與範例資料均為合成／去識別化資料。
### 系統欄位與 Admin

- 學生基本資料新增可複選「資優類別」：一般智能、創造能力、數理、英語、自然。
- 每份學期計畫新增就讀學校、年級及班級；學校預設「平興國中」，但可依轉學生資料修改。輸出班別由年級及班級組成，例如 8 年級、2 班輸出 `802`。
- 新增非必填教育轉銜紀錄；階段為 3–4 年級、5–6 年級、國中，並支援多選特殊教育服務類型。
- 評量紀錄新增可變筆數分量表與分量成績。
- IGP 年度計畫新增數理優勢、語文優勢、劣勢及情意方面四段綜合評析。
- 重新安置紀錄建立對應欄位，model 驗證與 Admin inline 均限制每位學生最多 2 筆。
- 新增 IGP 期初／期末會議紀錄，包含學年度、學期、會議類型、日期、時間、地點、記錄者、與會人員及會議紀錄；可由 Admin 產生私有 DOCX 並建立稽核事件。
- 上述模型變更由 migration `0021_igpplan_affective_analysis_igpplan_strength_language_and_more` 建立，未修改既有已套用 migration。

### IGP DOCX 輸出

- 主範本為 `accounts/docx_templates/igp-template.docx`；固定欄位由 `docx-mailmerge2` 填入，動態表格與區段由 `python-docx` 處理。
- P1 資優類別只顯示系統選取結果；學習階段表依每份學期計畫顯示學年度、學期、學校及組合後班別。
- P2 家庭狀況及 P5 興趣分析只顯示結果，不再重複固定選項。
- P3 教育轉銜、P4 評量與巢狀分量表、P5 多筆得獎、P7 四段綜合評析均由對應系統資料產生。
- 每門課保留兩個表格：課程表頭／教育需求與學習表現／評量表；課程數與學習表現筆數均可動態增減。
- 主 IGP 可帶入最近一筆 IGP 會議、最多兩筆重新安置紀錄，以及同學年度所有晤談／輔導摘要。
- 評量、得獎與輔導表依實際筆數增減列；跨頁會重複表頭並避免拆開單筆資料列。
- 日期欄採民國短日期並設定不換行，降低窄欄錯位。

### 獨立會議範本與對照輸出

- 可自行調整的 A4 會議範本：`accounts/docx_templates/igp-meeting-template.docx`。
- 完整 IGP 合成資料對照檔：`output/doc/IGP-template-sample.docx`。
- 獨立會議合成資料對照檔：`output/doc/IGP-meeting-sample.docx`。
- 對照檔只含合成資料，沒有真實學生資料。

### LibreOffice Windows Path 修正

- 已新增 `scripts/convert_docx_to_pdf.ps1`。腳本優先使用 `C:\Program Files\LibreOffice\program\soffice.com`，也可用 `-LibreOfficePath` 指定其他安裝位置。
- 問題原因不是 `bootstrap.ini` 實際損壞，而是 `UserInstallation` 曾收到 `file://C:\...` 這種無效值。腳本使用 .NET `System.Uri` 產生正確的 `file:///C:/...` URI，並為每次轉檔建立及清除獨立暫存 profile。
- 使用方式：

```powershell
.\scripts\convert_docx_to_pdf.ps1 `
  -InputPath .\output\doc\IGP-template-sample.docx `
  -OutputDirectory .\output
```

## 範本維護原則

- 可直接調整範本的字型、字級、欄寬、列高、框線、底色、段落間距、紙張與頁首頁尾。
- 固定 `MERGEFIELD` 欄位可移動但不可任意改名；新增欄位仍須同步修改系統資料與 `accounts/documents.py`。
- 動態表格需保留表頭與至少一列樣板列，不必預先建立大量空白列。
- 目前課程區仍依「學習領域」、「項次」及「（二）課表」標記辨識；不要刪除或任意改名。
- 大幅重排主要表格前，應先以兩份合成對照檔回歸測試。

## 權限與資料影響

- 沿用 Phase 3 學生可見範圍；沒有放寬輔導紀錄的閱讀、作者修改、送審或審核權限。
- IGP 與會議輸出都保存為私有 `ProgramDocument`，並建立文件上傳稽核事件。
- 不可提交真實學生資料、SQLite 資料庫、`media/`、備份、日誌或 `.env`。

## 驗證

- `manage.py check` 通過。
- `manage.py makemigrations --check --dry-run` 顯示無變更。
- 完整 `manage.py test` 共 68 項通過。
- 已以 LibreOffice 26.2.4.2 將合成完整 IGP 與獨立會議 DOCX 轉成 PDF；主文件為 11 頁 A4，會議文件為 1 頁 A4。
- 已逐頁檢查 12 頁渲染結果，PDF 文字抽取沒有 Unicode replacement character；資優類別、學期學校班別、轉銜、分量表、多筆得獎、四段評析、課程、會議、重新安置及輔導摘要均可辨識。

## 目前限制與後續建議

- 已上傳的課表與課程計畫可安全保存、下載；目前尚未將任意 PDF／DOCX 課表自動嵌入主 IGP 的課表頁，仍保留範本中的課表位置供人工貼入。若要自動組裝，建議下一步先限定附件格式為圖片或 PDF，再建立明確的插入規則。
- 主 IGP 沿用校方原始範本，因此仍有刻意保留的空白簽名區、課表頁與大尺寸表格；這些可由校方在範本中直接調整。

## 維護程序

1. 調整範本前保留備份，並用合成對照資料產出新檔。
2. 修改欄位名稱、主表格順序或新增附件組裝前，同步調整 `accounts/documents.py` 與回歸測試。
3. 執行 `manage.py check`、`manage.py makemigrations --check --dry-run` 與 `manage.py test`。
4. 使用 `scripts/convert_docx_to_pdf.ps1` 轉 PDF，逐頁檢查版面與亂碼。
5. 檢查 diff，只提交本次範圍後推送 GitHub。
