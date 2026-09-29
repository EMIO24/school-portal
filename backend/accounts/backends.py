"""School-scoped student name authentication alongside Django email login."""
from django.contrib.auth import get_user_model
from django.contrib.auth.backends import BaseBackend


def normalize_student_name(value):
    return " ".join(value.split()).casefold()


class StudentNameBackend(BaseBackend):
    def authenticate(self, request, student_name=None, password=None, admission_number="", **kwargs):
        if student_name is None or password is None:
            return None
        User = get_user_model()
        school = getattr(request, "tenant", None)
        matches = []
        if school and school.is_active and school.approval_status == "approved":
            students = User.objects.filter(
                school=school, role="student", is_active=True,
                student_profile__school=school, student_profile__status="active",
            )
            if admission_number:
                students = students.filter(student_profile__admission_number__iexact=admission_number.strip())
            name = normalize_student_name(student_name)
            for pk, first, last in students.values_list("pk", "first_name", "last_name").iterator():
                if normalize_student_name(f"{first} {last}") == name:
                    matches.append(pk)
                    if len(matches) > 1:
                        break
        if len(matches) != 1:
            # Same password-hashing work as an unsuccessful Django login.
            User().set_password(password)
            return None
        user = User.objects.get(pk=matches[0])
        if user.check_password(password) and user.is_active:
            return user
        return None

    def get_user(self, user_id):
        return get_user_model().objects.filter(pk=user_id, is_active=True).first()
