from rest_framework.permissions import IsAuthenticated


class StudentOnlyMixin:
    permission_classes = [IsAuthenticated]
    role_required = ["student"]

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if request.user.role not in self.role_required and request.user.role != "admin":
            self.permission_denied(
                request,
                message="Student access only"
            )


class InstructorOnlyMixin:
    permission_classes = [IsAuthenticated]
    role_required = ["instructor"]

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if request.user.role not in self.role_required and request.user.role != "admin":
            self.permission_denied(
                request,
                message="Instructor access only"
            )


class AdminOnlyMixin:
    permission_classes = [IsAuthenticated]
    role_required = ["admin"]

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if request.user.role != "admin":
            self.permission_denied(
                request,
                message="Admin access only"
            )
