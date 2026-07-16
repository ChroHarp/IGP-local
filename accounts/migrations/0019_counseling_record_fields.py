# Generated manually to preserve existing counseling record data.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0018_phase3_counseling_audit"),
    ]

    operations = [
        migrations.RenameField(
            model_name="counselingrecord",
            old_name="subject",
            new_name="event",
        ),
        migrations.RenameField(
            model_name="counselingrecord",
            old_name="content",
            new_name="summary",
        ),
        migrations.AlterField(
            model_name="counselingrecord",
            name="event",
            field=models.CharField(max_length=150, verbose_name="事件"),
        ),
        migrations.AlterField(
            model_name="counselingrecord",
            name="summary",
            field=models.TextField(verbose_name="內容概要敘述"),
        ),
        migrations.AddField(
            model_name="counselingrecord",
            name="participants",
            field=models.TextField(blank=True, verbose_name="參與人員"),
        ),
        migrations.AddField(
            model_name="counselingrecord",
            name="intervention",
            field=models.TextField(blank=True, verbose_name="處遇方式"),
        ),
        migrations.AlterField(
            model_name="counselingrecord",
            name="author",
            field=models.ForeignKey(
                on_delete=models.PROTECT,
                related_name="authored_counseling_records",
                to="accounts.user",
                verbose_name="記錄人員",
            ),
        ),
    ]
