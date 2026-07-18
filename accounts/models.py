from datetime import date
from pathlib import Path
from uuid import uuid4

from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone

from .validators import validate_program_document


class User(AbstractUser):
    class Role(models.TextChoices):
        SYSTEM_ADMIN = "system_admin", "技術系統管理員"
        SPECIAL_EDUCATION_LEAD = "special_education_lead", "特教組長／主管"
        CASE_MANAGER = "case_manager", "個管教師"
        COURSE_TEACHER = "course_teacher", "任課教師"
        HOMEROOM_TEACHER = "homeroom_teacher", "班級導師"
        VIEWER = "viewer", "閱覽者"

    email = models.EmailField("Google email", unique=True)
    role = models.CharField("業務角色", max_length=32, choices=Role.choices, default=Role.VIEWER)
    is_approved = models.BooleanField("已核准使用", default=False)

    class Meta:
        verbose_name = "系統使用者"
        verbose_name_plural = "系統使用者"


class SchoolSetting(models.Model):
    name = models.CharField("學校名稱", max_length=100)
    academic_year = models.CharField("目前學年度", max_length=16, blank=True)
    updated_at = models.DateTimeField("更新時間", auto_now=True)

    class Meta:
        verbose_name = "學校設定"
        verbose_name_plural = "學校設定"

    def save(self, *args, **kwargs):
        self.pk = 1
        return super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Student(models.Model):
    class Gender(models.TextChoices):
        UNSPECIFIED = "unspecified", "未填"
        FEMALE = "female", "女"
        MALE = "male", "男"
        OTHER = "other", "其他／自述"

    student_number = models.CharField("學號", max_length=32, unique=True, null=True, blank=True)
    full_name = models.CharField("學生姓名", max_length=100)
    gender = models.CharField("性別", max_length=16, choices=Gender.choices, default=Gender.UNSPECIFIED)
    gifted_categories = models.TextField("資優類別", blank=True)
    has_multiple_special_education_needs = models.BooleanField("雙重特教需求", default=False)
    date_of_birth = models.DateField("出生日期", null=True, blank=True)
    grade = models.PositiveSmallIntegerField("年級", null=True, blank=True)
    class_name = models.CharField("班別", max_length=32, blank=True)
    seat_number = models.PositiveSmallIntegerField("座號", null=True, blank=True)
    email = models.EmailField("學生 Email", blank=True)
    home_phone = models.CharField("住家電話", max_length=32, blank=True)
    address = models.CharField("住址", max_length=255, blank=True)
    is_active = models.BooleanField("在學／啟用", default=True)
    created_at = models.DateTimeField("建立時間", auto_now_add=True)
    updated_at = models.DateTimeField("更新時間", auto_now=True)

    class Meta:
        verbose_name = "學生"
        verbose_name_plural = "學生"
        ordering = ["grade", "class_name", "seat_number", "full_name"]

    def clean(self):
        if self.date_of_birth and self.date_of_birth > date.today():
            raise ValidationError({"date_of_birth": "出生日期不可晚於今天。"})

    def __str__(self):
        return self.full_name


class Guardian(models.Model):
    class Relationship(models.TextChoices):
        LEGAL_GUARDIAN = "legal_guardian", "法定代理人"
        FATHER = "father", "父親"
        MOTHER = "mother", "母親"
        OTHER = "other", "其他"

    student = models.ForeignKey(Student, verbose_name="學生", on_delete=models.CASCADE, related_name="guardians")
    relationship = models.CharField("關係", max_length=24, choices=Relationship.choices, default=Relationship.LEGAL_GUARDIAN)
    full_name = models.CharField("姓名", max_length=100)
    phone_work = models.CharField("公司電話", max_length=32, blank=True)
    phone_mobile = models.CharField("手機", max_length=32, blank=True)
    email = models.EmailField("Email", blank=True)
    is_primary = models.BooleanField("主要聯絡人", default=False)

    class Meta:
        verbose_name = "法定代理人"
        verbose_name_plural = "法定代理人"
        constraints = [
            models.UniqueConstraint(
                fields=["student"],
                condition=Q(is_primary=True),
                name="one_primary_guardian_per_student",
            ),
        ]

    def __str__(self):
        return f"{self.student}－{self.full_name}"


class FamilyMember(models.Model):
    student = models.ForeignKey(Student, verbose_name="學生", on_delete=models.CASCADE, related_name="family_members")
    relationship = models.CharField("稱謂", max_length=32)
    full_name = models.CharField("姓名", max_length=100)
    organization_or_school = models.CharField("服務機關／就讀學校", max_length=150, blank=True)
    education_major = models.CharField("畢業科系", max_length=150, blank=True)
    specialty = models.CharField("專長", max_length=255, blank=True)
    phone = models.CharField("聯絡電話", max_length=32, blank=True)
    sort_order = models.PositiveSmallIntegerField("排序", default=0)

    class Meta:
        verbose_name = "家庭成員"
        verbose_name_plural = "家庭成員"
        ordering = ["sort_order", "id"]

    def __str__(self):
        return f"{self.student}－{self.relationship} {self.full_name}"


class Teacher(models.Model):
    full_name = models.CharField("教師姓名", max_length=150)
    account = models.OneToOneField(
        User,
        verbose_name="登入帳號",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="teacher_profile",
    )
    is_active = models.BooleanField("啟用", default=True)

    class Meta:
        verbose_name = "教師"
        verbose_name_plural = "教師"
        ordering = ["full_name", "id"]

    def __str__(self):
        return self.full_name


class StudentStaffAssignment(models.Model):
    class Role(models.TextChoices):
        CASE_MANAGER = "case_manager", "個管教師"
        COURSE_TEACHER = "course_teacher", "任課教師"
        HOMEROOM_TEACHER = "homeroom_teacher", "班級導師"
        VIEWER = "viewer", "閱覽者"

    student = models.ForeignKey(Student, verbose_name="學生", on_delete=models.CASCADE, related_name="staff_assignments")
    staff = models.ForeignKey(Teacher, verbose_name="教師／人員", on_delete=models.PROTECT, related_name="student_assignments")
    role = models.CharField("指派角色", max_length=24, choices=Role.choices)
    start_date = models.DateField("開始日期", default=timezone.localdate)
    end_date = models.DateField("結束日期", null=True, blank=True)
    is_active = models.BooleanField("啟用", default=True)

    class Meta:
        verbose_name = "學生教師指派"
        verbose_name_plural = "學生教師指派"
        constraints = [
            models.UniqueConstraint(
                fields=["student", "staff", "role", "start_date"],
                name="unique_student_staff_role_start_date",
            ),
            models.UniqueConstraint(
                fields=["student"],
                condition=Q(role="case_manager", is_active=True, end_date__isnull=True),
                name="one_current_case_manager_per_student",
            ),
        ]

    def clean(self):
        if self.end_date and self.end_date < self.start_date:
            raise ValidationError({"end_date": "結束日期不得早於開始日期。"})

    def __str__(self):
        return f"{self.student}－{self.staff}（{self.get_role_display()}）"

def private_document_upload_to(instance, filename):
    suffix = Path(filename).suffix.lower()
    return f"documents/{timezone.now():%Y/%m}/{uuid4().hex}{suffix}"


class ProgramDocument(models.Model):
    class DocumentType(models.TextChoices):
        IGP_PLAN = "igp_plan", "IGP 計畫"
        IGP_MEETING = "igp_meeting", "IGP 會議紀錄"
        COURSE_PLAN = "course_plan", "課程計畫"
        TIMETABLE = "timetable", "課表"

    public_id = models.UUIDField(default=uuid4, unique=True, editable=False)
    student = models.ForeignKey(
        "Student",
        verbose_name="學生",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="program_documents",
    )
    document_type = models.CharField("文件類型", max_length=24, choices=DocumentType.choices)
    title = models.CharField("文件標題", max_length=150)
    academic_year = models.CharField("學年度", max_length=16, blank=True)
    semester = models.PositiveSmallIntegerField("學期", null=True, blank=True)
    document_file = models.FileField("檔案", upload_to=private_document_upload_to, validators=[validate_program_document])
    original_filename = models.CharField("原始檔名", max_length=255, editable=False)
    uploaded_by = models.ForeignKey(User, verbose_name="上傳者", on_delete=models.SET_NULL, null=True, editable=False)
    uploaded_at = models.DateTimeField("上傳時間", auto_now_add=True)

    class Meta:
        verbose_name = "課程文件"
        verbose_name_plural = "課程文件"
        ordering = ["-uploaded_at"]

    def clean(self):
        super().clean()
        validate_program_document(self.document_file)
        if self.semester not in {None, 1, 2}:
            raise ValidationError({"semester": "學期只能是 1 或 2。"})

    def save(self, *args, **kwargs):
        if self.document_file and not self.original_filename:
            self.original_filename = Path(self.document_file.name).name
        return super().save(*args, **kwargs)

    def __str__(self):
        return self.title

class InitialIGPProfile(models.Model):
    student = models.OneToOneField(Student, verbose_name="學生", on_delete=models.CASCADE, related_name="initial_igp_profile")
    raw_response = models.JSONField("原始完整回覆", default=dict, editable=False)
    source_submitted_at = models.CharField("原始填表時間", max_length=64, blank=True)
    source_email = models.CharField("原始填表 Email", max_length=254, blank=True)
    additional_family_notes = models.TextField("其他家庭成員說明", blank=True)
    family_culture = models.TextField("家庭文化特質", blank=True)
    primary_caregiver = models.TextField("主要照顧者", blank=True)
    learning_supporter = models.TextField("主要協助學習者", blank=True)
    household_economy = models.TextField("家庭經濟狀況", blank=True)
    caregiving_style = models.TextField("照顧者管教態度", blank=True)
    family_interaction = models.TextField("與家人互動情形", blank=True)
    math_aptitude_score = models.CharField("數學性向測驗分數", max_length=64, blank=True)
    science_aptitude_score = models.CharField("自然性向測驗分數", max_length=64, blank=True)
    math_practical_t_score = models.CharField("數學實作評量 T 分數", max_length=64, blank=True)
    science_practical_t_score = models.CharField("自然實作評量 T 分數", max_length=64, blank=True)
    science_interests = models.TextField("科學興趣", blank=True)
    arts_interests = models.TextField("人文與藝術興趣", blank=True)
    other_interests = models.TextField("其他興趣", blank=True)
    other_awards_notes = models.TextField("其他得獎紀錄", blank=True)
    completed_by = models.CharField("填寫者", max_length=100, blank=True)
    cognitive_strengths = models.TextField("認知優勢特質", blank=True)
    emotional_strengths = models.TextField("情意優勢特質", blank=True)
    academic_strengths = models.TextField("學科優勢能力", blank=True)
    cognitive_needs = models.TextField("認知弱勢特質", blank=True)
    emotional_needs = models.TextField("情意弱勢特質", blank=True)
    academic_needs = models.TextField("學科弱勢能力", blank=True)
    notes = models.TextField("其他補充說明事項", blank=True)
    updated_at = models.DateTimeField("更新時間", auto_now=True)

    class Meta:
        verbose_name = "初始 IGP 概況"
        verbose_name_plural = "初始 IGP 概況"

    def __str__(self):
        return f"{self.student}－初始 IGP 概況"


class AwardRecord(models.Model):
    student = models.ForeignKey(Student, verbose_name="學生", on_delete=models.CASCADE, related_name="award_records")
    award_date = models.CharField("獲獎日期", max_length=64, blank=True)
    activity_name = models.CharField("競賽／活動名稱", max_length=255, blank=True)
    organizer = models.CharField("主辦單位", max_length=255, blank=True)
    award = models.CharField("獎項", max_length=255, blank=True)
    award_type = models.CharField("得獎類型", max_length=100, blank=True)

    class Meta:
        verbose_name = "得獎紀錄"
        verbose_name_plural = "得獎紀錄"

    def __str__(self):
        return f"{self.student}－{self.activity_name or '得獎紀錄'}"








class Assessment(models.Model):
    student = models.ForeignKey(Student, verbose_name="學生", on_delete=models.CASCADE, related_name="assessments")
    name = models.CharField("評量名稱", max_length=150)
    assessed_on = models.DateField("評量日期", null=True, blank=True)
    result = models.CharField("結果／分數", max_length=255, blank=True)
    notes = models.TextField("說明", blank=True)

    class Meta:
        verbose_name = "評量紀錄"
        verbose_name_plural = "評量紀錄"
        ordering = ["-assessed_on", "name"]

    def __str__(self):
        return f"{self.student}－{self.name}"


class AssessmentSubscale(models.Model):
    assessment = models.ForeignKey(
        Assessment,
        verbose_name="評量紀錄",
        on_delete=models.CASCADE,
        related_name="subscales",
    )
    name = models.CharField("分量表", max_length=150)
    score = models.CharField("分量成績", max_length=100)
    sort_order = models.PositiveSmallIntegerField("排序", default=0)

    class Meta:
        verbose_name = "評量分量表"
        verbose_name_plural = "評量分量表"
        ordering = ["sort_order", "id"]

    def __str__(self):
        return f"{self.assessment}－{self.name}"


class Interest(models.Model):
    student = models.ForeignKey(Student, verbose_name="學生", on_delete=models.CASCADE, related_name="interests")
    category = models.CharField("領域", max_length=100)
    detail = models.CharField("興趣內容", max_length=255)
    notes = models.TextField("補充說明", blank=True)

    class Meta:
        verbose_name = "興趣"
        verbose_name_plural = "興趣"
        ordering = ["category", "detail"]

    def __str__(self):
        return f"{self.student}－{self.detail}"


class IGPPlan(models.Model):
    student = models.ForeignKey(Student, verbose_name="學生", on_delete=models.CASCADE, related_name="igp_plans")
    academic_year = models.CharField("學年度", max_length=16)
    overall_goal = models.TextField("年度目標")
    notes = models.TextField("備註", blank=True)
    cognitive_strengths = models.TextField("認知優勢特質", blank=True)
    emotional_strengths = models.TextField("情意優勢特質", blank=True)
    academic_strengths = models.TextField("學科優勢能力", blank=True)
    cognitive_needs = models.TextField("認知弱勢特質", blank=True)
    emotional_needs = models.TextField("情意弱勢特質", blank=True)
    academic_needs = models.TextField("學科弱勢能力", blank=True)
    qualitative_analysis = models.TextField("優弱勢能力綜合評析（質性描述）", blank=True)
    strength_math_science = models.TextField("優勢－學習領域（數理）", blank=True)
    strength_language = models.TextField("優勢－學習領域（語文）", blank=True)
    weakness_analysis = models.TextField("劣勢", blank=True)
    affective_analysis = models.TextField("情意方面", blank=True)
    learning_strategies = models.TextField("學習策略", blank=True)

    class Meta:
        verbose_name = "IGP 年度計畫"
        verbose_name_plural = "IGP 年度計畫"
        ordering = ["-academic_year"]
        constraints = [models.UniqueConstraint(fields=["student", "academic_year"], name="unique_igp_plan_per_student_year")]

    def __str__(self):
        return f"{self.student}－{self.academic_year} IGP"


class SemesterPlan(models.Model):
    class Semester(models.IntegerChoices):
        FIRST = 1, "第一學期"
        SECOND = 2, "第二學期"

    igp_plan = models.ForeignKey(IGPPlan, verbose_name="IGP 年度計畫", on_delete=models.CASCADE, related_name="semester_plans")
    semester = models.PositiveSmallIntegerField("學期", choices=Semester.choices)
    school_name = models.CharField("就讀學校", max_length=150, default="平興國中")
    grade = models.PositiveSmallIntegerField("年級", null=True, blank=True)
    class_number = models.PositiveSmallIntegerField("班級", null=True, blank=True)
    course_needs_assessment = models.TextField("課程需求評估", blank=True)
    learning_domains = models.TextField("領域學習課程", blank=True)
    special_needs_courses = models.TextField("特殊需求課程", blank=True)
    goals = models.TextField("學期目標")
    strategies = models.TextField("執行策略", blank=True)

    class Meta:
        verbose_name = "學期計畫"
        verbose_name_plural = "學期計畫"
        ordering = ["igp_plan", "semester"]
        constraints = [models.UniqueConstraint(fields=["igp_plan", "semester"], name="unique_semester_plan_per_igp")]

    def __str__(self):
        return f"{self.igp_plan}－{self.get_semester_display()}"


class EducationTransitionRecord(models.Model):
    class Stage(models.TextChoices):
        GRADES_3_4 = "grades_3_4", "3-4年級"
        GRADES_5_6 = "grades_5_6", "5-6年級"
        JUNIOR_HIGH = "junior_high", "國中"

    student = models.ForeignKey(
        Student,
        verbose_name="學生",
        on_delete=models.CASCADE,
        related_name="education_transition_records",
    )
    stage = models.CharField("階段", max_length=24, choices=Stage.choices)
    school_name = models.CharField("校名", max_length=150, blank=True)
    class_name = models.CharField("班級", max_length=32, blank=True)
    homeroom_teacher = models.CharField("普通班導師", max_length=100, blank=True)
    gifted_case_manager = models.CharField("資優教育個管教師", max_length=100, blank=True)
    service_types = models.TextField("服務類型", blank=True)
    other_service = models.CharField("其他服務說明", max_length=255, blank=True)

    class Meta:
        verbose_name = "教育轉銜紀錄"
        verbose_name_plural = "教育轉銜紀錄"
        ordering = ["stage", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["student", "stage"],
                name="unique_education_transition_stage_per_student",
            ),
        ]

    def __str__(self):
        return f"{self.student}－{self.get_stage_display()}"


class IGPMeeting(models.Model):
    class MeetingType(models.TextChoices):
        INITIAL = "initial", "期初會議"
        FINAL = "final", "期末會議"

    igp_plan = models.ForeignKey(
        IGPPlan,
        verbose_name="IGP 年度計畫",
        on_delete=models.CASCADE,
        related_name="meetings",
    )
    semester = models.PositiveSmallIntegerField("學期", choices=SemesterPlan.Semester.choices)
    meeting_type = models.CharField("會議類型", max_length=16, choices=MeetingType.choices)
    meeting_date = models.DateField("會議日期")
    meeting_time = models.TimeField("時間", null=True, blank=True)
    location = models.CharField("地點", max_length=150, blank=True)
    recorder = models.CharField("記錄者", max_length=100, blank=True)
    attendees = models.TextField("與會人員／簽到", blank=True)
    minutes = models.TextField("會議紀錄", blank=True)

    class Meta:
        verbose_name = "IGP 會議紀錄"
        verbose_name_plural = "IGP 會議紀錄"
        ordering = ["-meeting_date", "-id"]

    def __str__(self):
        return f"{self.igp_plan}－{self.get_semester_display()} {self.get_meeting_type_display()}"


class PlacementReviewRecord(models.Model):
    student = models.ForeignKey(
        Student,
        verbose_name="學生",
        on_delete=models.CASCADE,
        related_name="placement_review_records",
    )
    recorded_on = models.DateField("日期", null=True, blank=True)
    needs_description = models.TextField("評估需求說明", blank=True)
    result_summary = models.TextField("評估結果概要敘述", blank=True)
    recorder = models.CharField("記錄人員", max_length=100, blank=True)

    class Meta:
        verbose_name = "重新安置紀錄"
        verbose_name_plural = "重新安置紀錄"
        ordering = ["recorded_on", "id"]

    def clean(self):
        super().clean()
        if not self.student_id:
            return
        existing = type(self).objects.filter(student_id=self.student_id).exclude(pk=self.pk)
        if existing.count() >= 2:
            raise ValidationError("每位學生最多只能建立 2 筆重新安置紀錄。")

    def __str__(self):
        return f"{self.student}－{self.recorded_on or '重新安置紀錄'}"


class CoursePlan(models.Model):
    semester_plan = models.ForeignKey(SemesterPlan, verbose_name="學期計畫", on_delete=models.CASCADE, related_name="course_plans")
    template = models.ForeignKey(
        "self",
        verbose_name="課程範本",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="student_plans",
    )
    is_template = models.BooleanField("課程範本", default=False)
    course_name = models.CharField("課程名稱", max_length=150)
    teacher = models.ForeignKey(Teacher, verbose_name="授課教師", on_delete=models.PROTECT, null=True, blank=True, related_name="course_plans")
    goals = models.TextField("課程目標")
    activities = models.TextField("學習活動／調整", blank=True)
    learning_domains = models.TextField("領域學習課程", blank=True)
    special_needs_courses = models.TextField("特殊需求課程", blank=True)
    cognitive_adjustments = models.TextField("認知教學方面", blank=True)
    affective_support = models.TextField("情意輔導方面", blank=True)
    skill_training = models.TextField("技能培訓方面", blank=True)
    is_active = models.BooleanField("目前修課", default=True)

    class Meta:
        verbose_name = "課程計畫"
        verbose_name_plural = "課程計畫"
        ordering = ["course_name"]

    def __str__(self):
        return f"{self.semester_plan}－{self.course_name}"


class LearningPerformance(models.Model):
    course_plan = models.ForeignKey(CoursePlan, verbose_name="課程計畫", on_delete=models.CASCADE, related_name="learning_performances")
    description = models.TextField("學習表現", blank=True)
    adjustment = models.TextField("學習表現調整", blank=True)
    assessment_methods = models.TextField("評量方式", blank=True)
    sort_order = models.PositiveSmallIntegerField("項次", default=0)

    def save(self, *args, **kwargs):
        if self._state.adding and not self.sort_order:
            last = type(self).objects.filter(course_plan_id=self.course_plan_id).aggregate(value=models.Max("sort_order"))["value"] or 0
            self.sort_order = last + 1
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "學習表現條目"
        verbose_name_plural = "學習表現條目"
        ordering = ["sort_order", "id"]

    def __str__(self):
        return f"{self.course_plan}－{self.sort_order}"


class LearningOutcomeRating(models.Model):
    class Rating(models.IntegerChoices):
        TRY_HARDER = 1, "○1 再努力"
        FAIR = 2, "○2 尚可"
        GOOD = 3, "○3 良好"
        EXCELLENT = 4, "○4 優異"

    learning_performance = models.OneToOneField(LearningPerformance, verbose_name="學習表現", on_delete=models.CASCADE, related_name="rating")
    rating = models.PositiveSmallIntegerField("教師評分", choices=Rating.choices)
    notes = models.TextField("評語", blank=True)
    updated_by = models.ForeignKey(User, verbose_name="評分教師帳號", on_delete=models.SET_NULL, null=True, blank=True)
    updated_at = models.DateTimeField("更新時間", auto_now=True)

    class Meta:
        verbose_name = "學習成果評分"
        verbose_name_plural = "學習成果評分"

    def __str__(self):
        return f"{self.learning_performance}－{self.get_rating_display()}"


class LearningOutcome(models.Model):
    course_plan = models.ForeignKey(CoursePlan, verbose_name="課程計畫", on_delete=models.CASCADE, related_name="learning_outcomes")
    recorded_on = models.DateField("記錄日期", default=timezone.localdate)
    outcome = models.TextField("學習成果")
    reflection = models.TextField("檢核與調整", blank=True)

    class Meta:
        verbose_name = "學習成果"
        verbose_name_plural = "學習成果"
        ordering = ["-recorded_on", "-id"]

    def __str__(self):
        return f"{self.course_plan}－{self.recorded_on}"


class CounselingRecord(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "草稿"
        SUBMITTED = "submitted", "已送審"
        RETURNED = "returned", "退回修正"
        REVIEWED = "reviewed", "已審核"
        LOCKED = "locked", "已鎖定"

    student = models.ForeignKey(Student, verbose_name="學生", on_delete=models.CASCADE, related_name="counseling_records")
    academic_year = models.CharField("學年度", max_length=16, blank=True)
    recorded_on = models.DateField("紀錄日期", default=timezone.localdate)
    participants = models.TextField("參與人員", blank=True)
    event = models.CharField("事件", max_length=150)
    summary = models.TextField("內容概要敘述")
    intervention = models.TextField("處遇方式", blank=True)
    author = models.ForeignKey(User, verbose_name="記錄人員", on_delete=models.PROTECT, related_name="authored_counseling_records")
    status = models.CharField("狀態", max_length=16, choices=Status.choices, default=Status.DRAFT)
    review_note = models.TextField("審核意見", blank=True)
    submitted_at = models.DateTimeField("送審時間", null=True, blank=True)
    reviewed_by = models.ForeignKey(User, verbose_name="審核者", on_delete=models.PROTECT, null=True, blank=True, related_name="reviewed_counseling_records")
    reviewed_at = models.DateTimeField("審核時間", null=True, blank=True)
    locked_by = models.ForeignKey(User, verbose_name="鎖定者", on_delete=models.PROTECT, null=True, blank=True, related_name="locked_counseling_records")
    locked_at = models.DateTimeField("鎖定時間", null=True, blank=True)
    created_at = models.DateTimeField("建立時間", auto_now_add=True)
    updated_at = models.DateTimeField("更新時間", auto_now=True)

    class Meta:
        verbose_name = "輔導紀錄"
        verbose_name_plural = "輔導紀錄"
        ordering = ["-recorded_on", "-id"]

    def __str__(self):
        return f"{self.student}－{self.recorded_on} {self.event}"


class AuditEvent(models.Model):
    class EventType(models.TextChoices):
        COUNSELING_CREATED = "counseling_created", "建立輔導紀錄"
        COUNSELING_SUBMITTED = "counseling_submitted", "送審輔導紀錄"
        COUNSELING_RETURNED = "counseling_returned", "退回輔導紀錄"
        COUNSELING_REVIEWED = "counseling_reviewed", "審核輔導紀錄"
        COUNSELING_LOCKED = "counseling_locked", "鎖定輔導紀錄"
        USER_PERMISSION_CHANGED = "user_permission_changed", "帳號權限變更"
        ASSIGNMENT_CHANGED = "assignment_changed", "學生教師指派變更"
        STUDENT_IMPORT_APPLIED = "student_import_applied", "匯入學生資料"
        DOCUMENT_UPLOADED = "document_uploaded", "上傳課程文件"
        DOCUMENT_DELETED = "document_deleted", "刪除課程文件"

    occurred_at = models.DateTimeField("發生時間", auto_now_add=True)
    actor = models.ForeignKey(User, verbose_name="操作者", on_delete=models.PROTECT, related_name="audit_events")
    event_type = models.CharField("事件類型", max_length=32, choices=EventType.choices)
    target_model = models.CharField("目標類型", max_length=100)
    target_pk = models.CharField("目標識別", max_length=64)
    summary = models.CharField("摘要", max_length=255, blank=True)

    class Meta:
        verbose_name = "稽核事件"
        verbose_name_plural = "稽核事件"
        ordering = ["-occurred_at", "-id"]

    def __str__(self):
        return f"{self.get_event_type_display()}－{self.occurred_at:%Y-%m-%d %H:%M}"
