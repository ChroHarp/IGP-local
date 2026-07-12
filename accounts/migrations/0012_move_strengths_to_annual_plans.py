from django.db import migrations


def copy_profile_analysis(apps, schema_editor):
    IGPPlan = apps.get_model("accounts", "IGPPlan")
    InitialIGPProfile = apps.get_model("accounts", "InitialIGPProfile")
    fields = (
        "cognitive_strengths", "emotional_strengths", "academic_strengths",
        "cognitive_needs", "emotional_needs", "academic_needs",
    )
    for profile in InitialIGPProfile.objects.all():
        values = {field: getattr(profile, field) for field in fields}
        values["qualitative_analysis"] = profile.notes
        IGPPlan.objects.filter(student_id=profile.student_id).update(**values)


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0011_courseplan_affective_support_and_more"),
    ]

    operations = [
        migrations.RunPython(copy_profile_analysis, migrations.RunPython.noop),
    ]
