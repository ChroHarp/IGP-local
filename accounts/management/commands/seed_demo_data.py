from datetime import date

from django.utils import timezone

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from accounts.models import (
    Assessment,
    AuditEvent,
    CounselingRecord,
    AwardRecord,
    CoursePlan,
    FamilyMember,
    Guardian,
    IGPPlan,
    InitialIGPProfile,
    Interest,
    LearningOutcome,
    LearningOutcomeRating,
    LearningPerformance,
    SchoolSetting,
    SemesterPlan,
    Student,
    StudentStaffAssignment,
    Teacher,
)


DEMO_PASSWORD = "DemoIGP!2026"
ACADEMIC_YEAR = "115"


class Command(BaseCommand):
    help = "建立可重複執行的去識別 IGP 手動測試資料。"

    def handle(self, *args, **options):
        user_model = get_user_model()

        with transaction.atomic():
            SchoolSetting.objects.update_or_create(
                pk=1,
                defaults={"name": "IGP 測試學校", "academic_year": ACADEMIC_YEAR},
            )

            users = {}
            user_specs = (
                ("demo-lead", "demo-lead@example.edu.tw", "示範特教組長", user_model.Role.SPECIAL_EDUCATION_LEAD),
                ("demo-case-a", "demo-case-a@example.edu.tw", "示範個管教師甲", user_model.Role.CASE_MANAGER),
                ("demo-case-b", "demo-case-b@example.edu.tw", "示範個管教師乙", user_model.Role.CASE_MANAGER),
                ("demo-math", "demo-math@example.edu.tw", "示範數學教師", user_model.Role.COURSE_TEACHER),
                ("demo-science", "demo-science@example.edu.tw", "示範科學教師", user_model.Role.COURSE_TEACHER),
                ("demo-homeroom", "demo-homeroom@example.edu.tw", "示範班級導師", user_model.Role.HOMEROOM_TEACHER),
                ("demo-viewer", "demo-viewer@example.edu.tw", "示範閱覽者", user_model.Role.VIEWER),
            )
            for username, email, name, role in user_specs:
                user, _ = user_model.objects.get_or_create(username=username, defaults={"email": email})
                user.email = email
                user.first_name = name
                user.role = role
                user.is_approved = True
                user.is_staff = True
                user.is_active = True
                user.set_password(DEMO_PASSWORD)
                user.save()
                users[username] = user

            teachers = {}
            for username in ("demo-case-a", "demo-case-b", "demo-math", "demo-science", "demo-homeroom"):
                teacher, _ = Teacher.objects.get_or_create(
                    account=users[username], defaults={"full_name": users[username].first_name}
                )
                teacher.full_name = users[username].first_name
                teacher.is_active = True
                teacher.save()
                teachers[username] = teacher

            student_specs = (
                ("DEMO-701-01", "林星澄", Student.Gender.FEMALE, True, date(2013, 2, 14), 7, "701", 3),
                ("DEMO-701-02", "周思遠", Student.Gender.MALE, False, date(2013, 8, 9), 7, "701", 12),
                ("DEMO-702-01", "陳語禾", Student.Gender.FEMALE, False, date(2013, 5, 23), 7, "702", 8),
                ("DEMO-702-02", "許承恩", Student.Gender.MALE, True, date(2013, 11, 3), 7, "702", 19),
            )
            students = {}
            for number, name, gender, multiple_needs, birth, grade, class_name, seat in student_specs:
                student, _ = Student.objects.get_or_create(
                    student_number=number,
                    defaults={"full_name": name},
                )
                student.full_name = name
                student.gender = gender
                student.has_multiple_special_education_needs = multiple_needs
                student.date_of_birth = birth
                student.grade = grade
                student.class_name = class_name
                student.seat_number = seat
                student.email = f"{number.lower()}@student.example.edu.tw"
                student.home_phone = "02-2345-6789"
                student.address = "測試資料，非真實地址"
                student.is_active = True
                student.save()
                students[number] = student

            assignments = (
                ("DEMO-701-01", "demo-case-a", StudentStaffAssignment.Role.CASE_MANAGER),
                ("DEMO-701-02", "demo-case-a", StudentStaffAssignment.Role.CASE_MANAGER),
                ("DEMO-702-01", "demo-case-b", StudentStaffAssignment.Role.CASE_MANAGER),
                ("DEMO-702-02", "demo-case-b", StudentStaffAssignment.Role.CASE_MANAGER),
                ("DEMO-701-01", "demo-homeroom", StudentStaffAssignment.Role.HOMEROOM_TEACHER),
                ("DEMO-701-02", "demo-homeroom", StudentStaffAssignment.Role.HOMEROOM_TEACHER),

            )
            for student_number, teacher_username, role in assignments:
                StudentStaffAssignment.objects.get_or_create(
                    student=students[student_number], staff=teachers[teacher_username], role=role,
                    start_date=date(2026, 8, 1), defaults={"is_active": True},
                )
            StudentStaffAssignment.objects.filter(
                student__student_number__startswith="DEMO-",
                role=StudentStaffAssignment.Role.COURSE_TEACHER,
            ).update(is_active=False)

            for student in students.values():
                Guardian.objects.get_or_create(
                    student=student, full_name=f"{student.full_name}家長",
                    defaults={"relationship": Guardian.Relationship.LEGAL_GUARDIAN, "phone_mobile": "0912-345-678", "email": "guardian@example.edu.tw", "is_primary": True},
                )
                FamilyMember.objects.get_or_create(
                    student=student, full_name=f"{student.full_name}手足",
                    defaults={"relationship": "兄弟姊妹", "organization_or_school": "測試國小", "specialty": "閱讀與運動", "sort_order": 1},
                )
                Assessment.objects.get_or_create(
                    student=student, name="認知能力測驗",
                    defaults={"assessed_on": date(2026, 3, 12), "result": "百分等級 97", "notes": "去識別示範資料"},
                )
                Interest.objects.get_or_create(student=student, category="科學", detail="科學探究與實作", defaults={"notes": "喜歡提出假設並設計實驗"})
                AwardRecord.objects.get_or_create(student=student, activity_name="校內科學展覽", defaults={"award_date": "115 學年度", "organizer": "IGP 測試學校", "award": "佳作", "award_type": "科學"})
                InitialIGPProfile.objects.get_or_create(
                    student=student,
                    defaults={
                        "source_submitted_at": "2026-08-20 09:00",
                        "source_email": "guardian@example.edu.tw",
                        "completed_by": "家長與學生共同填寫",
                        "family_culture": "重視閱讀、討論與自主學習。",
                        "primary_caregiver": "父母共同照顧",
                        "learning_supporter": "家長協助規劃學習時間",
                        "math_aptitude_score": "PR 97",
                        "science_aptitude_score": "PR 95",
                        "science_interests": "物理、化學與生物實驗",
                        "cognitive_strengths": "能快速歸納規律並提出多種解題方法。",
                        "emotional_strengths": "願意與同儕合作分享想法。",
                        "academic_strengths": "數學推理與科學探究表現突出。",
                        "cognitive_needs": "需練習將複雜想法條理化表達。",
                        "emotional_needs": "面對高難度任務時需練習調節挫折感。",
                        "academic_needs": "需提供加深加廣與跨領域任務。",
                    },
                )

            for index, student in enumerate(students.values(), start=1):
                plan, _ = IGPPlan.objects.get_or_create(
                    student=student,
                    academic_year=ACADEMIC_YEAR,
                    defaults={
                        "overall_goal": "發展高層次思考、探究能力與自主學習習慣。",
                        "cognitive_strengths": "邏輯推理與模式辨識佳。",
                        "emotional_strengths": "對感興趣的議題具有持續投入的動機。",
                        "academic_strengths": "數學與自然領域表現優異。",
                        "cognitive_needs": "強化論證與反思能力。",
                        "emotional_needs": "建立面對挑戰的成長型思維。",
                        "academic_needs": "安排專題探究及加深加廣教材。",
                        "qualitative_analysis": "具明顯學術潛能，適合以專題與合作任務提供挑戰。",
                        "learning_strategies": "問題導向學習、同儕討論、學習歷程反思。",
                    },
                )
                semester, _ = SemesterPlan.objects.get_or_create(
                    igp_plan=plan, semester=1,
                    defaults={
                        "learning_domains": "數學、自然科學",
                        "special_needs_courses": "創造力與情意發展",
                        "goals": "能規劃並完成一項小型探究專題。",
                        "strategies": "每兩週檢視一次學習歷程並調整策略。",
                    },
                )
                courses = (
                    ("數學專題", "demo-math", "運用多元策略解決非例行問題。"),
                    ("科學探究", "demo-science", "設計實驗並以證據支持結論。"),
                )
                for course_name, teacher_username, goal in courses:
                    course, _ = CoursePlan.objects.get_or_create(
                        semester_plan=semester, course_name=course_name, is_template=False,
                        defaults={
                            "teacher": teachers[teacher_username], "goals": goal,
                            "activities": "小組討論、實作實驗與口頭發表。",
                            "cognitive_adjustments": "加深加廣",
                            "affective_support": "情意技能",
                            "skill_training": "問題解決",
                        },
                    )
                    for order, description in enumerate(("能清楚說明解題或探究步驟。", "能依回饋修正方法並完成反思。"), start=1):
                        performance, _ = LearningPerformance.objects.get_or_create(
                            course_plan=course, sort_order=order,
                            defaults={"description": description, "adjustment": "提供延伸提問與同儕回饋。", "assessment_methods": "觀察、作品與口頭發表"},
                        )
                        if index <= 2 and course_name == "數學專題":
                            LearningOutcomeRating.objects.get_or_create(
                                learning_performance=performance,
                                defaults={"rating": 3 if order == 1 else 4, "notes": "已完成示範評分", "updated_by": users["demo-math"]},
                            )
                    LearningOutcome.objects.get_or_create(
                        course_plan=course, recorded_on=date(2026, 10, min(index + 4, 28)),
                        defaults={"outcome": "完成示範專題階段成果並進行分享。", "reflection": "下階段將強化資料整理與論證。"},
                    )

            counseling_specs = (
                ("DEMO-701-01", "demo-case-a", "個管初談（草稿）", "了解近期學習安排與適應情形。", CounselingRecord.Status.DRAFT),
                ("DEMO-701-02", "demo-case-a", "個管追蹤（已送審）", "追蹤作業規劃與時間管理。", CounselingRecord.Status.SUBMITTED),
                ("DEMO-701-01", "demo-homeroom", "導師觀察（草稿）", "記錄班級參與與同儕互動情形。", CounselingRecord.Status.DRAFT),
                ("DEMO-701-01", "demo-math", "數學課觀察（退回修正）", "記錄解題活動中的參與表現。", CounselingRecord.Status.RETURNED),
                ("DEMO-701-02", "demo-math", "數學課追蹤（已審核）", "記錄延伸任務的完成情形。", CounselingRecord.Status.REVIEWED),
                ("DEMO-702-01", "demo-case-b", "個管結案紀錄（已鎖定）", "完成本階段目標檢核與後續建議。", CounselingRecord.Status.LOCKED),
            )
            for student_number, username, subject, content, status in counseling_specs:
                record, _ = CounselingRecord.objects.get_or_create(
                    student=students[student_number], author=users[username], event=subject,
                    defaults={"academic_year": ACADEMIC_YEAR, "recorded_on": date(2026, 10, 15), "summary": content},
                )
                record.academic_year = ACADEMIC_YEAR
                record.participants = "本人、家長、個管老師"
                record.summary = content
                record.intervention = "定期晤談、持續觀察、其他：視需要安排個別輔導"
                record.review_note = "建議持續追蹤。" if status in {CounselingRecord.Status.REVIEWED, CounselingRecord.Status.LOCKED} else ""
                record.status = status
                record.submitted_at = timezone.now() if status != CounselingRecord.Status.DRAFT else None
                record.reviewed_by = users["demo-lead"] if status in {CounselingRecord.Status.REVIEWED, CounselingRecord.Status.LOCKED} else None
                record.reviewed_at = timezone.now() if record.reviewed_by else None
                record.locked_by = users["demo-lead"] if status == CounselingRecord.Status.LOCKED else None
                record.locked_at = timezone.now() if record.locked_by else None
                record.save()
                event_types = [AuditEvent.EventType.COUNSELING_CREATED]
                if status in {CounselingRecord.Status.SUBMITTED, CounselingRecord.Status.RETURNED, CounselingRecord.Status.REVIEWED, CounselingRecord.Status.LOCKED}:
                    event_types.append(AuditEvent.EventType.COUNSELING_SUBMITTED)
                if status == CounselingRecord.Status.RETURNED:
                    event_types.append(AuditEvent.EventType.COUNSELING_RETURNED)
                if status in {CounselingRecord.Status.REVIEWED, CounselingRecord.Status.LOCKED}:
                    event_types.append(AuditEvent.EventType.COUNSELING_REVIEWED)
                if status == CounselingRecord.Status.LOCKED:
                    event_types.append(AuditEvent.EventType.COUNSELING_LOCKED)
                for event_type in event_types:
                    actor = users["demo-lead"] if event_type in {AuditEvent.EventType.COUNSELING_RETURNED, AuditEvent.EventType.COUNSELING_REVIEWED, AuditEvent.EventType.COUNSELING_LOCKED} else users[username]
                    AuditEvent.objects.get_or_create(
                        actor=actor, event_type=event_type,
                        target_model="accounts.counselingrecord", target_pk=str(record.pk),
                        defaults={"summary": record.event},
                    )
        self.stdout.write(self.style.SUCCESS("DEMO 測試資料已建立或更新。"))
        self.stdout.write(f"所有 DEMO 帳號密碼：{DEMO_PASSWORD}")
