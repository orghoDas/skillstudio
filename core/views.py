from django.shortcuts import render

from .auth import cookie_login_required

# ---------------------------------------------------------------------------
# Public pages (no auth required)
# ---------------------------------------------------------------------------

def home(request):
    """Landing page"""
    return render(request, 'home.html')

def login_page(request):
    """Login page"""
    return render(request, 'auth/login.html')

def register_page(request):
    """Registration page"""
    return render(request, 'auth/register.html')

def courses_list(request):
    """Course listing page"""
    return render(request, 'courses/list.html')

def course_detail(request, slug):
    """Course detail page"""
    return render(request, 'courses/detail.html')

def search_results(request):
    """Search results page"""
    return render(request, 'search/results.html')

def browse_courses(request):
    """Browse courses by category page"""
    return render(request, 'search/browse.html')

def ai_recommendations(request):
    """AI-powered course recommendations"""
    # AI recommender removed — redirect users to course browsing instead
    return render(request, 'search/browse.html')

# ---------------------------------------------------------------------------
# Authenticated pages (gated server-side via the JWT auth cookie)
# ---------------------------------------------------------------------------

@cookie_login_required
def student_dashboard(request):
    """Student dashboard"""
    return render(request, 'dashboard/student.html')

@cookie_login_required
def instructor_dashboard(request):
    """Instructor dashboard"""
    return render(request, 'dashboard/instructor.html')

@cookie_login_required
def profile_page(request):
    """Student profile page"""
    return render(request, 'profile/student-profile.html')

@cookie_login_required
def instructor_profile_page(request):
    """Instructor profile page"""
    return render(request, 'profile/instructor-profile.html')

@cookie_login_required
def settings_page(request):
    """Settings page"""
    return render(request, 'profile/settings.html')

@cookie_login_required
def assessments_list(request):
    """Assessments listing page"""
    return render(request, 'assessments/list.html')

@cookie_login_required
def assessment_attempt(request, assessment_id, attempt_id=None):
    """Assessment attempt page"""
    return render(request, 'assessments/attempt.html')

@cookie_login_required
def assessment_results(request, assessment_id, attempt_id):
    """Assessment results page"""
    return render(request, 'assessments/results.html')

@cookie_login_required
def instructor_courses_list(request):
    """Instructor courses list page"""
    return render(request, 'instructor/courses-list.html')

@cookie_login_required
def instructor_course_create(request):
    """Instructor course creation page"""
    return render(request, 'instructor/course-create.html')

@cookie_login_required
def instructor_course_content(request, slug):
    """Instructor course content management page"""
    return render(request, 'instructor/course-content.html')

@cookie_login_required
def instructor_course_edit(request, slug):
    """Instructor course edit page"""
    return render(request, 'instructor/course-edit.html')

@cookie_login_required
def instructor_lesson_edit(request, id):
    """Instructor lesson content editor page"""
    return render(request, 'instructor/lesson-editor.html')

@cookie_login_required
def instructor_course_preview(request, slug):
    """Instructor course preview page"""
    return render(request, 'instructor/course-preview.html')

@cookie_login_required
def instructor_students(request):
    """Instructor students list page"""
    return render(request, 'instructor/students-list.html')

@cookie_login_required
def my_courses(request):
    """Student's enrolled courses page"""
    return render(request, 'students/my-courses.html')

@cookie_login_required
def enrollments_list(request):
    """Student's enrollments page"""
    return render(request, 'student/enrollments.html')

@cookie_login_required
def learn_course(request, slug):
    """Student course learning interface"""
    return render(request, 'students/learn.html')

@cookie_login_required
def checkout(request):
    """Payment checkout page"""
    return render(request, 'payments/checkout.html')

@cookie_login_required
def certificates_list(request):
    """User certificates list page"""
    return render(request, 'certificates/list.html')

@cookie_login_required
def payment_history(request):
    """Payment history and transactions page"""
    return render(request, 'payments/history.html')

@cookie_login_required
def wallet_page(request):
    """Student wallet page"""
    return render(request, 'student/wallet.html')

@cookie_login_required
def exams_list(request):
    """Exams list page"""
    return render(request, 'exams/list.html')

@cookie_login_required
def exam_take(request, exam_id):
    """Exam taking page"""
    return render(request, 'exams/take.html')

@cookie_login_required
def exam_results(request, exam_id):
    """Exam results page"""
    return render(request, 'exams/results.html')

@cookie_login_required
def exam_create(request):
    """Exam creation page"""
    return render(request, 'exams/create.html')

@cookie_login_required
def course_resources(request, course_id):
    """Student course resources view"""
    return render(request, 'courses/resources.html')

@cookie_login_required
def instructor_resources(request):
    """Instructor resource management"""
    return render(request, 'instructor/resources.html')
