from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from accounts.importers import import_basic_students


class Command(BaseCommand):
    help = "預覽或匯入學生基礎資料 Excel。預設只預覽，不寫入資料庫。"

    def add_arguments(self, parser):
        parser.add_argument("file", type=Path)
        parser.add_argument("--apply", action="store_true", help="確認無誤後才寫入資料庫。")

    def handle(self, *args, **options):
        source = options["file"]
        if source.suffix.lower() != ".xlsx" or not source.is_file():
            raise CommandError("請提供存在的 .xlsx 檔案。")
        with source.open("rb") as workbook_file:
            result = import_basic_students(workbook_file, apply=options["apply"])
        for error in result.errors:
            self.stderr.write(error)
        self.stdout.write(
            f"資料列：{result.row_count}；新增：{result.create_count}；"
            f"略過既有資料：{result.skip_count}；錯誤：{result.error_count}。"
        )
        if result.errors:
            raise CommandError("匯入未執行；請先修正上述錯誤。")
        if not options["apply"]:
            self.stdout.write(self.style.WARNING("這是預覽；加上 --apply 才會寫入資料庫。"))
        elif result.create_count:
            self.stdout.write(self.style.SUCCESS("匯入完成。"))
