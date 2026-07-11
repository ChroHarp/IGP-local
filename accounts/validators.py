from pathlib import Path
from zipfile import BadZipFile, ZipFile

from django.core.exceptions import ValidationError

MAX_DOCUMENT_SIZE = 15 * 1024 * 1024
MAX_DOCX_UNCOMPRESSED_SIZE = 60 * 1024 * 1024
MAX_DOCX_FILE_COUNT = 5_000


def validate_program_document(uploaded_file):
    if not uploaded_file:
        return

    suffix = Path(uploaded_file.name).suffix.lower()
    if suffix not in {".pdf", ".docx"}:
        raise ValidationError("僅允許上傳 PDF 或 DOCX 檔案。")
    if uploaded_file.size > MAX_DOCUMENT_SIZE:
        raise ValidationError("檔案不得超過 15 MB。")

    uploaded_file.open("rb")
    stream = uploaded_file.file
    original_position = stream.tell()
    try:
        stream.seek(0)
        signature = stream.read(5)
        if suffix == ".pdf":
            if signature != b"%PDF-":
                raise ValidationError("PDF 檔案格式不正確。")
            return

        stream.seek(0)
        with ZipFile(stream) as archive:
            entries = archive.infolist()
            if len(entries) > MAX_DOCX_FILE_COUNT:
                raise ValidationError("DOCX 內含過多檔案。")
            if sum(entry.file_size for entry in entries) > MAX_DOCX_UNCOMPRESSED_SIZE:
                raise ValidationError("DOCX 解壓後內容過大。")
            if "word/document.xml" not in archive.namelist():
                raise ValidationError("DOCX 缺少 Word 文件內容。")
    except BadZipFile as exc:
        raise ValidationError("DOCX 檔案格式不正確。") from exc
    finally:
        stream.seek(original_position)
