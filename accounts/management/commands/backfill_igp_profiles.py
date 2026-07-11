from django.core.management.base import BaseCommand
from django.db import transaction

from accounts.importers import populate_imported_details
from accounts.models import InitialIGPProfile


class Command(BaseCommand):
    help = "將初始 IGP 概況的原始回覆回填為可編輯欄位、家庭成員與得獎紀錄。"

    def add_arguments(self, parser):
        parser.add_argument("--overwrite", action="store_true", help="覆寫已有的概況欄位。")

    def handle(self, *args, **options):
        profiles = InitialIGPProfile.objects.exclude(raw_response={}).select_related("student")
        with transaction.atomic():
            for profile in profiles:
                populate_imported_details(profile.student, profile.raw_response, overwrite=options["overwrite"])
        self.stdout.write(self.style.SUCCESS(f"已回填 {profiles.count()} 位學生的 IGP 資料。"))
