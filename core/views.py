from django.conf import settings
from django.shortcuts import redirect, render
from django.views.decorators.csp import csp_override

from .auth import cookie_login_required, page_user
from accounts.utils import is_platform_admin

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

# ---------------------------------------------------------------------------
# Authenticated pages (gated server-side via the JWT auth cookie)
# ---------------------------------------------------------------------------

@cookie_login_required
def student_dashboard(request):
    """Student dashboard"""
    if page_user(request).role == 'instructor':
        return redirect('instructor_dashboard')
    return render(request, 'dashboard/student.html')

@cookie_login_required(role='instructor')
def instructor_dashboard(request):
    """Instructor dashboard"""
    return render(request, 'dashboard/instructor.html')

@cookie_login_required
def profile_page(request):
    """Student profile page"""
    user = page_user(request)
    if user.role == 'instructor' or is_platform_admin(user):
        return redirect('instructor_profile_page')
    return render(request, 'profile/student-profile.html')

@cookie_login_required(role='instructor')
def instructor_profile_page(request):
    """Instructor profile page"""
    return render(request, 'profile/instructor-profile.html')

@cookie_login_required
def settings_page(request):
    """Settings page"""
    return render(request, 'profile/settings.html')

@cookie_login_required(role='instructor')
def instructor_courses_list(request):
    """Instructor courses list page"""
    return render(request, 'instructor/courses-list.html')

@cookie_login_required(role='instructor')
def instructor_course_create(request):
    """Instructor course creation page"""
    return render(request, 'instructor/course-create.html')

@cookie_login_required(role='instructor')
def instructor_course_content(request, slug):
    """Instructor course content management page"""
    return render(request, 'instructor/course-content.html')

@cookie_login_required(role='instructor')
def instructor_course_edit(request, slug):
    """Instructor course edit page"""
    return render(request, 'instructor/course-edit.html')

@cookie_login_required(role='instructor')
def instructor_lesson_edit(request, id):
    """Instructor lesson content editor page"""
    return render(request, 'instructor/lesson-editor.html')

@cookie_login_required(role='instructor')
def instructor_course_preview(request, slug):
    """Instructor course preview page"""
    return render(request, 'instructor/course-preview.html')

@cookie_login_required(role='instructor')
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
    user = page_user(request)
    if user.role == 'instructor':
        return redirect('instructor_dashboard')
    if is_platform_admin(user):
        return redirect('student_dashboard')
    return render(request, 'student/enrollments.html')

@cookie_login_required
@csp_override({
    **settings.SECURE_CSP,
    'script-src': [
        *settings.SECURE_CSP['script-src'],
        'https://www.youtube.com/iframe_api',
        'https://www.youtube.com/s/player/',
        'https://player.vimeo.com/api/player.js',
    ],
})
def learn_course(request, slug):
    """Student course learning interface"""
    return render(request, 'students/learn.html')

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

@cookie_login_required(role='instructor')
def exam_create(request):
    """Exam creation page"""
    return render(request, 'exams/create.html')



@cookie_login_required(role='student')
def learning_library(request):
    return render(request, 'students/library.html')


@cookie_login_required
def api_keys_page(request):
    return render(request, 'profile/api-keys.html')


@cookie_login_required
def refunds_page(request):
    return render(request, 'payments/refunds.html')


@cookie_login_required(role='instructor')
def payouts_page(request):
    return render(request, 'payments/payouts.html', {
        'payout_details_configured': bool(settings.PAYOUT_DETAILS_ENCRYPTION_KEY),
    })


@cookie_login_required
def payment_receipt(request, payment_id):
    from django.shortcuts import get_object_or_404
    from django.views.decorators.cache import add_never_cache_headers
    from payments.models import Payment
    from payments.services import SETTLED_PAYMENT_STATUSES, with_payment_refunds

    payment = get_object_or_404(
        with_payment_refunds(Payment.objects.select_related('course')),
        pk=payment_id, user=page_user(request), status__in=SETTLED_PAYMENT_STATUSES,
        purpose=Payment.PURPOSE_COURSE_PURCHASE,
    )
    response = render(request, 'payments/receipt.html', {'payment': payment})
    add_never_cache_headers(response)
    return response
