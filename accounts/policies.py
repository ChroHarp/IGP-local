from django.db.models import Q
from django.utils import timezone

from .models import Student, StudentStaffAssignment, User


STUDENT_DATA_MANAGER_ROLES = {
    User.Role.SPECIAL_EDUCATION_LEAD,
    User.Role.CASE_MANAGER,
}


def approved_google_user_for_email(email: str) -> User | None:
    normalized_email = email.strip()
    if not normalized_email:
        return None
    return (
        User.objects.filter(
            email__iexact=normalized_email,
            is_active=True,
            is_approved=True,
        )
        .order_by("id")
        .first()
    )


def can_manage_accounts(user) -> bool:
    return bool(
        user.is_authenticated
        and (
            user.is_superuser
            or user.role in {User.Role.SYSTEM_ADMIN, User.Role.SPECIAL_EDUCATION_LEAD}
        )
    )


def can_manage_school_settings(user) -> bool:
    return bool(user.is_authenticated and (user.is_superuser or user.role == User.Role.SPECIAL_EDUCATION_LEAD))


def visible_students_for(user):
    if not user.is_authenticated:
        return Student.objects.none()
    if user.is_superuser or user.role == User.Role.SPECIAL_EDUCATION_LEAD:
        return Student.objects.all()
    today = timezone.localdate()
    return Student.objects.filter(
        staff_assignments__staff__account=user,
        staff_assignments__role=StudentStaffAssignment.Role.CASE_MANAGER,
        staff_assignments__is_active=True,
    ).filter(Q(staff_assignments__end_date__isnull=True) | Q(staff_assignments__end_date__gte=today)).distinct()


def can_view_student(user, student=None) -> bool:
    if not user.is_authenticated:
        return False
    if student is None:
        return user.is_superuser or user.role in STUDENT_DATA_MANAGER_ROLES or StudentStaffAssignment.objects.filter(staff__account=user, role=StudentStaffAssignment.Role.CASE_MANAGER, is_active=True).exists()
    return visible_students_for(user).filter(pk=student.pk).exists()


def can_edit_student(user, student=None) -> bool:
    return can_view_student(user, student)


def can_add_student(user) -> bool:
    return can_manage_school_settings(user)

def can_view_program_documents(user) -> bool:
    return bool(
        user.is_authenticated
        and (
            user.is_superuser
            or user.role
            in {
                User.Role.SPECIAL_EDUCATION_LEAD,
                User.Role.CASE_MANAGER,
                User.Role.COURSE_TEACHER,
                User.Role.HOMEROOM_TEACHER,
            }
        )
    )


def can_manage_program_documents(user) -> bool:
    return can_manage_school_settings(user)





def students_for_learning_outcomes(user):
    if not user.is_authenticated:
        return Student.objects.none()
    if user.is_superuser or user.role == User.Role.SPECIAL_EDUCATION_LEAD:
        return visible_students_for(user)
    return Student.objects.filter(
        igp_plans__semester_plans__course_plans__teacher__account=user,
        igp_plans__semester_plans__course_plans__is_active=True,
    ).distinct()


def can_view_learning_outcomes(user, student=None):
    if not user.is_authenticated:
        return False
    students = Student.objects.filter(
        Q(pk__in=visible_students_for(user)) | Q(pk__in=students_for_learning_outcomes(user))
    ).distinct()
    return students.exists() if student is None else students.filter(pk=student.pk).exists()


def can_manage_learning_outcomes(user, student=None):
    students = students_for_learning_outcomes(user)
    return students.exists() if student is None else students.filter(pk=student.pk).exists()


def taught_students_for(user):
    if not user.is_authenticated:
        return Student.objects.none()
    return Student.objects.filter(
        igp_plans__semester_plans__course_plans__teacher__account=user,
        igp_plans__semester_plans__course_plans__is_active=True,
        igp_plans__semester_plans__course_plans__is_template=False,
    ).distinct()


def students_for_course_plans(user):
    if not user.is_authenticated:
        return Student.objects.none()
    return Student.objects.filter(
        Q(pk__in=visible_students_for(user)) | Q(pk__in=taught_students_for(user))
    ).distinct()


def students_for_counseling_records(user):
    if not user.is_authenticated:
        return Student.objects.none()
    if user.is_superuser or user.role == User.Role.SPECIAL_EDUCATION_LEAD:
        return Student.objects.all()
    today = timezone.localdate()
    return Student.objects.filter(
        staff_assignments__staff__account=user,
        staff_assignments__role__in=(
            StudentStaffAssignment.Role.CASE_MANAGER,
            StudentStaffAssignment.Role.HOMEROOM_TEACHER,
        ),
        staff_assignments__is_active=True,
    ).filter(
        Q(staff_assignments__end_date__isnull=True) | Q(staff_assignments__end_date__gte=today)
    ).distinct()

def students_for_counseling_authoring(user):
    if not user.is_authenticated:
        return Student.objects.none()
    return Student.objects.filter(
        Q(pk__in=students_for_counseling_records(user)) | Q(pk__in=taught_students_for(user))
    ).distinct()


def counseling_records_for(user):
    from .models import CounselingRecord

    if not user.is_authenticated:
        return CounselingRecord.objects.none()
    if user.is_superuser or user.role == User.Role.SPECIAL_EDUCATION_LEAD:
        return CounselingRecord.objects.all()
    return CounselingRecord.objects.filter(
        Q(student__in=students_for_counseling_records(user)) | Q(author=user)
    ).distinct()


def students_for_counseling_index(user):
    if not user.is_authenticated:
        return Student.objects.none()
    return Student.objects.filter(
        Q(pk__in=students_for_counseling_authoring(user))
        | Q(counseling_records__in=counseling_records_for(user))
    ).distinct()

def can_view_counseling_records(user, student=None):
    records = counseling_records_for(user)
    return records.exists() if student is None else records.filter(student=student).exists()


def can_add_counseling_record(user, student=None):
    if not user.is_authenticated:
        return False
    if user.is_superuser or user.role == User.Role.SPECIAL_EDUCATION_LEAD:
        return True
    students = students_for_counseling_authoring(user)
    return students.exists() if student is None else students.filter(pk=student.pk).exists()

def can_review_counseling_records(user):
    return bool(user.is_authenticated and (user.is_superuser or user.role == User.Role.SPECIAL_EDUCATION_LEAD))


def can_edit_counseling_record(user, record):
    return bool(
        user.is_authenticated
        and record.author_id == user.pk
        and record.status in {record.Status.DRAFT, record.Status.RETURNED}
        and can_add_counseling_record(user, record.student)
    )
