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
    if user.is_superuser or user.role in STUDENT_DATA_MANAGER_ROLES:
        return visible_students_for(user)
    if user.role != User.Role.COURSE_TEACHER:
        return Student.objects.none()
    today = timezone.localdate()
    return Student.objects.filter(
        staff_assignments__staff__account=user,
        staff_assignments__role=StudentStaffAssignment.Role.COURSE_TEACHER,
        staff_assignments__is_active=True,
    ).filter(Q(staff_assignments__end_date__isnull=True) | Q(staff_assignments__end_date__gte=today)).distinct()


def can_manage_learning_outcomes(user, student=None):
    students = students_for_learning_outcomes(user)
    return students.exists() if student is None else students.filter(pk=student.pk).exists()
