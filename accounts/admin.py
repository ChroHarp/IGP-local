from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Count
from django.http import Http404, HttpResponseRedirect
from django.template.response import TemplateResponse
from django.shortcuts import get_object_or_404
from django.urls import path, reverse
from django.utils import timezone
from django.utils.html import format_html

from .forms import BulkIGPPlanForm, BulkSemesterPlanForm, CopySemesterPlanForm, InitialIGPProfileForm, StudentImportForm, TeacherCreateForm, TeacherStudentAssignmentForm
from .importers import import_basic_students
from .models import Assessment, AwardRecord, CoursePlan, FamilyMember, Guardian, IGPPlan, InitialIGPProfile, Interest, LearningOutcome, ProgramDocument, SchoolSetting, SemesterPlan, Student, StudentStaffAssignment, Teacher, User
from .policies import (
    can_add_student,
    can_edit_student,
    can_manage_accounts,
    can_manage_program_documents,
    can_manage_school_settings,
    can_manage_learning_outcomes,
    students_for_learning_outcomes,
    can_view_program_documents,
    can_view_student,
    visible_students_for,
)

admin.site.site_header = "IGP 本地管理"
admin.site.site_title = "IGP 本地管理"
admin.site.index_title = "學校資料管理"


def current_academic_year():
    return SchoolSetting.objects.values_list("academic_year", flat=True).first() or ""


_original_get_app_list = admin.site.get_app_list


def get_grouped_app_list(request, app_label=None):
    app_list = _original_get_app_list(request, app_label)
    if app_label:
        return app_list
    accounts_app = next((app for app in app_list if app["app_label"] == "accounts"), None)
    if not accounts_app:
        return app_list
    igp_models = {"igpplan", "semesterplan", "courseplan", "learningoutcome"}
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
        ("優勢、需求與補充", {"fields": ("cognitive_strengths", "emotional_strengths", "academic_strengths", "cognitive_needs", "emotional_needs", "academic_needs", "notes"), "classes": ("strength-fields",)}),
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


class IGPPlanInline(StudentRelatedInlinePermissions, admin.TabularInline):
    model = IGPPlan
    extra = 0


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
    change_list_template = "admin/accounts/igpplan/change_list.html"
    list_display = ("student", "academic_year", "overall_goal")
    list_filter = ("academic_year",)
    search_fields = ("student__full_name", "academic_year", "overall_goal")

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        current_year = current_academic_year()
        if current_year and "academic_year" not in request.GET:
            return queryset.filter(academic_year=current_year)
        return queryset

    def get_urls(self):
        return [path("bulk/", self.admin_site.admin_view(self.bulk_view), name="accounts_igpplan_bulk")] + super().get_urls()

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
            self.message_user(request, "???????????????????", messages.SUCCESS)
            return HttpResponseRedirect(reverse("admin:accounts_igpplan_changelist"))
        return TemplateResponse(request, "admin/accounts/igp/bulk_form.html", {
            **self.admin_site.each_context(request), "title": "???? IGP ????", "form": form, "opts": self.model._meta,
        })


@admin.register(SemesterPlan)
class SemesterPlanAdmin(StudentDataAdmin):
    change_list_template = "admin/accounts/semesterplan/change_list.html"
    student_lookup = "igp_plan__student"
    parent_field = "igp_plan"
    parent_student_lookup = "student"
    list_display = ("igp_plan", "semester", "goals", "copy_link")
    list_filter = ("semester", "igp_plan__academic_year")
    search_fields = ("igp_plan__student__full_name", "goals")
    actions = ("copy_selected_plan",)

    @admin.action(description="Copy selected plan to other students")
    def copy_selected_plan(self, request, queryset):
        if queryset.count() != 1:
            self.message_user(request, "Select exactly one source semester plan.", messages.ERROR)
            return None
        return HttpResponseRedirect(reverse("admin:accounts_semesterplan_copy", args=[queryset.get().pk]))

    @admin.display(description="??")
    def copy_link(self, obj):
        return format_html('<a href="{}">???????</a>', reverse("admin:accounts_semesterplan_copy", args=[obj.pk]))

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
            self.message_user(request, "????????????????", messages.SUCCESS)
            return HttpResponseRedirect(reverse("admin:accounts_semesterplan_changelist"))
        return TemplateResponse(request, "admin/accounts/igp/bulk_form.html", {
            **self.admin_site.each_context(request), "title": "????????", "form": form, "opts": self.model._meta,
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
                    defaults={"overall_goal": source.igp_plan.overall_goal, "notes": source.igp_plan.notes},
                )
                target_semester, _ = SemesterPlan.objects.get_or_create(
                    igp_plan=target_igp,
                    semester=source.semester,
                    defaults={"goals": source.goals, "strategies": source.strategies},
                )
                for course in source.course_plans.all():
                    CoursePlan.objects.get_or_create(
                        semester_plan=target_semester,
                        course_name=course.course_name,
                        defaults={"goals": course.goals, "activities": course.activities},
                    )
            self.message_user(request, "????????????????????", messages.SUCCESS)
            return HttpResponseRedirect(reverse("admin:accounts_semesterplan_changelist"))
        return TemplateResponse(request, "admin/accounts/igp/bulk_form.html", {
            **self.admin_site.each_context(request), "title": f"?????{source}", "form": form, "opts": self.model._meta,
        })


@admin.register(CoursePlan)
class CoursePlanAdmin(StudentDataAdmin):
    student_lookup = "semester_plan__igp_plan__student"
    parent_field = "semester_plan"
    parent_student_lookup = "igp_plan__student"
    list_display = ("course_name", "semester_plan")
    search_fields = ("course_name", "semester_plan__igp_plan__student__full_name")


@admin.register(LearningOutcome)
class LearningOutcomeAdmin(StudentDataAdmin):
    student_lookup = "course_plan__semester_plan__igp_plan__student"
    parent_field = "course_plan"
    parent_student_lookup = "semester_plan__igp_plan__student"
    list_display = ("course_plan", "recorded_on", "outcome")
    list_filter = ("recorded_on",)
    search_fields = ("course_plan__semester_plan__igp_plan__student__full_name", "outcome")

    def get_queryset(self, request):
        return super(StudentDataAdmin, self).get_queryset(request).filter(
            course_plan__semester_plan__igp_plan__student__in=students_for_learning_outcomes(request.user)
        )

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "course_plan":
            kwargs["queryset"] = CoursePlan.objects.filter(
                semester_plan__igp_plan__student__in=students_for_learning_outcomes(request.user)
            )
        return super(StudentDataAdmin, self).formfield_for_foreignkey(db_field, request, **kwargs)

    def has_module_permission(self, request):
        return can_manage_learning_outcomes(request.user)

    def has_view_permission(self, request, obj=None):
        return can_manage_learning_outcomes(request.user, obj.course_plan.semester_plan.igp_plan.student) if obj else can_manage_learning_outcomes(request.user)

    def has_change_permission(self, request, obj=None):
        return can_manage_learning_outcomes(request.user, obj.course_plan.semester_plan.igp_plan.student) if obj else can_manage_learning_outcomes(request.user)

    def has_add_permission(self, request):
        return can_manage_learning_outcomes(request.user)


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
        StudentStaffAssignment.Role.COURSE_TEACHER,
    )

    def get_urls(self):
        return [path("teacher/add/", self.admin_site.admin_view(self.teacher_add_view), name="accounts_studentstaffassignment_teacher_add"), path("teacher/<int:staff_id>/", self.admin_site.admin_view(self.teacher_view), name="accounts_studentstaffassignment_teacher")] + super().get_urls()

    def changelist_view(self, request, extra_context=None):
        if not can_manage_school_settings(request.user):
            raise PermissionDenied
        teachers = Teacher.objects.filter(is_active=True).select_related("account")
        active = StudentStaffAssignment.objects.filter(is_active=True, end_date__isnull=True)
        active_counts = {
            item["staff_id"]: item["count"]
            for item in active.values("staff_id").annotate(count=Count("id"))
        }
        role_labels = dict(StudentStaffAssignment.Role.choices)
        active_roles = {}
        for item in active.values("staff_id", "role").distinct():
            active_roles.setdefault(item["staff_id"], []).append(role_labels[item["role"]])
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
            self.message_user(request, "教師資料已建立；可分別勾選導師、個管與任課學生。", messages.SUCCESS)
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
    list_display = ("title", "document_type", "academic_year", "semester", "uploaded_by", "uploaded_at", "download_link")
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

    def has_view_permission(self, request, obj=None):
        return can_view_program_documents(request.user)

    def has_change_permission(self, request, obj=None):
        return can_manage_program_documents(request.user)

    def has_add_permission(self, request):
        return can_manage_program_documents(request.user)

    def has_delete_permission(self, request, obj=None):
        return can_manage_program_documents(request.user)




















