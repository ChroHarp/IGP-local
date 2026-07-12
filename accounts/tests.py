from datetime import date, timedelta
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.files.storage import InMemoryStorage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from .importers import import_basic_students
from .models import AwardRecord, FamilyMember, Guardian, InitialIGPProfile, ProgramDocument, Student, StudentStaffAssignment, Teacher
from .policies import approved_google_user_for_email, visible_students_for


class ProjectSmokeTests(TestCase):
    def test_health_check(self):
        response = self.client.get(reverse("health"), secure=True)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"ok")

    def test_custom_user_model_is_active(self):
        user = get_user_model().objects.create_user(
            username="phase-one-user",
            email="phase-one@example.edu.tw",
            password="safe-test-password",
        )

        self.assertEqual(user.email, "phase-one@example.edu.tw")


class AccountLoginTests(TestCase):
    def test_approved_local_user_can_open_login_and_log_in(self):
        user = get_user_model().objects.create_user(
            username="joyce", email="joyce@example.edu.tw", password="safe-test-password",
            is_approved=True, is_active=True,
        )

        self.assertEqual(self.client.get(reverse("account_login")).status_code, 200)
        response = self.client.post(reverse("account_login"), {"login": user.username, "password": "safe-test-password"})

        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.client.post(reverse("account_logout")).status_code, 302)


class PhaseOneModelTests(TestCase):
    def setUp(self):
        self.student = Student.objects.create(full_name="測試學生")
        self.teacher = get_user_model().objects.create_user(
            username="teacher",
            email="teacher@example.edu.tw",
            password="safe-test-password",
            is_approved=True,
        )
        self.teacher_record = Teacher.objects.create(
            full_name="測試教師", account=self.teacher
        )

    def test_only_one_primary_guardian_is_allowed(self):
        Guardian.objects.create(
            student=self.student,
            relationship=Guardian.Relationship.LEGAL_GUARDIAN,
            full_name="測試家長一",
            is_primary=True,
        )

        with self.assertRaises(IntegrityError), transaction.atomic():
            Guardian.objects.create(
                student=self.student,
                relationship=Guardian.Relationship.OTHER,
                full_name="測試家長二",
                is_primary=True,
            )

    def test_assignment_rejects_an_end_date_before_its_start_date(self):
        assignment = StudentStaffAssignment(
            student=self.student,
            staff=self.teacher_record,
            role=StudentStaffAssignment.Role.COURSE_TEACHER,
            start_date=date.today(),
            end_date=date.today() - timedelta(days=1),
        )

        with self.assertRaises(ValidationError):
            assignment.full_clean()

    def test_only_one_current_case_manager_is_allowed(self):
        other_account = get_user_model().objects.create_user(
            username="other-case-manager",
            email="other-case-manager@example.edu.tw",
            password="safe-test-password",
        )
        other_teacher = Teacher.objects.create(full_name="other", account=other_account)
        StudentStaffAssignment.objects.create(
            student=self.student,
            staff=self.teacher_record,
            role=StudentStaffAssignment.Role.CASE_MANAGER,
        )
        duplicate = StudentStaffAssignment(
            student=self.student,
            staff=other_teacher,
            role=StudentStaffAssignment.Role.CASE_MANAGER,
        )

        with self.assertRaises(ValidationError):
            duplicate.full_clean()

    def test_google_policy_requires_an_approved_active_local_user(self):
        self.assertEqual(
            approved_google_user_for_email("TEACHER@example.edu.tw"),
            self.teacher,
        )

        self.teacher.is_approved = False
        self.teacher.save(update_fields=["is_approved"])
        self.assertIsNone(approved_google_user_for_email("teacher@example.edu.tw"))


    def test_phase_two_plan_links_learning_outcomes_to_a_student(self):
        from .models import CoursePlan, IGPPlan, LearningOutcome, SemesterPlan

        plan = IGPPlan.objects.create(student=self.student, academic_year="114", overall_goal="research")
        semester = SemesterPlan.objects.create(igp_plan=plan, semester=1, goals="project")
        course = CoursePlan.objects.create(semester_plan=semester, course_name="science", goals="question")
        outcome = LearningOutcome.objects.create(course_plan=course, outcome="record")

        self.assertEqual(outcome.course_plan.semester_plan.igp_plan.student, self.student)


class StudentAccessTests(TestCase):
    def setUp(self):
        self.visible_student = Student.objects.create(full_name="可見學生")
        self.hidden_student = Student.objects.create(full_name="不可見學生")
        self.case_manager = self.create_user("case-manager", get_user_model().Role.CASE_MANAGER)
        self.course_teacher = self.create_user("course-teacher", get_user_model().Role.COURSE_TEACHER)
        self.system_admin = self.create_user("system-admin", get_user_model().Role.SYSTEM_ADMIN)
        self.school_lead = self.create_user("school-lead", get_user_model().Role.SPECIAL_EDUCATION_LEAD)
        self.case_manager_record = Teacher.objects.create(
            full_name="個管教師", account=self.case_manager
        )
        StudentStaffAssignment.objects.create(
            student=self.visible_student,
            staff=self.case_manager_record,
            role=StudentStaffAssignment.Role.CASE_MANAGER,
        )

    def create_user(self, username, role):
        return get_user_model().objects.create_user(
            username=username,
            email=f"{username}@example.edu.tw",
            password="safe-test-password",
            role=role,
            is_approved=True,
            is_staff=True,
        )

    def test_case_manager_only_sees_assigned_students(self):
        self.assertQuerySetEqual(visible_students_for(self.case_manager), [self.visible_student])

    def test_course_teacher_and_system_admin_see_no_student_data_by_default(self):
        self.assertQuerySetEqual(visible_students_for(self.course_teacher), [])
        self.assertQuerySetEqual(visible_students_for(self.system_admin), [])

    def test_special_education_lead_sees_all_students(self):
        self.assertQuerySetEqual(
            visible_students_for(self.school_lead),
            [self.visible_student, self.hidden_student],
            ordered=False,
        )

    def test_admin_list_never_exposes_an_unassigned_student(self):
        self.client.force_login(self.case_manager)

        response = self.client.get(reverse("admin:accounts_student_changelist"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "可見學生")
        self.assertNotContains(response, "不可見學生")
    def test_student_change_form_groups_data_into_tabs(self):
        InitialIGPProfile.objects.create(
            student=self.visible_student,
            family_culture="重視閱讀",
            cognitive_strengths="理解力佳",
        )
        AwardRecord.objects.create(
            student=self.visible_student,
            activity_name="科展",
            award="第一名",
        )
        self.client.force_login(self.school_lead)

        response = self.client.get(reverse("admin:accounts_student_change", args=[self.visible_student.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "基本資料")
        self.assertContains(response, "家庭與聯絡")
        self.assertContains(response, "學生能力分析")
        self.assertContains(response, "得獎與紀錄")
        self.assertContains(response, "重視閱讀")
        self.assertContains(response, "科展")
    def test_igp_plans_default_to_the_school_academic_year(self):
        from .models import IGPPlan, SchoolSetting

        SchoolSetting.objects.create(name="Test School", academic_year="115")
        IGPPlan.objects.create(student=self.visible_student, academic_year="114", overall_goal="obsolete-goal-marker")
        IGPPlan.objects.create(student=self.hidden_student, academic_year="115", overall_goal="current")
        self.client.force_login(self.school_lead)

        response = self.client.get(reverse("admin:accounts_igpplan_changelist"))

        self.assertContains(response, "current")
        self.assertNotContains(response, "obsolete-goal-marker")

    def test_selected_semester_plan_can_open_the_copy_action(self):
        from .models import IGPPlan, SemesterPlan

        plan = IGPPlan.objects.create(student=self.visible_student, academic_year="115", overall_goal="goal")
        semester = SemesterPlan.objects.create(igp_plan=plan, semester=1, goals="semester goal")
        self.client.force_login(self.school_lead)

        response = self.client.post(
            reverse("admin:accounts_semesterplan_changelist"),
            {"action": "copy_selected_plan", "_selected_action": semester.pk},
        )

        self.assertRedirects(response, reverse("admin:accounts_semesterplan_copy", args=[semester.pk]))

    def test_special_education_lead_can_open_the_import_page(self):
        self.client.force_login(self.school_lead)

        response = self.client.get(reverse("admin:accounts_student_import"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "匯入學生基礎資料")
    def test_superuser_can_open_an_empty_student_list(self):
        StudentStaffAssignment.objects.all().delete()
        Student.objects.all().delete()
        get_user_model().objects.all().delete()
        Student.objects.all().delete()
        superuser = get_user_model().objects.create_superuser(
            username="break-glass",
            email="break-glass@example.edu.tw",
            password="safe-test-password",
        )
        self.client.force_login(superuser)

        response = self.client.get(reverse("admin:accounts_student_changelist"))

        self.assertEqual(response.status_code, 200)

class BatchImportTests(TestCase):
    def workbook(self, rows):
        from openpyxl import Workbook

        workbook = Workbook()
        worksheet = workbook.active
        worksheet.append(["學生姓名", "性別", "年級", "班別", "座號", "出生年月日", "法定代理人", "法定代理人連絡電話 (手機)"])
        for row in rows:
            worksheet.append(row)
        data = BytesIO()
        workbook.save(data)
        data.seek(0)
        return data

    def test_preview_does_not_write_student_data(self):
        result = import_basic_students(
            self.workbook([["預覽學生", "女", 7, "701", 3, date(2013, 1, 2), "預覽家長", "0912345678"]]),
            apply=False,
        )

        self.assertTrue(result.is_valid)
        self.assertEqual(result.create_count, 1)
        self.assertFalse(Student.objects.filter(full_name="預覽學生").exists())

    def test_apply_creates_student_and_primary_guardian(self):
        result = import_basic_students(
            self.workbook([["匯入學生", "男", 7, "701", 4, date(2013, 2, 3), "匯入家長", "0987654321"]]),
            apply=True,
        )

        student = Student.objects.get(full_name="匯入學生")
        self.assertTrue(result.is_valid)
        self.assertEqual(student.guardians.get().full_name, "匯入家長")
        self.assertTrue(student.guardians.get().is_primary)
        self.assertTrue(InitialIGPProfile.objects.filter(student=student).exists())

    def test_import_maps_igp_profile_family_award_and_multiple_needs(self):
        from openpyxl import Workbook

        headers = [
            "學生姓名", "性別", "年級", "班別", "是否有雙重特教需求", "父親姓名", "父親畢業科系",
            "父親專長", "父親連絡電話", "父親服務機關", "家庭文化特質", "主要照顧者", "主要協助學習者",
            "家庭經濟狀況", "照顧者管教態度", "與家人互動情形", "第一階段-數學性向測驗分數",
            "科學興趣", "認知優勢特質", "情意弱勢特質", "獲獎日期", "競賽/活動名稱", "主辦單位", "獎項", "得獎類型", "填寫者",
        ]
        row = [
            "完整匯入學生", "女", 7, "701", "是", "王父", "工程", "程式設計", "0911", "科技公司",
            "一般生", "父親, 母親", "母親", "小康", "民主式", "5", "97", "數學, 天文",
            "記憶能力, 理解能力", "情緒控制", "2025-01-21", "科展", "教育局", "第一名", "團體獎", "家長觀察",
        ]
        workbook = Workbook()
        worksheet = workbook.active
        worksheet.append(headers)
        worksheet.append(row)
        data = BytesIO()
        workbook.save(data)
        data.seek(0)

        result = import_basic_students(data, apply=True)

        student = Student.objects.get(full_name="完整匯入學生")
        profile = student.initial_igp_profile
        self.assertTrue(result.is_valid)
        self.assertTrue(student.has_multiple_special_education_needs)
        self.assertEqual(profile.family_culture, "一般生")
        self.assertEqual(profile.primary_caregiver, "父親, 母親")
        self.assertEqual(profile.cognitive_strengths, "記憶能力, 理解能力")
        self.assertEqual(FamilyMember.objects.get(student=student, relationship="父親").specialty, "程式設計")
        self.assertEqual(AwardRecord.objects.get(student=student).activity_name, "科展")

    def test_backfill_populates_existing_raw_response(self):
        student = Student.objects.create(full_name="回填學生")
        InitialIGPProfile.objects.create(
            student=student,
            raw_response={"是否有雙重特教需求": "是", "科學興趣": "數學, 生物", "填寫者": "學生自評"},
        )

        call_command("backfill_igp_profiles")

        student.refresh_from_db()
        student.initial_igp_profile.refresh_from_db()
        self.assertTrue(student.has_multiple_special_education_needs)
        self.assertEqual(student.initial_igp_profile.science_interests, "數學, 生物")
        self.assertEqual(student.initial_igp_profile.completed_by, "學生自評")
    def test_duplicate_rows_are_rejected_without_writing(self):
        result = import_basic_students(
            self.workbook([
                ["重複學生", "女", 7, "701", 1, date(2013, 3, 4), "家長", ""],
                ["重複學生", "女", 7, "701", 2, date(2013, 3, 4), "家長", ""],
            ]),
            apply=True,
        )

        self.assertFalse(result.is_valid)
        self.assertFalse(Student.objects.filter(full_name="重複學生").exists())


class ProgramDocumentTests(TestCase):
    def setUp(self):
        self.document_field = ProgramDocument._meta.get_field("document_file")
        self.original_storage = self.document_field.storage
        self.document_field.storage = InMemoryStorage()
        self.addCleanup(setattr, self.document_field, "storage", self.original_storage)

    def create_document(self, filename, content):
        return ProgramDocument(
            document_type=ProgramDocument.DocumentType.COURSE_PLAN,
            title="測試文件",
            document_file=SimpleUploadedFile(filename, content),
        )

    def test_valid_pdf_is_accepted_and_fake_pdf_is_rejected(self):
        self.create_document("plan.pdf", b"%PDF-1.7\ncontent").full_clean()
        with self.assertRaises(ValidationError):
            self.create_document("fake.pdf", b"not a pdf").full_clean()

    def test_valid_docx_requires_word_document_xml(self):
        data = BytesIO()
        with ZipFile(data, "w") as archive:
            archive.writestr("word/document.xml", "<w:document />")
        self.create_document("plan.docx", data.getvalue()).full_clean()

    def test_download_is_denied_to_system_admin_and_allowed_to_course_teacher(self):
        document = ProgramDocument.objects.create(
            document_type=ProgramDocument.DocumentType.TIMETABLE,
            title="課表",
            document_file=SimpleUploadedFile("timetable.pdf", b"%PDF-1.7\ncontent"),
        )
        system_admin = get_user_model().objects.create_user(
            username="document-system-admin",
            email="document-system-admin@example.edu.tw",
            password="safe-test-password",
            role=get_user_model().Role.SYSTEM_ADMIN,
            is_staff=True,
        )
        course_teacher = get_user_model().objects.create_user(
            username="document-course-teacher",
            email="document-course-teacher@example.edu.tw",
            password="safe-test-password",
            role=get_user_model().Role.COURSE_TEACHER,
            is_staff=True,
        )

        self.client.force_login(system_admin)
        denied = self.client.get(reverse("program-document-download", args=[document.public_id]))
        self.assertEqual(denied.status_code, 403)

        self.client.force_login(course_teacher)
        allowed = self.client.get(reverse("program-document-download", args=[document.public_id]))
        self.assertEqual(allowed.status_code, 200)









class TeacherAssignmentBoardTests(TestCase):
    def setUp(self):
        self.lead = get_user_model().objects.create_user(
            username="lead", email="lead@example.edu.tw", password="safe-test-password",
            role=get_user_model().Role.SPECIAL_EDUCATION_LEAD, is_approved=True, is_staff=True,
        )
        self.teacher_account = get_user_model().objects.create_user(
            username="course", email="course@example.edu.tw", password="safe-test-password",
            role=get_user_model().Role.COURSE_TEACHER, is_approved=True, is_staff=True,
        )
        self.teacher = Teacher.objects.create(
            full_name="course", account=self.teacher_account,
        )
        self.first_student = Student.objects.create(full_name="第一位學生")
        self.second_student = Student.objects.create(full_name="第二位學生")
        self.url = reverse("admin:accounts_studentstaffassignment_teacher", args=[self.teacher.pk])

    def test_lead_can_assign_many_students_and_preserve_unchecked_history(self):
        self.client.force_login(self.lead)
        board = self.client.get(reverse("admin:accounts_studentstaffassignment_changelist"))
        self.assertEqual(board.status_code, 200)
        self.assertContains(board, "course")

        self.client.post(self.url, {"account": self.teacher_account.pk, "course_students": [self.first_student.pk, self.second_student.pk]})
        self.assertEqual(StudentStaffAssignment.objects.filter(staff=self.teacher, is_active=True).count(), 2)

        self.client.post(self.url, {"account": self.teacher_account.pk, "course_students": [self.first_student.pk]})
        self.assertTrue(StudentStaffAssignment.objects.get(staff=self.teacher, student=self.first_student).is_active)
        self.assertFalse(StudentStaffAssignment.objects.get(staff=self.teacher, student=self.second_student).is_active)

    def test_roles_are_saved_independently_for_the_same_teacher(self):
        self.client.force_login(self.lead)

        self.client.post(self.url, {
            "account": self.teacher_account.pk,
            "homeroom_students": [self.first_student.pk, self.second_student.pk],
            "case_manager_students": [self.second_student.pk],
            "course_students": [self.first_student.pk, self.second_student.pk],
        })

        active = StudentStaffAssignment.objects.filter(staff=self.teacher, is_active=True)
        self.assertEqual(active.count(), 5)
        self.assertTrue(active.filter(student=self.second_student, role=StudentStaffAssignment.Role.HOMEROOM_TEACHER).exists())
        self.assertTrue(active.filter(student=self.second_student, role=StudentStaffAssignment.Role.CASE_MANAGER).exists())
        self.assertTrue(active.filter(student=self.second_student, role=StudentStaffAssignment.Role.COURSE_TEACHER).exists())
        self.client.post(self.url, {
            "account": self.teacher_account.pk,
            "homeroom_students": [self.first_student.pk, self.second_student.pk],
            "case_manager_students": [self.second_student.pk],
            "course_students": [self.first_student.pk],
        })

        self.assertTrue(active.get(student=self.second_student, role=StudentStaffAssignment.Role.HOMEROOM_TEACHER).is_active)
        self.assertTrue(active.get(student=self.second_student, role=StudentStaffAssignment.Role.CASE_MANAGER).is_active)
        self.assertFalse(StudentStaffAssignment.objects.get(student=self.second_student, role=StudentStaffAssignment.Role.COURSE_TEACHER).is_active)
    def test_lead_can_create_a_teacher_without_an_account(self):
        self.client.force_login(self.lead)
        response = self.client.post(
            reverse("admin:accounts_studentstaffassignment_teacher_add"),
            {"full_name": "新任教師"},
        )

        teacher = Teacher.objects.get(full_name="新任教師")
        self.assertRedirects(response, reverse("admin:accounts_studentstaffassignment_teacher", args=[teacher.pk]))
        self.assertIsNone(teacher.account)

    def test_account_can_be_linked_later(self):
        account = get_user_model().objects.create_user(
            username="later", email="later@example.edu.tw", password="safe-test-password",
            role=get_user_model().Role.COURSE_TEACHER, is_approved=True, is_staff=True,
        )
        teacher = Teacher.objects.create(full_name="稍後綁定")
        self.client.force_login(self.lead)

        response = self.client.post(
            reverse("admin:accounts_studentstaffassignment_teacher", args=[teacher.pk]),
            {"account": account.pk},
        )

        teacher.refresh_from_db()
        self.assertRedirects(response, reverse("admin:accounts_studentstaffassignment_changelist"))
        self.assertEqual(teacher.account, account)

    def test_board_exposes_teacher_first_workflow(self):
        self.client.force_login(self.lead)

        board = self.client.get(reverse("admin:accounts_studentstaffassignment_changelist"))
        assignment = self.client.get(self.url)

        self.assertContains(board, "新增教師")
        self.assertContains(board, "指派學生")
        self.assertContains(assignment, 'type="checkbox"', count=6)

    def test_lead_can_change_a_users_role_and_approval(self):
        account = get_user_model().objects.create_user(
            username="editable-user", email="editable@example.edu.tw", password="safe-test-password",
            role=get_user_model().Role.VIEWER, is_staff=True,
        )
        self.client.force_login(self.lead)

        response = self.client.post(
            reverse("admin:accounts_user_change", args=[account.pk]),
            {
                "username": account.username,
                "email": account.email,
                "role": get_user_model().Role.COURSE_TEACHER,
                "is_approved": "on",
                "is_active": "on",
                "is_staff": "on",
                "_save": "Save",
            },
        )

        account.refresh_from_db()
        self.assertRedirects(response, reverse("admin:accounts_user_changelist"))
        self.assertEqual(account.role, get_user_model().Role.COURSE_TEACHER)
        self.assertTrue(account.is_approved)

    def test_teacher_can_be_created_with_an_approved_account(self):
        account = get_user_model().objects.create_user(
            username="matchable", email="matchable@example.edu.tw", password="safe-test-password",
            role=get_user_model().Role.COURSE_TEACHER, is_approved=True, is_staff=True,
        )
        self.client.force_login(self.lead)

        response = self.client.post(
            reverse("admin:accounts_studentstaffassignment_teacher_add"),
            {"full_name": "Matched Teacher", "account": account.pk},
        )

        teacher = Teacher.objects.get(full_name="Matched Teacher")
        self.assertRedirects(response, reverse("admin:accounts_studentstaffassignment_teacher", args=[teacher.pk]))
        self.assertEqual(teacher.account, account)

    def test_user_admin_requires_email_instead_of_saving_an_empty_unique_value(self):
        self.client.force_login(self.lead)

        response = self.client.post(
            reverse("admin:accounts_user_add"),
            {
                "username": "second-teacher",
                "password1": "safe-test-password",
                "password2": "safe-test-password",
                "role": get_user_model().Role.COURSE_TEACHER,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("email", response.context["adminform"].form.errors)
        self.assertFalse(get_user_model().objects.filter(username="second-teacher").exists())

    def test_admin_add_link_redirects_to_teacher_creation(self):
        self.client.force_login(self.lead)
        response = self.client.get(reverse("admin:accounts_studentstaffassignment_add"))
        self.assertRedirects(response, reverse("admin:accounts_studentstaffassignment_teacher_add"))













