import re
from pathlib import Path

from django import forms
from django.forms import inlineformset_factory
from django.db.models import Q
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from .models import CounselingRecord, CoursePlan, EducationTransitionRecord, IGPPlan, InitialIGPProfile, LearningPerformance, SemesterPlan, Student, StudentStaffAssignment, Teacher, User


def split_choices(value):
    if not value:
        return []
    return [item.strip() for item in re.split(r"[,、\n]", str(value)) if item.strip()]


class TagMultipleChoiceField(forms.MultipleChoiceField):
    def prepare_value(self, value):
        return split_choices(value) if isinstance(value, str) else value

    def clean(self, value):
        return "、".join(super().clean(value))


class StudentForm(forms.ModelForm):
    GIFTED_CATEGORIES = ("一般智能", "創造能力", "數理", "英語", "自然")
    gifted_categories = TagMultipleChoiceField(
        label="資優類別",
        required=False,
        choices=[(choice, choice) for choice in GIFTED_CATEGORIES],
        widget=forms.CheckboxSelectMultiple(attrs={"class": "tag-checkboxes"}),
    )

    class Meta:
        model = Student
        fields = "__all__"


class EducationTransitionRecordForm(forms.ModelForm):
    SERVICE_TYPES = (
        "縮短修業年限", "資優資源班", "校本資優教育方案", "區域資優教育方案",
        "身障巡迴輔導", "資優巡迴輔導", "身心障礙資源班", "其他",
    )
    service_types = TagMultipleChoiceField(
        label="服務類型",
        required=False,
        choices=[(choice, choice) for choice in SERVICE_TYPES],
        widget=forms.CheckboxSelectMultiple(attrs={"class": "tag-checkboxes"}),
    )

    class Meta:
        model = EducationTransitionRecord
        fields = "__all__"


class StudentImportForm(forms.Form):
    workbook = forms.FileField(label="Excel 基礎資料檔")

    def clean_workbook(self):
        workbook = self.cleaned_data["workbook"]
        if Path(workbook.name).suffix.lower() != ".xlsx":
            raise forms.ValidationError("請上傳 .xlsx 檔案。")
        if workbook.size > 10 * 1024 * 1024:
            raise forms.ValidationError("Excel 檔案不得超過 10 MB。")
        return workbook


class InitialIGPProfileForm(forms.ModelForm):
    FAMILY_CULTURE = ("一般生", "原住民", "新住民", "低收入戶", "僑生", "其他")
    CAREGIVERS = ("父親", "母親", "其他")
    ECONOMY = ("富裕", "小康", "普通", "清寒", "其他")
    CAREGIVING = ("民主式", "權威式", "放任式", "其他")
    INTERACTION = ("5", "4", "3", "2", "1")
    SCIENCE = ("數學", "生物", "物理", "化學", "地球科學", "天文", "地質", "資訊科技", "生活科技", "其他")
    ARTS = ("語文", "史地", "音樂", "美術", "設計", "工藝", "家政", "舞蹈", "戲劇", "電影", "閱讀", "其他")
    OTHER_INTERESTS = ("球類", "田徑", "游泳", "民俗體育", "武術", "棋藝", "牌藝", "廚藝", "登山", "旅遊", "手工藝", "飼養寵物", "其他")
    COGNITIVE = ("觀察能力", "記憶能力", "理解能力", "推理能力", "分析能力", "應用能力", "評鑑能力", "創造能力", "批判能力", "問題解決", "後設能力", "其他")
    EMOTIONAL = ("專注能力", "成就動機", "要求完美", "溝通協調", "情緒控制", "挫折容忍", "正向思考", "領導能力", "合作能力", "自信心", "同理心", "復原力", "其他")
    ACADEMIC = ("數學", "自然", "物理", "生物", "化學", "地科", "語文", "國文", "英文", "社會", "歷史", "地理", "公民", "資訊", "生科", "其他")

    @staticmethod
    def tag_field(label, choices):
        return TagMultipleChoiceField(
            label=label,
            required=False,
            choices=[(choice, choice) for choice in choices],
            widget=forms.CheckboxSelectMultiple(attrs={"class": "tag-checkboxes"}),
        )

    family_culture = tag_field.__func__("家庭文化特質", FAMILY_CULTURE)
    primary_caregiver = tag_field.__func__("主要照顧者", CAREGIVERS)
    learning_supporter = tag_field.__func__("主要協助學習者", CAREGIVERS)
    household_economy = tag_field.__func__("家庭經濟狀況", ECONOMY)
    caregiving_style = tag_field.__func__("照顧者管教態度", CAREGIVING)
    family_interaction = tag_field.__func__("與家人互動情形", INTERACTION)
    science_interests = tag_field.__func__("科學興趣", SCIENCE)
    arts_interests = tag_field.__func__("人文與藝術興趣", ARTS)
    other_interests = tag_field.__func__("其他興趣", OTHER_INTERESTS)
    cognitive_strengths = tag_field.__func__("認知優勢特質", COGNITIVE)
    cognitive_needs = tag_field.__func__("認知弱勢特質", COGNITIVE)
    emotional_strengths = tag_field.__func__("情意優勢特質", EMOTIONAL)
    emotional_needs = tag_field.__func__("情意弱勢特質", EMOTIONAL)
    academic_strengths = tag_field.__func__("學科優勢能力", ACADEMIC)
    academic_needs = tag_field.__func__("學科弱勢能力", ACADEMIC)

    class Meta:
        model = InitialIGPProfile
        fields = (
            "source_submitted_at", "source_email", "completed_by", "additional_family_notes",
            "family_culture", "primary_caregiver", "learning_supporter", "household_economy",
            "caregiving_style", "family_interaction", "math_aptitude_score", "science_aptitude_score",
            "math_practical_t_score", "science_practical_t_score", "science_interests", "arts_interests",
            "other_interests", "other_awards_notes", "cognitive_strengths", "emotional_strengths",
            "academic_strengths", "cognitive_needs", "emotional_needs", "academic_needs", "notes",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name in (
            "family_culture", "primary_caregiver", "learning_supporter", "household_economy",
            "caregiving_style", "family_interaction", "science_interests", "arts_interests", "other_interests",
            "cognitive_strengths", "emotional_strengths", "academic_strengths", "cognitive_needs",
            "emotional_needs", "academic_needs",
        ):
            selected = split_choices(getattr(self.instance, field_name, ""))
            known = {value for value, _ in self.fields[field_name].choices}
            self.fields[field_name].choices += [(value, value) for value in selected if value not in known]


class TeacherStudentAssignmentForm(forms.Form):
    assignment_fields = (
        (StudentStaffAssignment.Role.HOMEROOM_TEACHER, "homeroom_students"),
        (StudentStaffAssignment.Role.CASE_MANAGER, "case_manager_students"),
    )

    account = forms.ModelChoiceField(label="登入帳號", queryset=User.objects.none(), required=False, help_text="可先留空，建立帳號後再回來綁定。")
    homeroom_students = forms.ModelMultipleChoiceField(label="擔任班級導師的學生", queryset=Student.objects.none(), required=False, widget=forms.CheckboxSelectMultiple)
    case_manager_students = forms.ModelMultipleChoiceField(label="擔任個管教師的學生", queryset=Student.objects.none(), required=False, widget=forms.CheckboxSelectMultiple)


    def __init__(self, *args, teacher=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.teacher = teacher
        students = Student.objects.filter(is_active=True)
        for _, field_name in self.assignment_fields:
            self.fields[field_name].queryset = students
        accounts = User.objects.filter(is_active=True, is_approved=True)
        if teacher:
            accounts = accounts.filter(Q(teacher_profile__isnull=True) | Q(teacher_profile=teacher))
        self.fields["account"].queryset = accounts.order_by("email", "username")

    def clean_case_manager_students(self):
        students = self.cleaned_data["case_manager_students"]
        if not self.teacher:
            return students

        conflicts = StudentStaffAssignment.objects.filter(
            student__in=students,
            role=StudentStaffAssignment.Role.CASE_MANAGER,
            is_active=True,
            end_date__isnull=True,
        ).exclude(staff=self.teacher).select_related("student", "staff")
        if conflicts.exists():
            details = "；".join(
                f"{assignment.student.full_name} 已是 {assignment.staff.full_name} 的個案"
                for assignment in conflicts
            )
            raise forms.ValidationError(f"無法指派個管教師：{details}。請先解除原個管指派。")
        return students


class TeacherCreateForm(forms.ModelForm):
    class Meta:
        model = Teacher
        fields = ("full_name", "account")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["account"].queryset = User.objects.filter(
            is_active=True, is_approved=True, teacher_profile__isnull=True
        ).order_by("email", "username")
        self.fields["account"].required = False
        self.fields["account"].help_text = "可先留空，之後也可在教師指派頁面媒合。"


class BulkIGPPlanForm(forms.Form):
    students = forms.ModelMultipleChoiceField(label="Students", queryset=Student.objects.none(), widget=forms.CheckboxSelectMultiple)
    academic_year = forms.CharField(label="Academic year", max_length=16)
    overall_goal = forms.CharField(label="Annual goal", widget=forms.Textarea)
    notes = forms.CharField(label="Notes", required=False, widget=forms.Textarea)

    def __init__(self, *args, students=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["students"].queryset = students if students is not None else Student.objects.filter(is_active=True)


class BulkSemesterPlanForm(forms.Form):
    plans = forms.ModelMultipleChoiceField(label="IGP plans", queryset=IGPPlan.objects.none(), widget=forms.CheckboxSelectMultiple)
    semester = forms.TypedChoiceField(label="Semester", choices=SemesterPlan.Semester.choices, coerce=int)
    goals = forms.CharField(label="Semester goals", widget=forms.Textarea)
    strategies = forms.CharField(label="Strategies", required=False, widget=forms.Textarea)

    def __init__(self, *args, plans=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["plans"].queryset = plans if plans is not None else IGPPlan.objects.none()


class CopySemesterPlanForm(forms.Form):
    students = forms.ModelMultipleChoiceField(label="Target students", queryset=Student.objects.none(), widget=forms.CheckboxSelectMultiple)
    academic_year = forms.CharField(label="Target academic year", max_length=16)

    def __init__(self, *args, students=None, academic_year="", **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["students"].queryset = students if students is not None else Student.objects.filter(is_active=True)
        self.fields["academic_year"].initial = academic_year


class IGPPlanForm(forms.ModelForm):
    cognitive_strengths = InitialIGPProfileForm.tag_field("認知優勢特質", InitialIGPProfileForm.COGNITIVE)
    emotional_strengths = InitialIGPProfileForm.tag_field("情意優勢特質", InitialIGPProfileForm.EMOTIONAL)
    academic_strengths = InitialIGPProfileForm.tag_field("學科優勢能力", InitialIGPProfileForm.ACADEMIC)
    cognitive_needs = InitialIGPProfileForm.tag_field("認知弱勢特質", InitialIGPProfileForm.COGNITIVE)
    emotional_needs = InitialIGPProfileForm.tag_field("情意弱勢特質", InitialIGPProfileForm.EMOTIONAL)
    academic_needs = InitialIGPProfileForm.tag_field("學科弱勢能力", InitialIGPProfileForm.ACADEMIC)

    class Meta:
        model = IGPPlan
        fields = "__all__"


class ParentChildCheckboxSelectMultiple(forms.CheckboxSelectMultiple):
    def __init__(self, groups, *args, **kwargs):
        self.groups = groups
        choices = [choice for _, children in groups for choice in children]
        super().__init__(choices=choices, *args, **kwargs)

    def render(self, name, value, attrs=None, renderer=None):
        selected = set(value or [])
        base_id = (attrs or {}).get("id", f"id_{name}")
        groups = []
        for index, (parent, children) in enumerate(self.groups):
            child_widget = forms.CheckboxSelectMultiple(choices=children)
            child_html = child_widget.render(name, list(selected), {"id": f"{base_id}_{index}"}, renderer)
            groups.append(format_html(
                '<fieldset class="parent-child-group"><label class="parent-choice"><input type="checkbox" data-parent-checkbox> {}</label><div class="child-choices">{}</div></fieldset>',
                parent, mark_safe(child_html),
            ))
        return mark_safe('<div class="parent-child-choices">' + ''.join(groups) + '</div>')


class ParentChildChoiceField(TagMultipleChoiceField):
    def __init__(self, label, groups):
        groups = tuple((parent, tuple((choice, choice) for choice in children)) for parent, children in groups)
        super().__init__(
            label=label,
            required=False,
            choices=[choice for _, children in groups for choice in children],
            widget=ParentChildCheckboxSelectMultiple(groups, attrs={"class": "tag-checkboxes"}),
        )


class CoursePlanForm(forms.ModelForm):
    DOMAINS = ("國語文", "英語文", "第二外國語文", "數學領域", "社會領域", "自然科學領域", "藝術領域", "綜合活動領域", "科技領域", "健康與體育領域")
    SPECIAL = ("創造能力", "領導才能", "獨立研究", "情意發展", "專長領域", "生活管理", "社會技巧", "學習策略", "職業教育", "定向行動", "點字", "溝通訓練", "功能性動作訓練", "輔助科技應用")
    COGNITIVE = ("內容調整：加深加廣", "內容調整：獨立研究", "內容調整：濃縮加速／縮短修業", "歷程調整：思考訓練", "歷程調整：研究方法訓練", "歷程調整：學習策略訓練", "結果調整：作業調整", "結果調整：評量調整", "結果調整：成果分享", "環境調整：自學空間", "環境調整：校外學習", "環境調整：校外交流")
    AFFECTIVE = ("輔導重點：情意技能", "輔導重點：親子互動", "輔導重點：同儂互動", "輔導重點：情緒調適", "輔導重點：壓力調適", "輔導重點：自我認識", "輔導重點：學習動機", "輔導重點：生涯規劃", "輔導方式：融入學科", "輔導方式：團體輔導", "輔導方式：小組輔導", "輔導方式：個別輔導", "輔導方式：親職教育")
    SKILLS = ("培訓重點：生活技能", "培訓重點：學習技能", "培訓重點：時間管理", "培訓重點：自我管理", "培訓方式：融入學科", "培訓方式：團體訓練", "培訓方式：小組訓練", "培訓方式：個別訓練")

    learning_domains = InitialIGPProfileForm.tag_field("領域學習課程", DOMAINS)
    special_needs_courses = InitialIGPProfileForm.tag_field("特殊需求課程", SPECIAL)
    cognitive_adjustments = ParentChildChoiceField("認知教學方面", (
        ("內容調整", tuple(item.split("：", 1)[1] for item in COGNITIVE if item.startswith("內容調整"))),
        ("歷程調整", tuple(item.split("：", 1)[1] for item in COGNITIVE if item.startswith("歷程調整"))),
        ("結果調整", tuple(item.split("：", 1)[1] for item in COGNITIVE if item.startswith("結果調整"))),
        ("環境調整", tuple(item.split("：", 1)[1] for item in COGNITIVE if item.startswith("環境調整"))),
    ))
    affective_support = ParentChildChoiceField("情意輔導方面", (
        ("輔導重點", tuple(item.split("：", 1)[1] for item in AFFECTIVE if item.startswith("輔導重點"))),
        ("輔導方式", tuple(item.split("：", 1)[1] for item in AFFECTIVE if item.startswith("輔導方式"))),
    ))
    skill_training = ParentChildChoiceField("技能培訓方面", (
        ("培訓重點", tuple(item.split("：", 1)[1] for item in SKILLS if item.startswith("培訓重點"))),
        ("培訓方式", tuple(item.split("：", 1)[1] for item in SKILLS if item.startswith("培訓方式"))),
    ))

    class Meta:
        model = CoursePlan
        exclude = ("activities", "is_active", "template", "is_template")


class CourseGroupForm(CoursePlanForm):
    academic_year = forms.CharField(label="學年度", max_length=16)
    semester = forms.TypedChoiceField(label="學期", choices=SemesterPlan.Semester.choices, coerce=int)
    students = forms.ModelMultipleChoiceField(
        label="上課學生",
        queryset=Student.objects.none(),
        widget=forms.CheckboxSelectMultiple,
    )

    class Meta:
        model = CoursePlan
        fields = (
            "course_name", "teacher", "goals", "learning_domains",
            "special_needs_courses", "cognitive_adjustments", "affective_support", "skill_training",
        )

    def __init__(self, *args, students=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["students"].queryset = students if students is not None else Student.objects.filter(is_active=True)


class CollapsibleCheckboxSelectMultiple(forms.CheckboxSelectMultiple):
    def render(self, name, value, attrs=None, renderer=None):
        checkboxes = super().render(name, value, attrs, renderer)
        return format_html("<details><summary>選擇評量方式</summary>{}</details>", mark_safe(checkboxes))


class LearningPerformanceForm(forms.ModelForm):
    METHODS = ("紙筆評量", "口語評量", "實作評量", "作業評量", "觀察評量", "檔案評量", "同儂評量", "學生自評")
    assessment_methods = TagMultipleChoiceField(
        label="評量方式", required=False,
        choices=[(choice, choice) for choice in METHODS],
        widget=CollapsibleCheckboxSelectMultiple(attrs={"class": "tag-checkboxes"}),
    )

    class Meta:
        model = LearningPerformance
        fields = "__all__"


CourseLearningPerformanceFormSet = inlineformset_factory(
    CoursePlan,
    LearningPerformance,
    form=LearningPerformanceForm,
    fields=("description", "adjustment", "assessment_methods"),
    extra=1,
    can_delete=False,
)


class SemesterPlanForm(forms.ModelForm):
    learning_domains = InitialIGPProfileForm.tag_field("領域學習課程", CoursePlanForm.DOMAINS)
    special_needs_courses = InitialIGPProfileForm.tag_field("特殊需求課程", CoursePlanForm.SPECIAL)

    class Meta:
        model = SemesterPlan
        fields = "__all__"


class CopyCoursePlanForm(CopySemesterPlanForm):
    semester = forms.TypedChoiceField(label="Target semester", choices=SemesterPlan.Semester.choices, coerce=int)

    def __init__(self, *args, semester=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["semester"].initial = semester
class CounselingRecordForm(forms.ModelForm):
    PARTICIPANTS = ("本人", "家長", "原班導師", "個管老師", "資優任課")
    INTERVENTIONS = ("轉介二級", "協同導師", "定期晤談", "持續觀察")
    participants = TagMultipleChoiceField(
        label="參與人員",
        required=False,
        choices=[(choice, choice) for choice in PARTICIPANTS],
        widget=forms.CheckboxSelectMultiple,
    )
    participants_other = forms.CharField(label="其他參與人員", max_length=150, required=False)
    intervention = TagMultipleChoiceField(
        label="處遇方式",
        required=False,
        choices=[(choice, choice) for choice in INTERVENTIONS],
        widget=forms.CheckboxSelectMultiple,
    )
    intervention_other = forms.CharField(label="其他處遇方式", max_length=150, required=False)

    class Meta:
        model = CounselingRecord
        fields = ("student", "academic_year", "recorded_on", "participants", "event", "summary", "intervention", "review_note")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        values = split_choices(self.instance.participants if self.instance.pk else self.initial.get("participants", ""))
        selected = [value for value in values if value in self.PARTICIPANTS]
        other_values = [value.removeprefix("其他：") for value in values if value not in self.PARTICIPANTS]
        if other_values:
            self.initial["participants_other"] = "、".join(other_values)
        self.initial["participants"] = selected

        intervention_values = split_choices(self.instance.intervention if self.instance.pk else self.initial.get("intervention", ""))
        selected_interventions = [value for value in intervention_values if value in self.INTERVENTIONS]
        other_interventions = [value.removeprefix("其他：") for value in intervention_values if value not in self.INTERVENTIONS]
        if other_interventions:
            self.initial["intervention_other"] = "、".join(other_interventions)
        self.initial["intervention"] = selected_interventions

    def clean(self):
        cleaned_data = super().clean()
        participants = split_choices(cleaned_data.get("participants", ""))
        participants_other = cleaned_data.get("participants_other", "").strip()
        if participants_other:
            participants.append(f"其他：{participants_other}")
        cleaned_data["participants"] = "、".join(participants)

        interventions = split_choices(cleaned_data.get("intervention", ""))
        intervention_other = cleaned_data.get("intervention_other", "").strip()
        if intervention_other:
            interventions.append(f"其他：{intervention_other}")
        cleaned_data["intervention"] = "、".join(interventions)
        return cleaned_data
