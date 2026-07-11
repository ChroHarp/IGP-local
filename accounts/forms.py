import re
from pathlib import Path

from django import forms
from django.db.models import Q

from .models import InitialIGPProfile, Student, StudentStaffAssignment, Teacher, User


def split_choices(value):
    if not value:
        return []
    return [item.strip() for item in re.split(r"[,、\n]", str(value)) if item.strip()]


class TagMultipleChoiceField(forms.MultipleChoiceField):
    def prepare_value(self, value):
        return split_choices(value) if isinstance(value, str) else value

    def clean(self, value):
        return "、".join(super().clean(value))


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
        (StudentStaffAssignment.Role.COURSE_TEACHER, "course_students"),
    )

    account = forms.ModelChoiceField(label="登入帳號", queryset=User.objects.none(), required=False, help_text="可先留空，建立帳號後再回來綁定。")
    homeroom_students = forms.ModelMultipleChoiceField(label="擔任班級導師的學生", queryset=Student.objects.none(), required=False, widget=forms.CheckboxSelectMultiple)
    case_manager_students = forms.ModelMultipleChoiceField(label="擔任個管教師的學生", queryset=Student.objects.none(), required=False, widget=forms.CheckboxSelectMultiple)
    course_students = forms.ModelMultipleChoiceField(label="擔任任課教師的學生", queryset=Student.objects.none(), required=False, widget=forms.CheckboxSelectMultiple)

    def __init__(self, *args, teacher=None, **kwargs):
        super().__init__(*args, **kwargs)
        students = Student.objects.filter(is_active=True)
        for _, field_name in self.assignment_fields:
            self.fields[field_name].queryset = students
        accounts = User.objects.filter(is_active=True, is_approved=True)
        if teacher:
            accounts = accounts.filter(Q(teacher_profile__isnull=True) | Q(teacher_profile=teacher))
        self.fields["account"].queryset = accounts.order_by("email", "username")


class TeacherCreateForm(forms.ModelForm):
    class Meta:
        model = Teacher
        fields = ("full_name",)
