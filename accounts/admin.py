from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.core.exceptions import PermissionDenied
from django.core.files.base import ContentFile
from django.db import transaction
from django.db.models import Count, Max, Q
from django.http import Http404, HttpResponseNotAllowed, HttpResponseRedirect
from django.template.response import TemplateResponse
from django.shortcuts import get_object_or_404
from django.urls import path, reverse
from django.utils import timezone
from django.utils.html import format_html
from django.utils.text import get_valid_filename

from .documents import IGPDocumentError, build_igp_docx
from .forms import BulkIGPPlanForm, BulkSemesterPlanForm, CopySemesterPlanForm, CounselingRecordForm, CourseGroupForm, CourseLearningPerformanceFormSet, CoursePlanForm, IGPPlanForm, InitialIGPProfileForm, SemesterPlanForm, LearningPerformanceForm, StudentImportForm, TeacherCreateForm, TeacherStudentAssignmentForm
from .importers import import_basic_students
from .models import Assessment, AuditEvent, CounselingRecord, AwardRecord, CoursePlan, FamilyMember, Guardian, IGPPlan, InitialIGPProfile, Interest, LearningOutcomeRating, LearningPerformance, ProgramDocument, SchoolSetting, SemesterPlan, Student, StudentStaffAssignment, Teacher, User
from .policies import (
    can_add_student,
    can_edit_student,
    can_manage_accounts,
    can_manage_program_documents,
    can_manage_school_settings,
    can_manage_learning_outcomes,
    students_for_learning_outcomes,
    can_view_learning_outcomes,
    can_view_program_document,
    can_view_program_documents,
    program_documents_for,
    can_view_student,
    visible_students_for,
    can_add_counseling_record,
    can_edit_counseling_record,
    can_review_counseling_records,
    counseling_records_for,
    students_for_counseling_authoring,
    students_for_counseling_index,
    students_for_course_plans,)

admin.site.site_header = "IGP 本地管理"
admin.site.site_title = "IGP 本地管理"
admin.site.index_title = "學校資料管理"


def current_academic_year():
    return SchoolSetting.objects.values_list("academic_year", flat=True).first() or ""


def reanchor_course_templates(semester_plan_ids):
    semester_plan_ids = set(semester_plan_ids)
    if not semester_plan_ids:
        return
    templates = CoursePlan.objects.filter(is_template=True, semester_plan_id__in=semester_plan_ids)
    for template in templates:
        replacement = template.student_plans.exclude(
            semester_plan_id__in=semester_plan_ids
        ).select_related("semester_plan").first()
        if replacement:
            template.semester_plan = replacement.semester_plan
            template.save(update_fields=("semester_plan",))


_original_get_app_list = admin.site.get_app_list


def get_grouped_app_list(request, app_label=None):
    app_list = _original_get_app_list(request, app_label)
    if app_label:
        return app_list
    accounts_app = next((app for app in app_list if app["app_label"] == "accounts"), None)
    if not accounts_app:
        return app_list
    igp_models = {"igpplan", "semesterplan", "courseplan", "learningoutcomerating", "counselingrecord"}
    models = [model for model in accounts_app["models"] if model["object_name"].lower() in igp_models]
    if not models:
        return app_list
    accounts_app["models"] = [model for model in accounts_app["models"] if model not in models]
    app_list.append({
        "name": "IGP 計畫", "app_label": "igp", "app_url": reverse("admin:app_list", args=("accounts",)),
        "has_module_perms": True, "models": models,
    })
    return app_list


admin.site.get_app_list = get_grouped_app_list

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ("username", "email", "role", "is_approved", "is_active", "is_staff")
    list_filter = ("role", "is_approved", "is_active", "is_staff")
    search_fields = ("username", "email", "first_name", "last_name")
    fieldsets = (
        (None, {"fields": ("username", "password")}),
        ("帳號資料", {"fields": ("first_name", "last_name", "email")}),
        ("IGP 權限", {"fields": ("role", "is_approved", "is_active", "is_staff")}),
        ("群組與權限", {"fields": ("groups", "user_permissions"), "classes": ("collapse",)}),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ("帳號資料", {"fields": ("email", "first_name", "last_name", "role", "is_approved", "is_active", "is_staff")}),
    )

    def has_module_permission(self, request):
        return can_manage_accounts(request.user)

    def has_view_permission(self, request, obj=None):
        return can_manage_accounts(request.user)

    def has_change_permission(self, request, obj=None):
        return can_manage_accounts(request.user)

    def has_add_permission(self, request):
        return can_manage_accounts(request.user)


class StudentRelatedInlinePermissions:
    def has_view_permission(self, request, obj=None):
        return can_view_student(request.user)

    def has_change_permission(self, request, obj=None):
        return can_edit_student(request.user)

    def has_add_permission(self, request, obj=None):
        return can_edit_student(request.user)

    def has_delete_permission(self, request, obj=None):
        return can_edit_student(request.user)


class GuardianInline(StudentRelatedInlinePermissions, admin.TabularInline):
    model = Guardian
    extra = 0


class FamilyMemberInline(StudentRelatedInlinePermissions, admin.TabularInline):
    model = FamilyMember
    extra = 0


class InitialIGPProfileInline(StudentRelatedInlinePermissions, admin.StackedInline):
    model = InitialIGPProfile
    form = InitialIGPProfileForm
    extra = 1
    max_num = 1
    can_delete = False
    readonly_fields = ("raw_response", "updated_at")
    fieldsets = (
        ("來源", {"fields": ("source_submitted_at", "source_email", "completed_by", "updated_at"), "classes": ("source-fields",)}),
        ("家庭與支持", {"fields": ("additional_family_notes", "family_culture", "primary_caregiver", "learning_supporter", "household_economy", "caregiving_style", "family_interaction"), "classes": ("family-fields",)}),
        ("能力與興趣", {"fields": ("math_aptitude_score", "science_aptitude_score", "math_practical_t_score", "science_practical_t_score", "science_interests", "arts_interests", "other_interests"), "classes": ("ability-fields",)}),
        ("其他得獎紀錄", {"fields": ("other_awards_notes",), "classes": ("award-fields",)}),
        ("原始匯入資料", {"fields": ("raw_response",), "classes": ("collapse",)}),
    )


class AwardRecordInline(StudentRelatedInlinePermissions, admin.TabularInline):
    model = AwardRecord
    extra = 0


class AssessmentInline(StudentRelatedInlinePermissions, admin.TabularInline):
    model = Assessment
    extra = 0


class InterestInline(StudentRelatedInlinePermissions, admin.TabularInline):
    model = Interest
    extra = 0


class IGPPlanInline(StudentRelatedInlinePermissions, admin.StackedInline):
    model = IGPPlan
    form = IGPPlanForm
    extra = 0
    fieldsets = (
        ("年度目標", {"fields": ("academic_year", "overall_goal")}),
        ("優勢能力", {"fields": ("cognitive_strengths", "emotional_strengths", "academic_strengths")}),
        ("弱勢需求", {"fields": ("cognitive_needs", "emotional_needs", "academic_needs")}),
        ("綜合評析與策略", {"fields": ("qualitative_analysis", "learning_strategies", "notes")}),
    )

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ("full_name", "grade", "class_name", "seat_number", "is_active")
    list_filter = ("is_active", "grade", "gender")
    search_fields = ("full_name", "student_number", "class_name")
    inlines = (GuardianInline, FamilyMemberInline, InitialIGPProfileInline, AssessmentInline, InterestInline, AwardRecordInline, IGPPlanInline)
    change_list_template = "admin/accounts/student/change_list.html"
    change_form_template = "admin/accounts/student/change_form.html"
    fieldsets = (
        ("基本資料", {"fields": ("student_number", "full_name", "gender", "has_multiple_special_education_needs", "date_of_birth", "grade", "class_name", "seat_number", "email", "home_phone", "address", "is_active")}),
    )

    def get_urls(self):
        return [path("import-basic-data/", self.admin_site.admin_view(self.import_view), name="accounts_student_import")] + super().get_urls()

    def import_view(self, request):
        if not can_add_student(request.user):
            raise PermissionDenied
        form = StudentImportForm(request.POST or None, request.FILES or None)
        result = None
        if request.method == "POST" and form.is_valid():
            apply = request.POST.get("action") == "apply"
            result = import_basic_students(form.cleaned_data["workbook"], apply=apply)
            if apply and result.is_valid:
                self.message_user(request, "匯入完成。", level="success")
            elif not apply:
                self.message_user(request, "這是預覽，資料尚未寫入。", level="warning")
        return TemplateResponse(request, "admin/accounts/student/import_form.html", {**self.admin_site.each_context(request), "title": "匯入學生基礎資料", "form": form, "result": result, "opts": self.model._meta})

    def get_queryset(self, request):
        return visible_students_for(request.user)

    def has_module_permission(self, request):
        return can_view_student(request.user)

    def has_view_permission(self, request, obj=None):
        return can_view_student(request.user, obj)

    def has_change_permission(self, request, obj=None):
        return can_edit_student(request.user, obj)

    def has_add_permission(self, request):
        return can_add_student(request.user)

    def has_delete_permission(self, request, obj=None):
        return can_manage_school_settings(request.user)


class StudentDataAdmin(admin.ModelAdmin):
    student_lookup = "student"
    parent_field = "student"
    parent_student_lookup = "pk"

    def student_for(self, obj):
        for part in self.student_lookup.split("__"):
            obj = getattr(obj, part)
        return obj

    def get_queryset(self, request):
        return super().get_queryset(request).filter(**{f"{self.student_lookup}__in": visible_students_for(request.user)})

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == self.parent_field:
            kwargs["queryset"] = db_field.remote_field.model._default_manager.filter(
                **{f"{self.parent_student_lookup}__in": visible_students_for(request.user)}
            )
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def has_module_permission(self, request):
        return can_view_student(request.user)

    def has_view_permission(self, request, obj=None):
        return can_view_student(request.user, self.student_for(obj)) if obj else can_view_student(request.user)

    def has_change_permission(self, request, obj=None):
        return can_edit_student(request.user, self.student_for(obj)) if obj else can_view_student(request.user)

    def has_add_permission(self, request):
        return can_view_student(request.user)

    def has_delete_permission(self, request, obj=None):
        return can_edit_student(request.user, self.student_for(obj)) if obj else can_view_student(request.user)


@admin.register(IGPPlan)
class IGPPlanAdmin(StudentDataAdmin):
    form = IGPPlanForm
    change_form_template = "admin/accounts/igpplan/change_form.html"
    fieldsets = (
        ("基本資料", {"fields": ("student", "academic_year", "overall_goal")}),
        ("優勢能力", {"fields": ("cognitive_strengths", "emotional_strengths", "academic_strengths")}),
        ("弱勢需求", {"fields": ("cognitive_needs", "emotional_needs", "academic_needs")}),
        ("綜合評析與策略", {"fields": ("qualitative_analysis", "learning_strategies", "notes")}),
    )
    change_list_template = "admin/accounts/igpplan/change_list.html"
    list_display = ("student", "academic_year", "overall_goal")
    list_filter = ("academic_year",)
    search_fields = ("student__full_name", "academic_year", "overall_goal")
    actions = ("copy_selected_annual_plan",)

    def has_delete_permission(self, request, obj=None):
        return can_manage_school_settings(request.user)

    def delete_model(self, request, obj):
        reanchor_course_templates(obj.semester_plans.values_list("pk", flat=True))
        super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        semester_ids = SemesterPlan.objects.filter(igp_plan__in=queryset).values_list("pk", flat=True)
        reanchor_course_templates(semester_ids)
        super().delete_queryset(request, queryset)

    @admin.action(description="Copy selected annual plan to other students")
    def copy_selected_annual_plan(self, request, queryset):
        if queryset.count() != 1:
            self.message_user(request, "Select exactly one source annual plan.", messages.ERROR)
            return None
        return HttpResponseRedirect(reverse("admin:accounts_igpplan_copy", args=[queryset.get().pk]))

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        current_year = current_academic_year()
        if current_year and "academic_year" not in request.GET:
            return queryset.filter(academic_year=current_year)
        return queryset

    def get_urls(self):
        return [
            path("bulk/", self.admin_site.admin_view(self.bulk_view), name="accounts_igpplan_bulk"),
            path("<int:plan_id>/copy/", self.admin_site.admin_view(self.copy_view), name="accounts_igpplan_copy"),
            path("<int:plan_id>/export-docx/", self.admin_site.admin_view(self.export_docx_view), name="accounts_igpplan_export_docx"),
        ] + super().get_urls()

    def export_docx_view(self, request, plan_id):
        if request.method != "POST":
            return HttpResponseNotAllowed(["POST"])
        plan = get_object_or_404(
            IGPPlan.objects.select_related("student").filter(
                student__in=visible_students_for(request.user)
            ),
            pk=plan_id,
        )
        try:
            content = build_igp_docx(plan)
        except IGPDocumentError as exc:
            self.message_user(request, str(exc), messages.ERROR)
            return HttpResponseRedirect(reverse("admin:accounts_igpplan_change", args=[plan.pk]))

        filename = get_valid_filename(f"{plan.academic_year}_{plan.student.full_name}_IGP.docx")
        document = ProgramDocument(
            student=plan.student,
            document_type=ProgramDocument.DocumentType.IGP_PLAN,
            title=f"{plan.academic_year} 學年度 {plan.student.full_name} IGP",
            academic_year=plan.academic_year,
            document_file=ContentFile(content, name=filename),
            uploaded_by=request.user,
        )
        document.full_clean()
        with transaction.atomic():
            document.save()
            record_audit_event(
                actor=request.user,
                event_type=AuditEvent.EventType.DOCUMENT_UPLOADED,
                target=document,
                summary=document.title,
            )
        return HttpResponseRedirect(reverse("program-document-download", args=[document.public_id]))

    def copy_view(self, request, plan_id):
        if not can_manage_school_settings(request.user):
            raise PermissionDenied
        source = get_object_or_404(IGPPlan, pk=plan_id)
        form = CopySemesterPlanForm(
            request.POST or None,
            students=Student.objects.filter(is_active=True).exclude(pk=source.student_id),
            academic_year=current_academic_year(),
        )
        if request.method == "POST" and form.is_valid():
            fields = ("overall_goal", "notes", "cognitive_strengths", "emotional_strengths", "academic_strengths", "cognitive_needs", "emotional_needs", "academic_needs", "qualitative_analysis", "learning_strategies")
            defaults = {field: getattr(source, field) for field in fields}
            for student in form.cleaned_data["students"]:
                IGPPlan.objects.get_or_create(student=student, academic_year=form.cleaned_data["academic_year"], defaults=defaults)
            self.message_user(request, "Annual plan copied; existing plans were not overwritten.", messages.SUCCESS)
            return HttpResponseRedirect(reverse("admin:accounts_igpplan_changelist"))
        return TemplateResponse(request, "admin/accounts/igp/bulk_form.html", {**self.admin_site.each_context(request), "title": f"Copy annual plan: {source}", "form": form, "opts": self.model._meta})

    def bulk_view(self, request):
        if not can_manage_school_settings(request.user):
            raise PermissionDenied
        form = BulkIGPPlanForm(request.POST or None, students=Student.objects.filter(is_active=True), initial={"academic_year": current_academic_year()})
        if request.method == "POST" and form.is_valid():
            for student in form.cleaned_data["students"]:
                IGPPlan.objects.get_or_create(
                    student=student,
                    academic_year=form.cleaned_data["academic_year"],
                    defaults={"overall_goal": form.cleaned_data["overall_goal"], "notes": form.cleaned_data["notes"]},
                )
            self.message_user(request, "年度計畫已建立；既有計畫未覆寫。", messages.SUCCESS)
            return HttpResponseRedirect(reverse("admin:accounts_igpplan_changelist"))
        return TemplateResponse(request, "admin/accounts/igp/bulk_form.html", {
            **self.admin_site.each_context(request), "title": "批次建立 IGP 年度計畫", "form": form, "opts": self.model._meta,
        })


class CoursePlanInline(StudentRelatedInlinePermissions, admin.TabularInline):
    model = CoursePlan
    form = CoursePlanForm
    extra = 0
    show_change_link = True
    fields = ("course_name", "teacher", "goals")

    def get_queryset(self, request):
        return super().get_queryset(request).filter(is_template=False)


@admin.register(SemesterPlan)
class SemesterPlanAdmin(StudentDataAdmin):
    form = SemesterPlanForm
    inlines = (CoursePlanInline,)
    fieldsets = (
        ("課程需求評估", {"fields": ("learning_domains", "special_needs_courses")}),
        ("學期目標與策略", {"fields": ("igp_plan", "semester", "goals", "strategies")}),
        ("舊版課程需求評估", {"fields": ("course_needs_assessment",), "classes": ("collapse",)}),
    )
    change_list_template = "admin/accounts/semesterplan/change_list.html"
    student_lookup = "igp_plan__student"
    parent_field = "igp_plan"
    parent_student_lookup = "student"
    list_display = ("igp_plan", "semester", "goals", "copy_link")
    list_filter = ("semester", "igp_plan__academic_year")
    search_fields = ("igp_plan__student__full_name", "goals")
    actions = ("copy_selected_plan",)

    def has_delete_permission(self, request, obj=None):
        return can_manage_school_settings(request.user)

    def delete_model(self, request, obj):
        reanchor_course_templates([obj.pk])
        super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        reanchor_course_templates(queryset.values_list("pk", flat=True))
        super().delete_queryset(request, queryset)

    @admin.action(description="Copy selected plan to other students")
    def copy_selected_plan(self, request, queryset):
        if queryset.count() != 1:
            self.message_user(request, "Select exactly one source semester plan.", messages.ERROR)
            return None
        return HttpResponseRedirect(reverse("admin:accounts_semesterplan_copy", args=[queryset.get().pk]))

    @admin.display(description="複製")
    def copy_link(self, obj):
        return format_html('<a href="{}">複製到其他學生</a>', reverse("admin:accounts_semesterplan_copy", args=[obj.pk]))

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        current_year = current_academic_year()
        if current_year and "igp_plan__academic_year" not in request.GET:
            return queryset.filter(igp_plan__academic_year=current_year)
        return queryset

    def get_urls(self):
        return [
            path("bulk/", self.admin_site.admin_view(self.bulk_view), name="accounts_semesterplan_bulk"),
            path("<int:plan_id>/copy/", self.admin_site.admin_view(self.copy_view), name="accounts_semesterplan_copy"),
        ] + super().get_urls()

    def bulk_view(self, request):
        if not can_manage_school_settings(request.user):
            raise PermissionDenied
        plans = IGPPlan.objects.filter(student__is_active=True, academic_year=current_academic_year())
        form = BulkSemesterPlanForm(request.POST or None, plans=plans)
        if request.method == "POST" and form.is_valid():
            for plan in form.cleaned_data["plans"]:
                SemesterPlan.objects.get_or_create(
                    igp_plan=plan,
                    semester=form.cleaned_data["semester"],
                    defaults={"goals": form.cleaned_data["goals"], "strategies": form.cleaned_data["strategies"]},
                )
            self.message_user(request, "學期計畫已建立；既有計畫未覆寫。", messages.SUCCESS)
            return HttpResponseRedirect(reverse("admin:accounts_semesterplan_changelist"))
        return TemplateResponse(request, "admin/accounts/igp/bulk_form.html", {
            **self.admin_site.each_context(request), "title": "批次建立學期計畫", "form": form, "opts": self.model._meta,
        })

    def copy_view(self, request, plan_id):
        if not can_manage_school_settings(request.user):
            raise PermissionDenied
        source = get_object_or_404(SemesterPlan.objects.select_related("igp_plan"), pk=plan_id)
        students = Student.objects.filter(is_active=True).exclude(pk=source.igp_plan.student_id)
        form = CopySemesterPlanForm(request.POST or None, students=students, academic_year=current_academic_year())
        if request.method == "POST" and form.is_valid():
            for student in form.cleaned_data["students"]:
                target_igp, _ = IGPPlan.objects.get_or_create(
                    student=student,
                    academic_year=form.cleaned_data["academic_year"],
                    defaults={
                        "overall_goal": source.igp_plan.overall_goal, "notes": source.igp_plan.notes,
                        "cognitive_strengths": source.igp_plan.cognitive_strengths,
                        "emotional_strengths": source.igp_plan.emotional_strengths,
                        "academic_strengths": source.igp_plan.academic_strengths,
                        "cognitive_needs": source.igp_plan.cognitive_needs,
                        "emotional_needs": source.igp_plan.emotional_needs,
                        "academic_needs": source.igp_plan.academic_needs,
                        "qualitative_analysis": source.igp_plan.qualitative_analysis,
                        "learning_strategies": source.igp_plan.learning_strategies,
                    },
                )
                target_semester, _ = SemesterPlan.objects.get_or_create(
                    igp_plan=target_igp,
                    semester=source.semester,
                    defaults={"course_needs_assessment": source.course_needs_assessment, "learning_domains": source.learning_domains, "special_needs_courses": source.special_needs_courses, "goals": source.goals, "strategies": source.strategies},
                )
                for course in source.course_plans.filter(is_template=False):
                    CoursePlan.objects.get_or_create(
                        semester_plan=target_semester,
                        course_name=course.course_name,
                        defaults={
                            "teacher": course.teacher, "goals": course.goals, "activities": course.activities,
                            "learning_domains": course.learning_domains, "special_needs_courses": course.special_needs_courses,
                            "cognitive_adjustments": course.cognitive_adjustments, "affective_support": course.affective_support,
                            "skill_training": course.skill_training,
                        },
                    )
                    target_course = CoursePlan.objects.get(semester_plan=target_semester, course_name=course.course_name, is_template=False)
                    for performance in course.learning_performances.all():
                        LearningPerformance.objects.get_or_create(
                            course_plan=target_course, description=performance.description,
                            defaults={"adjustment": performance.adjustment, "assessment_methods": performance.assessment_methods, "sort_order": performance.sort_order},
                        )
            self.message_user(request, "年度計畫已建立；既有計畫未覆寫。?", messages.SUCCESS)
            return HttpResponseRedirect(reverse("admin:accounts_semesterplan_changelist"))
        return TemplateResponse(request, "admin/accounts/igp/bulk_form.html", {
            **self.admin_site.each_context(request), "title": f"複製計畫：{source}", "form": form, "opts": self.model._meta,
        })




class LearningPerformanceInline(admin.TabularInline):
    model = LearningPerformance
    form = LearningPerformanceForm
    extra = 0
    fields = ("description", "adjustment", "assessment_methods")

    def has_view_permission(self, request, obj=None):
        if obj is None:
            return can_view_student(request.user)
        return can_view_student(request.user, obj.semester_plan.igp_plan.student)

    def has_change_permission(self, request, obj=None):
        if obj is None:
            return can_view_student(request.user)
        return can_edit_student(request.user, obj.semester_plan.igp_plan.student)

    def has_add_permission(self, request, obj=None):
        return self.has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        return self.has_change_permission(request, obj)


@admin.register(CoursePlan)
class CoursePlanAdmin(StudentDataAdmin):
    form = CoursePlanForm
    inlines = (LearningPerformanceInline,)
    change_list_template = "admin/accounts/courseplan/subject_list.html"
    student_lookup = "semester_plan__igp_plan__student"
    parent_field = "semester_plan"
    parent_student_lookup = "igp_plan__student"
    shared_fields = (
        "course_name", "teacher", "goals", "learning_domains",
        "special_needs_courses", "cognitive_adjustments", "affective_support", "skill_training",
    )

    def get_queryset(self, request):
        return admin.ModelAdmin.get_queryset(self, request).filter(
            semester_plan__igp_plan__student__in=students_for_course_plans(request.user)
        )

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "semester_plan":
            kwargs["queryset"] = SemesterPlan.objects.filter(
                igp_plan__student__in=students_for_course_plans(request.user)
            )
        return admin.ModelAdmin.formfield_for_foreignkey(self, db_field, request, **kwargs)

    def has_module_permission(self, request):
        return students_for_course_plans(request.user).exists()

    def has_view_permission(self, request, obj=None):
        if obj is None:
            return self.has_module_permission(request)
        student = obj.semester_plan.igp_plan.student
        return students_for_course_plans(request.user).filter(pk=student.pk).exists()
    class Media:
        css = {"all": ("admin/accounts/parent_child_checkboxes.css",)}
        js = ("admin/accounts/parent_child_checkboxes.js",)

    fieldsets = (
        ("課程基本資料", {"fields": ("semester_plan", "course_name", "teacher", "goals")} ),
        ("課程與特殊需求", {"fields": ("learning_domains", "special_needs_courses")} ),
        ("教育需求與輔導建議事項", {"fields": ("cognitive_adjustments", "affective_support", "skill_training")} ),
    )

    def get_urls(self):
        return [
            path("group/add/", self.admin_site.admin_view(self.group_add_view), name="accounts_courseplan_group_add"),
            path("group/<int:plan_id>/", self.admin_site.admin_view(self.group_view), name="accounts_courseplan_group"),
        ] + super().get_urls()

    def add_view(self, request, form_url="", extra_context=None):
        return HttpResponseRedirect(reverse("admin:accounts_courseplan_group_add"))

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return ("semester_plan", "course_name", "teacher")
        return ()

    def changelist_view(self, request, extra_context=None):
        plans = self.get_queryset(request).filter(is_active=True, is_template=False).select_related(
            "semester_plan__igp_plan__student", "teacher", "template__semester_plan__igp_plan", "template__teacher"
        )
        academic_year = current_academic_year()
        if academic_year:
            plans = plans.filter(semester_plan__igp_plan__academic_year=academic_year)
        groups = {}
        for plan in plans:
            group_plan = plan.template or plan
            key = (group_plan.pk,)
            group = groups.setdefault(key, {"plan": group_plan, "student_ids": set(), "teacher_ids": set()})
            group["student_ids"].add(plan.semester_plan.igp_plan.student_id)
            group["teacher_ids"].add(plan.teacher_id)
        course_groups = [
            {
                "plan": item["plan"],
                "student_count": len(item["student_ids"]),
                "has_mixed_teachers": len(item["teacher_ids"]) > 1,
            }
            for item in groups.values()
        ]
        course_groups.sort(key=lambda item: (
            item["plan"].course_name,
            item["plan"].semester_plan.semester,
        ))
        return TemplateResponse(request, self.change_list_template, {
            **self.admin_site.each_context(request),
            "title": "課程計畫",
            "course_groups": course_groups,
            "opts": self.model._meta,
        })

    def group_plans_for(self, request, source):
        return self.get_queryset(request).filter(
            template=source,
            is_template=False,
        ).select_related("semester_plan__igp_plan__student", "semester_plan__igp_plan")

    def available_students_for(self, request):
        return visible_students_for(request.user).filter(is_active=True)

    def group_form_initial(self, source, plans):
        return {
            "academic_year": source.semester_plan.igp_plan.academic_year,
            "semester": source.semester_plan.semester,
            "students": plans.filter(is_active=True).values_list("semester_plan__igp_plan__student_id", flat=True),
        }

    def plan_defaults(self, source):
        if source and source.pk:
            annual = source.semester_plan.igp_plan
            semester = source.semester_plan
            annual_defaults = {
                field: getattr(annual, field)
                for field in (
                    "overall_goal", "notes", "cognitive_strengths", "emotional_strengths",
                    "academic_strengths", "cognitive_needs", "emotional_needs", "academic_needs",
                    "qualitative_analysis", "learning_strategies",
                )
            }
            semester_defaults = {
                field: getattr(semester, field)
                for field in (
                    "course_needs_assessment", "learning_domains", "special_needs_courses", "goals", "strategies",
                )
            }
            return annual_defaults, semester_defaults
        return (
            {"overall_goal": "請補充年度目標。"},
            {"goals": "請補充學期目標。"},
        )

    def semester_for(self, student, academic_year, semester_number, source):
        annual_defaults, semester_defaults = self.plan_defaults(source)
        annual, _ = IGPPlan.objects.get_or_create(
            student=student,
            academic_year=academic_year,
            defaults=annual_defaults,
        )
        semester, _ = SemesterPlan.objects.get_or_create(
            igp_plan=annual,
            semester=semester_number,
            defaults=semester_defaults,
        )
        return semester

    def sync_performances(self, source, target):
        if source.pk == target.pk:
            return
        for source_item in source.learning_performances.all():
            target_item = target.learning_performances.filter(sort_order=source_item.sort_order).first()
            if target_item is None:
                LearningPerformance.objects.create(
                    course_plan=target,
                    description=source_item.description,
                    adjustment=source_item.adjustment,
                    assessment_methods=source_item.assessment_methods,
                    sort_order=source_item.sort_order,
                )
                continue
            target_item.description = source_item.description
            target_item.adjustment = source_item.adjustment
            target_item.assessment_methods = source_item.assessment_methods
            target_item.save(update_fields=("description", "adjustment", "assessment_methods"))

    def save_group(self, form, formset, source, old_plans, overwrite_existing=False):
        selected_students = list(form.cleaned_data["students"])
        selected_ids = {student.pk for student in selected_students}
        academic_year = form.cleaned_data["academic_year"]
        semester_number = form.cleaned_data["semester"]
        common = form.save(commit=False)
        old_by_student = {
            plan.semester_plan.igp_plan.student_id: plan
            for plan in old_plans
        }

        if source is None:
            first_student = selected_students[0]
            common.semester_plan = self.semester_for(first_student, academic_year, semester_number, None)
            common.is_template = True
            common.is_active = False
            common.save()
            source = common
        else:
            source.save()

        formset.instance = source
        formset.save()

        active_plans = []
        for student in selected_students:
            semester = self.semester_for(student, academic_year, semester_number, source)
            target = old_by_student.get(student.pk)
            if target is None:
                target = CoursePlan.objects.filter(
                    semester_plan=semester,
                    course_name=common.course_name,
                    teacher=common.teacher,
                    is_template=False,
                ).first()
            is_new = target is None
            if target is None:
                target = CoursePlan(semester_plan=semester, template=source)
            target.semester_plan = semester
            target.template = source
            if is_new or overwrite_existing:
                for field in self.shared_fields:
                    setattr(target, field, getattr(common, field))
            target.is_active = True
            target.save()
            if is_new or overwrite_existing:
                self.sync_performances(source, target)
            active_plans.append(target)

        for plan in old_plans:
            if plan.semester_plan.igp_plan.student_id not in selected_ids:
                plan.is_active = False
                plan.save(update_fields=("is_active",))

        return active_plans[0]

    def group_view(self, request, plan_id):
        visible_students = students_for_course_plans(request.user)
        requested_plan = get_object_or_404(
            CoursePlan.objects.select_related("template", "semester_plan__igp_plan__student").filter(
                Q(pk=plan_id, is_template=False, semester_plan__igp_plan__student__in=visible_students)
                | Q(pk=plan_id, is_template=True, student_plans__semester_plan__igp_plan__student__in=visible_students)
            ).distinct()
        )
        source = requested_plan.template or requested_plan
        if request.method == "POST" and not can_edit_student(request.user, requested_plan.semester_plan.igp_plan.student):
            raise PermissionDenied
        if not source.is_template:
            values = {field: getattr(source, field) for field in self.shared_fields}
            with transaction.atomic():
                source = CoursePlan.objects.create(
                    semester_plan=requested_plan.semester_plan,
                    is_template=True,
                    is_active=False,
                    activities=requested_plan.activities,
                    **values,
                )
                self.sync_performances(requested_plan, source)
                requested_plan.template = source
                requested_plan.save(update_fields=("template",))
        plans = self.group_plans_for(request, source)
        students = self.available_students_for(request)
        form = CourseGroupForm(
            request.POST or None,
            instance=source,
            students=students,
            initial=self.group_form_initial(source, plans),
        )
        formset = CourseLearningPerformanceFormSet(
            request.POST or None,
            instance=source,
            prefix="learning_performances",
        )
        if request.method == "POST" and form.is_valid() and formset.is_valid():
            overwrite_existing = request.POST.get("action") == "overwrite"
            with transaction.atomic():
                redirect_plan = self.save_group(
                    form,
                    formset,
                    source,
                    list(plans),
                    overwrite_existing=overwrite_existing,
                )
            message = (
                "課程範本已覆蓋所有勾選學生版本。"
                if overwrite_existing
                else "課程範本已儲存；新增學生已套用範本，既有學生版本保持不變。"
            )
            self.message_user(request, message, messages.SUCCESS)
            return HttpResponseRedirect(reverse("admin:accounts_courseplan_group", args=[redirect_plan.pk]))
        return TemplateResponse(request, "admin/accounts/courseplan/group_form.html", {
            **self.admin_site.each_context(request),
            "title": f"課程：{source.course_name}",
            "opts": self.model._meta,
            "form": form,
            "formset": formset,
            "student_plans": plans.filter(is_active=True),
            "media": self.media + form.media + formset.media,
            "empty_performance_form": formset.empty_form,
        })

    def group_add_view(self, request):
        if not can_view_student(request.user):
            raise PermissionDenied
        students = self.available_students_for(request)
        draft = CoursePlan()
        form = CourseGroupForm(
            request.POST or None,
            instance=draft,
            students=students,
            initial={"academic_year": current_academic_year(), "semester": 1},
        )
        formset = CourseLearningPerformanceFormSet(
            request.POST or None,
            instance=draft,
            prefix="learning_performances",
        )
        if request.method == "POST" and form.is_valid() and formset.is_valid():
            with transaction.atomic():
                redirect_plan = self.save_group(form, formset, None, [])
            self.message_user(request, "課程已建立並同步到所有勾選學生。", messages.SUCCESS)
            return HttpResponseRedirect(reverse("admin:accounts_courseplan_group", args=[redirect_plan.pk]))
        return TemplateResponse(request, "admin/accounts/courseplan/group_form.html", {
            **self.admin_site.each_context(request),
            "title": "新增課程",
            "opts": self.model._meta,
            "form": form,
            "formset": formset,
            "student_plans": (),
            "media": self.media + form.media + formset.media,
            "empty_performance_form": formset.empty_form,
        })

@admin.register(LearningOutcomeRating)
class LearningOutcomeRatingAdmin(admin.ModelAdmin):
    change_list_template = "admin/accounts/learningoutcomerating/subject_list.html"

    def course_plans_for(self, user):
        plans = CoursePlan.objects.filter(is_active=True).select_related("semester_plan__igp_plan__student", "teacher")
        if user.is_superuser or user.role == User.Role.SPECIAL_EDUCATION_LEAD:
            return plans.filter(
                semester_plan__igp_plan__student__in=students_for_learning_outcomes(user)
            )
        return plans.filter(teacher__account=user)

    def get_urls(self):
        return [
            path("subject/<int:course_plan_id>/", self.admin_site.admin_view(self.subject_view), name="accounts_learningoutcomerating_subject"),
            path("student/<int:student_id>/", self.admin_site.admin_view(self.student_view), name="accounts_learningoutcomerating_student"),
        ] + super().get_urls()

    def changelist_view(self, request, extra_context=None):
        subjects = {}
        for plan in self.course_plans_for(request.user):
            key = (plan.semester_plan.igp_plan.academic_year, plan.semester_plan.semester, plan.course_name, plan.teacher_id)
            subjects.setdefault(key, {"plan": plan, "student_ids": set()})["student_ids"].add(plan.semester_plan.igp_plan.student_id)
        rows = [
            {"plan": item["plan"], "student_count": len(item["student_ids"])}
            for item in subjects.values()
        ]
        case_students = Student.objects.none()
        if not request.user.is_superuser and request.user.role != User.Role.SPECIAL_EDUCATION_LEAD:
            case_students = visible_students_for(request.user)
        return TemplateResponse(request, self.change_list_template, {
            **self.admin_site.each_context(request),
            "title": "學習成果評分",
            "subjects": rows,
            "case_students": case_students,
            "opts": self.model._meta,
        })

    def subject_view(self, request, course_plan_id):
        source = get_object_or_404(self.course_plans_for(request.user), pk=course_plan_id)
        semester = source.semester_plan
        plans = self.course_plans_for(request.user).filter(
            course_name=source.course_name,
            semester_plan__semester=semester.semester,
            semester_plan__igp_plan__academic_year=semester.igp_plan.academic_year,
            teacher_id=source.teacher_id,
        ).select_related("semester_plan__igp_plan__student").prefetch_related("learning_performances__rating")
        performances = [performance for plan in plans for performance in plan.learning_performances.all()]
        if request.method == "POST":
            valid_ratings = {str(value) for value, _ in LearningOutcomeRating.Rating.choices}
            with transaction.atomic():
                for performance in performances:
                    value = request.POST.get(f"rating-{performance.pk}")
                    if value in valid_ratings:
                        LearningOutcomeRating.objects.update_or_create(
                            learning_performance=performance,
                            defaults={"rating": int(value), "updated_by": request.user},
                        )
            self.message_user(request, "學習成果評分已儲存。", messages.SUCCESS)
            return HttpResponseRedirect(request.path)
        rows = []
        for performance in performances:
            try:
                current_rating = performance.rating.rating
            except LearningOutcomeRating.DoesNotExist:
                current_rating = None
            rows.append({
                "student": performance.course_plan.semester_plan.igp_plan.student,
                "performance": performance,
                "current_rating": current_rating,
            })
        student_groups = {}
        visible_student_ids = set(visible_students_for(request.user).values_list("pk", flat=True))
        for row in rows:
            student = row["student"]
            group = student_groups.setdefault(student.pk, {
                "student": student,
                "rows": [],
                "can_view_all": student.pk in visible_student_ids,
            })
            group["rows"].append(row)
        return TemplateResponse(request, "admin/accounts/learningoutcomerating/subject_form.html", {
            **self.admin_site.each_context(request), "title": f"{source.course_name}－學習成果評分",
            "source": source, "student_groups": student_groups.values(), "rating_choices": LearningOutcomeRating.Rating.choices, "opts": self.model._meta,
        })

    def student_view(self, request, student_id):
        if request.method != "GET":
            return HttpResponseNotAllowed(["GET"])
        student = get_object_or_404(visible_students_for(request.user), pk=student_id)
        plans = CoursePlan.objects.filter(
            semester_plan__igp_plan__student=student,
        ).select_related("semester_plan__igp_plan", "teacher").prefetch_related(
            "learning_performances__rating"
        ).order_by("-semester_plan__igp_plan__academic_year", "semester_plan__semester", "course_name")
        courses = []
        for plan in plans:
            rows = []
            for performance in plan.learning_performances.all():
                try:
                    rating = performance.rating
                except LearningOutcomeRating.DoesNotExist:
                    rating = None
                rows.append({"performance": performance, "rating": rating})
            courses.append({"plan": plan, "rows": rows})
        return TemplateResponse(request, "admin/accounts/learningoutcomerating/student_detail.html", {
            **self.admin_site.each_context(request),
            "title": f"{student}－全部學習成果",
            "student": student,
            "courses": courses,
            "opts": self.model._meta,
        })

    def get_queryset(self, request):
        return super().get_queryset(request).filter(
            learning_performance__course_plan__in=self.course_plans_for(request.user)
        )

    def has_module_permission(self, request):
        return can_view_learning_outcomes(request.user)

    def has_view_permission(self, request, obj=None):
        if obj:
            student = obj.learning_performance.course_plan.semester_plan.igp_plan.student
            return can_view_learning_outcomes(request.user, student)
        return can_view_learning_outcomes(request.user)

    def has_change_permission(self, request, obj=None):
        if obj:
            student = obj.learning_performance.course_plan.semester_plan.igp_plan.student
            return can_manage_learning_outcomes(request.user, student)
        return can_manage_learning_outcomes(request.user)

    def has_add_permission(self, request):
        return False



def record_audit_event(*, actor, event_type, target, summary=""):
    AuditEvent.objects.create(
        actor=actor,
        event_type=event_type,
        target_model=target._meta.label_lower,
        target_pk=str(target.pk),
        summary=summary[:255],
    )


@admin.register(CounselingRecord)
class CounselingRecordAdmin(admin.ModelAdmin):
    form = CounselingRecordForm
    change_list_template = "admin/accounts/counselingrecord/change_list.html"
    list_display = ("recorded_on", "participants", "event", "summary_brief", "intervention_brief", "author", "status")
    list_display_links = ("recorded_on", "event")
    list_filter = ("status", "academic_year", "recorded_on")
    search_fields = ("student__full_name", "event", "summary", "intervention", "author__username")
    readonly_fields = ("author", "status", "review_note", "submitted_at", "reviewed_by", "reviewed_at", "locked_by", "locked_at", "created_at", "updated_at")
    actions = ("submit_selected", "return_selected", "review_selected", "lock_selected")
    fieldsets = (
        ("輔導紀錄", {"fields": ("student", "academic_year", "recorded_on", "participants", "participants_other", "event", "summary", "intervention", "intervention_other", "author")}),
        ("審核", {"fields": ("status", "review_note", "submitted_at", "reviewed_by", "reviewed_at", "locked_by", "locked_at")}),
        ("系統資訊", {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )

    def get_urls(self):
        return [
            path(
                "student/<int:student_id>/",
                self.admin_site.admin_view(self.student_records_view),
                name="accounts_counselingrecord_student_records",
            ),
        ] + super().get_urls()

    @admin.display(description="內容概要敘述")
    def summary_brief(self, obj):
        return obj.summary if len(obj.summary) <= 80 else f"{obj.summary[:80]}…"

    @admin.display(description="處遇方式")
    def intervention_brief(self, obj):
        return obj.intervention if len(obj.intervention) <= 80 else f"{obj.intervention[:80]}…"

    def changelist_view(self, request, extra_context=None):
        if not self.has_module_permission(request):
            raise PermissionDenied
        records = counseling_records_for(request.user)
        students = students_for_counseling_index(request.user).annotate(
            visible_record_count=Count(
                "counseling_records",
                filter=Q(counseling_records__in=records),
                distinct=True,
            ),
            latest_recorded_on=Max(
                "counseling_records__recorded_on",
                filter=Q(counseling_records__in=records),
            ),
        )
        student_rows = [(student, can_add_counseling_record(request.user, student)) for student in students]
        return TemplateResponse(request, "admin/accounts/counselingrecord/student_list.html", {
            **self.admin_site.each_context(request),
            "title": "輔導紀錄－選擇學生",
            "opts": self.model._meta,
            "student_rows": student_rows,
        })

    def student_records_view(self, request, student_id):
        student = get_object_or_404(students_for_counseling_index(request.user), pk=student_id)
        return super().changelist_view(request, {
            "title": f"{student.full_name}－輔導紀錄",
            "current_student": student,
            "can_add_for_student": can_add_counseling_record(request.user, student),
        })

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "student":
            kwargs["queryset"] = students_for_counseling_authoring(request.user)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def get_queryset(self, request):
        queryset = counseling_records_for(request.user).select_related("student", "author", "reviewed_by", "locked_by")
        student_id = request.resolver_match.kwargs.get("student_id") if request.resolver_match else None
        return queryset.filter(student_id=student_id) if student_id else queryset

    def get_changeform_initial_data(self, request):
        initial = super().get_changeform_initial_data(request)
        student_id = request.GET.get("student")
        if student_id and students_for_counseling_authoring(request.user).filter(pk=student_id).exists():
            initial["student"] = student_id
        return initial

    def get_exclude(self, request, obj=None):
        return ("author", "status", "submitted_at", "reviewed_by", "reviewed_at", "locked_by", "locked_at")

    def get_readonly_fields(self, request, obj=None):
        if obj and can_review_counseling_records(request.user) and obj.status == CounselingRecord.Status.SUBMITTED:
            return tuple(field.name for field in self.model._meta.fields if field.name != "review_note")
        if obj and not can_edit_counseling_record(request.user, obj):
            return tuple(field.name for field in self.model._meta.fields)
        return self.readonly_fields

    def save_model(self, request, obj, form, change):
        if not change:
            if not can_add_counseling_record(request.user, obj.student):
                raise PermissionDenied
            obj.author = request.user
            if not obj.academic_year:
                obj.academic_year = current_academic_year()
        super().save_model(request, obj, form, change)
        if not change:
            record_audit_event(
                actor=request.user,
                event_type=AuditEvent.EventType.COUNSELING_CREATED,
                target=obj,
                summary=f"{obj.student}：{obj.event}",
            )

    def has_module_permission(self, request):
        return counseling_records_for(request.user).exists() or can_add_counseling_record(request.user)

    def has_view_permission(self, request, obj=None):
        if obj is None:
            return self.has_module_permission(request)
        return counseling_records_for(request.user).filter(pk=obj.pk).exists()

    def has_add_permission(self, request):
        return can_add_counseling_record(request.user)

    def has_change_permission(self, request, obj=None):
        if obj is None:
            return self.has_module_permission(request)
        return can_edit_counseling_record(request.user, obj) or (
            can_review_counseling_records(request.user) and obj.status == CounselingRecord.Status.SUBMITTED
        )

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.action(description="送審選取的輔導紀錄")
    def submit_selected(self, request, queryset):
        eligible = queryset.filter(author=request.user, status__in=(CounselingRecord.Status.DRAFT, CounselingRecord.Status.RETURNED))
        with transaction.atomic():
            for record in eligible.select_for_update():
                record.status = CounselingRecord.Status.SUBMITTED
                record.submitted_at = timezone.now()
                record.save(update_fields=("status", "submitted_at", "updated_at"))
                record_audit_event(actor=request.user, event_type=AuditEvent.EventType.COUNSELING_SUBMITTED, target=record, summary=record.event)
        self.message_user(request, f"已送審 {eligible.count()} 筆輔導紀錄。", messages.SUCCESS)

    @admin.action(description="退回選取的輔導紀錄")
    def return_selected(self, request, queryset):
        if not can_review_counseling_records(request.user):
            raise PermissionDenied
        eligible = queryset.filter(status=CounselingRecord.Status.SUBMITTED)
        with transaction.atomic():
            for record in eligible.select_for_update():
                record.status = CounselingRecord.Status.RETURNED
                record.save(update_fields=("status", "updated_at"))
                record_audit_event(actor=request.user, event_type=AuditEvent.EventType.COUNSELING_RETURNED, target=record, summary=record.event)
        self.message_user(request, f"已退回 {eligible.count()} 筆輔導紀錄。", messages.SUCCESS)

    @admin.action(description="審核選取的輔導紀錄")
    def review_selected(self, request, queryset):
        if not can_review_counseling_records(request.user):
            raise PermissionDenied
        eligible = queryset.filter(status=CounselingRecord.Status.SUBMITTED)
        with transaction.atomic():
            for record in eligible.select_for_update():
                record.status = CounselingRecord.Status.REVIEWED
                record.reviewed_by = request.user
                record.reviewed_at = timezone.now()
                record.save(update_fields=("status", "reviewed_by", "reviewed_at", "updated_at"))
                record_audit_event(actor=request.user, event_type=AuditEvent.EventType.COUNSELING_REVIEWED, target=record, summary=record.event)
        self.message_user(request, f"已審核 {eligible.count()} 筆輔導紀錄。", messages.SUCCESS)

    @admin.action(description="鎖定選取的輔導紀錄")
    def lock_selected(self, request, queryset):
        if not can_review_counseling_records(request.user):
            raise PermissionDenied
        eligible = queryset.filter(status=CounselingRecord.Status.REVIEWED)
        with transaction.atomic():
            for record in eligible.select_for_update():
                record.status = CounselingRecord.Status.LOCKED
                record.locked_by = request.user
                record.locked_at = timezone.now()
                record.save(update_fields=("status", "locked_by", "locked_at", "updated_at"))
                record_audit_event(actor=request.user, event_type=AuditEvent.EventType.COUNSELING_LOCKED, target=record, summary=record.event)
        self.message_user(request, f"已鎖定 {eligible.count()} 筆輔導紀錄。", messages.SUCCESS)


@admin.register(AuditEvent)
class AuditEventAdmin(admin.ModelAdmin):
    list_display = ("occurred_at", "event_type", "actor", "target_model", "target_pk", "summary")
    list_filter = ("event_type", "occurred_at")
    search_fields = ("actor__username", "target_model", "target_pk", "summary")
    readonly_fields = ("occurred_at", "actor", "event_type", "target_model", "target_pk", "summary")

    def has_module_permission(self, request):
        return can_manage_school_settings(request.user)

    def has_view_permission(self, request, obj=None):
        return can_manage_school_settings(request.user)

    def has_change_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
@admin.register(SchoolSetting)
class SchoolSettingAdmin(admin.ModelAdmin):
    list_display = ("name", "academic_year", "updated_at")

    def has_module_permission(self, request):
        return can_manage_school_settings(request.user)

    def has_view_permission(self, request, obj=None):
        return can_manage_school_settings(request.user)

    def has_change_permission(self, request, obj=None):
        return can_manage_school_settings(request.user)

    def has_add_permission(self, request):
        return can_manage_school_settings(request.user) and not SchoolSetting.objects.exists()


@admin.register(StudentStaffAssignment)
class StudentStaffAssignmentAdmin(admin.ModelAdmin):
    eligible_roles = (
        StudentStaffAssignment.Role.HOMEROOM_TEACHER,
        StudentStaffAssignment.Role.CASE_MANAGER,
    )

    def get_urls(self):
        return [path("teacher/add/", self.admin_site.admin_view(self.teacher_add_view), name="accounts_studentstaffassignment_teacher_add"), path("teacher/<int:staff_id>/", self.admin_site.admin_view(self.teacher_view), name="accounts_studentstaffassignment_teacher")] + super().get_urls()

    def changelist_view(self, request, extra_context=None):
        if not can_manage_school_settings(request.user):
            raise PermissionDenied
        teachers = Teacher.objects.filter(is_active=True).select_related("account")
        active = StudentStaffAssignment.objects.filter(
            is_active=True,
            end_date__isnull=True,
            role__in=self.eligible_roles,
        )
        active_counts = {
            item["staff_id"]: item["count"]
            for item in active.values("staff_id").annotate(count=Count("id"))
        }
        role_labels = dict(StudentStaffAssignment.Role.choices)
        active_roles = {}
        for item in active.values("staff_id", "role").distinct():
            active_roles.setdefault(item["staff_id"], []).append(role_labels[item["role"]])
        course_counts = CoursePlan.objects.filter(is_active=True).exclude(teacher=None).values("teacher_id").annotate(
            count=Count("semester_plan__igp_plan__student", distinct=True)
        )
        for item in course_counts:
            teacher_id = item["teacher_id"]
            active_roles.setdefault(teacher_id, []).append(role_labels[StudentStaffAssignment.Role.COURSE_TEACHER])
            active_counts[teacher_id] = active_counts.get(teacher_id, 0) + item["count"]
        return TemplateResponse(request, "admin/accounts/studentstaffassignment/teacher_list.html", {
            **self.admin_site.each_context(request), "title": "學生教師指派", "opts": self.model._meta,
            "teacher_rows": [(teacher, "、".join(active_roles.get(teacher.pk, [])) or "尚未指派", active_counts.get(teacher.pk, 0)) for teacher in teachers],
        })

    def teacher_add_view(self, request):
        if not can_manage_school_settings(request.user):
            raise PermissionDenied
        form = TeacherCreateForm(request.POST or None)
        if request.method == "POST" and form.is_valid():
            teacher = form.save()
            self.message_user(request, "教師資料已建立；可指派導師與個管學生，任課學生由課程計畫認定。", messages.SUCCESS)
            return HttpResponseRedirect(reverse("admin:accounts_studentstaffassignment_teacher", args=[teacher.pk]))
        return TemplateResponse(request, "admin/accounts/studentstaffassignment/teacher_add_form.html", {
            **self.admin_site.each_context(request), "title": "新增教師", "opts": self.model._meta, "form": form,
        })

    def teacher_view(self, request, staff_id):
        if not can_manage_school_settings(request.user):
            raise PermissionDenied
        try:
            teacher = Teacher.objects.get(pk=staff_id, is_active=True)
        except Teacher.DoesNotExist as error:
            raise Http404("找不到可指派的教師") from error

        initial = {"account": teacher.account_id}
        if request.method == "GET":
            for role, field_name in TeacherStudentAssignmentForm.assignment_fields:
                initial[field_name] = StudentStaffAssignment.objects.filter(
                    staff=teacher, role=role, is_active=True, end_date__isnull=True
                ).values_list("student_id", flat=True)
        form = TeacherStudentAssignmentForm(request.POST or None, teacher=teacher, initial=initial)
        course_students = Student.objects.filter(
            igp_plans__semester_plans__course_plans__teacher=teacher,
            igp_plans__semester_plans__course_plans__is_active=True,
        ).distinct().order_by("grade", "class_name", "seat_number", "full_name")

        if request.method == "POST" and form.is_valid():
            today = timezone.localdate()
            with transaction.atomic():
                teacher.account = form.cleaned_data["account"]
                teacher.save(update_fields=["account"])
                for role, field_name in form.assignment_fields:
                    selected_ids = set(form.cleaned_data[field_name].values_list("id", flat=True))
                    active = StudentStaffAssignment.objects.select_for_update().filter(
                        staff=teacher, role=role, is_active=True, end_date__isnull=True
                    )
                    active.exclude(student_id__in=selected_ids).update(is_active=False)
                    active_ids = set(active.filter(student_id__in=selected_ids).values_list("student_id", flat=True))
                    for student_id in selected_ids - active_ids:
                        assignment, _ = StudentStaffAssignment.objects.get_or_create(
                            student_id=student_id, staff=teacher, role=role, start_date=today,
                            defaults={"is_active": True},
                        )
                        if not assignment.is_active or assignment.end_date:
                            assignment.is_active = True
                            assignment.end_date = None
                            assignment.save(update_fields=["is_active", "end_date"])
            self.message_user(request, "各身分的學生指派已分別更新；既有歷程仍保留。", messages.SUCCESS)
            return HttpResponseRedirect(reverse("admin:accounts_studentstaffassignment_changelist"))
        return TemplateResponse(request, "admin/accounts/studentstaffassignment/teacher_form.html", {
            **self.admin_site.each_context(request), "title": f"指派學生：{teacher.full_name}",
            "opts": self.model._meta, "teacher": teacher, "form": form,
            "course_students": course_students,
        })

    def add_view(self, request, form_url="", extra_context=None):
        return HttpResponseRedirect(reverse("admin:accounts_studentstaffassignment_teacher_add"))

    def has_module_permission(self, request):
        return can_manage_school_settings(request.user)

    def has_view_permission(self, request, obj=None):
        return can_manage_school_settings(request.user)

    def has_change_permission(self, request, obj=None):
        return can_manage_school_settings(request.user)

    def has_add_permission(self, request):
        return can_manage_school_settings(request.user)

@admin.register(ProgramDocument)
class ProgramDocumentAdmin(admin.ModelAdmin):
    list_display = ("title", "student", "document_type", "academic_year", "semester", "uploaded_by", "uploaded_at", "download_link")
    list_filter = ("document_type", "academic_year", "semester")
    search_fields = ("title", "original_filename")
    readonly_fields = ("original_filename", "uploaded_by", "uploaded_at", "download_link")

    @admin.display(description="下載")
    def download_link(self, obj):
        if not obj or not obj.pk:
            return "－"
        return format_html('<a href="{}">安全下載</a>', reverse("program-document-download", args=[obj.public_id]))

    def save_model(self, request, obj, form, change):
        if not change:
            obj.uploaded_by = request.user
        super().save_model(request, obj, form, change)

    def has_module_permission(self, request):
        return can_view_program_documents(request.user)

    def get_queryset(self, request):
        return program_documents_for(request.user)

    def has_view_permission(self, request, obj=None):
        if obj:
            return can_view_program_document(request.user, obj)
        return can_view_program_documents(request.user)

    def has_change_permission(self, request, obj=None):
        return can_manage_program_documents(request.user)

    def has_add_permission(self, request):
        return can_manage_program_documents(request.user)

    def has_delete_permission(self, request, obj=None):
        return can_manage_program_documents(request.user)




















