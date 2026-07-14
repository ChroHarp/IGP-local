from django.db import migrations


SHARED_FIELDS = (
    "course_name",
    "teacher_id",
    "goals",
    "activities",
    "learning_domains",
    "special_needs_courses",
    "cognitive_adjustments",
    "affective_support",
    "skill_training",
)


def create_templates(apps, schema_editor):
    CoursePlan = apps.get_model("accounts", "CoursePlan")
    LearningPerformance = apps.get_model("accounts", "LearningPerformance")
    groups = {}
    plans = CoursePlan.objects.filter(is_template=False).select_related("semester_plan__igp_plan")
    for plan in plans.order_by("pk"):
        key = (
            plan.semester_plan.igp_plan.academic_year,
            plan.semester_plan.semester,
            plan.course_name,
        )
        groups.setdefault(key, []).append(plan)

    for plans in groups.values():
        source = plans[0]
        values = {field: getattr(source, field) for field in SHARED_FIELDS}
        template = CoursePlan.objects.create(
            semester_plan_id=source.semester_plan_id,
            is_template=True,
            is_active=False,
            **values,
        )
        for item in LearningPerformance.objects.filter(course_plan_id=source.pk).order_by("sort_order", "pk"):
            LearningPerformance.objects.create(
                course_plan_id=template.pk,
                description=item.description,
                adjustment=item.adjustment,
                assessment_methods=item.assessment_methods,
                sort_order=item.sort_order,
            )
        CoursePlan.objects.filter(pk__in=[plan.pk for plan in plans]).update(template_id=template.pk)


def remove_templates(apps, schema_editor):
    CoursePlan = apps.get_model("accounts", "CoursePlan")
    CoursePlan.objects.filter(is_template=True).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0016_course_plan_templates"),
    ]

    operations = [
        migrations.RunPython(create_templates, remove_templates),
    ]