from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Count
from django.http import Http404, HttpResponseRedirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils import timezone
from django.utils.html import format_html

from .forms import InitialIGPProfileForm, StudentImportForm, TeacherCreateForm, TeacherStudentAssignmentForm
from .importers import import_basic_students
from .models import AwardRecord, FamilyMember, Guardian, InitialIGPProfile, ProgramDocument, SchoolSetting, Student, StudentStaffAssignment, Teacher, User
from .policies import (
    can_add_student,
    can_edit_student,
    can_manage_accounts,
    can_manage_program_documents,
    can_manage_school_settings,
    can_view_program_documents,
    can_view_student,
    visible_students_for,
)

admin.site.site_header = "IGP 本地管理"
admin.site.site_title = "IGP 本地管理"
admin.site.index_title = "學校資料管理"


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ("username", "email", "role", "is_approved", "is_active", "is_staff")
    list_filter = ("role", "is_approved", "is_active", "is_staff")
    search_fields = ("username", "email", "first_name", "last_name")
    fieldsets = BaseUserAdmin.fieldsets + (("IGP 權限", {"fields": ("role", "is_approved")}),)
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ("帳號資料", {"fields": ("email", "first_name", "last_name", "role", "is_approved")}),
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


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ("full_name", "grade", "class_name", "seat_number", "is_active")
    list_filter = ("is_active", "grade", "gender")
    search_fields = ("full_name", "student_number", "class_name")
    inlines = (GuardianInline, FamilyMemberInline, InitialIGPProfileInline, AwardRecordInline)
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




















