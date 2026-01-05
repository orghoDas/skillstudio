from django.shortcuts import render

# Create your views here.

def home(request):
    """Landing page"""
    return render(request, 'home.html')

# Authentication views
def login_page(request):
    """Login page"""
    return render(request, 'auth/login.html')

def register_page(request):
    """Registration page"""
    return render(request, 'auth/register.html')

def password_reset_page(request):
    """Password reset request page"""
    return render(request, 'auth/password-reset.html')

def password_reset_confirm_page(request):
    """Password reset confirm page"""
    return render(request, 'auth/password-reset-confirm.html')

# Dashboard views
def student_dashboard(request):
    """Student dashboard"""
    return render(request, 'dashboard/student.html')

def instructor_dashboard(request):
    """Instructor dashboard"""
    return render(request, 'dashboard/instructor.html')

# Course views
def courses_list(request):
    """Course listing page"""
    return render(request, 'courses/list.html')

def course_detail(request, slug):
    """Course detail page"""
    return render(request, 'courses/detail.html')

# Profile views
def profile_page(request):
    """Student profile page"""
    return render(request, 'profile/student-profile.html')

def instructor_profile_page(request):
    """Instructor profile page"""
    return render(request, 'profile/instructor-profile.html')

def settings_page(request):
    """Settings page"""
    return render(request, 'profile/settings.html')

def circles_list(request):
    """Learning circles listing page"""
    return render(request, 'social/circles.html')

def circle_detail(request, circle_id):
    """Learning circle detail page"""
    return render(request, 'social/circle-detail.html')



def assessments_list(request):
    """Assessments listing page"""
    return render(request, 'assessments/list.html')

def assessment_attempt(request, assessment_id, attempt_id=None):
    """Assessment attempt page"""
    return render(request, 'assessments/attempt.html')

def assessment_results(request, assessment_id, attempt_id):
    """Assessment results page"""
    return render(request, 'assessments/results.html')

def instructor_courses_list(request):
    """Instructor courses list page"""
    return render(request, 'instructor/courses-list.html')

def instructor_course_create(request):
    """Instructor course creation page"""
    return render(request, 'instructor/course-create.html')

def instructor_course_content(request, slug):
    """Instructor course content management page"""
    return render(request, 'instructor/course-content.html')

def instructor_course_edit(request, slug):
    """Instructor course edit page"""
    return render(request, 'instructor/course-edit.html')

def instructor_lesson_edit(request, id):
    """Instructor lesson content editor page"""
    return render(request, 'instructor/lesson-editor.html')

def instructor_course_preview(request, slug):
    """Instructor course preview page"""
    return render(request, 'instructor/course-preview.html')

def instructor_students(request):
    """Instructor students list page"""
    return render(request, 'instructor/students-list.html')

def my_courses(request):
    """Student's enrolled courses page"""
    return render(request, 'students/my-courses.html')
def enrollments_list(request):
    """Student's enrollments page"""
    return render(request, 'student/enrollments.html')
def learn_course(request, slug):
    """Student course learning interface"""
    return render(request, 'students/learn.html')

def checkout(request):
    """Payment checkout page"""
    return render(request, 'payments/checkout.html')

def certificates_list(request):
    """User certificates list page"""
    return render(request, 'certificates/list.html')

def payment_history(request):
    """Payment history and transactions page"""
    return render(request, 'payments/history.html')

def wallet_page(request):
    """Student wallet page"""
    return render(request, 'student/wallet.html')

def live_schedule(request):
    """Live sessions schedule page"""
    return render(request, 'live/schedule.html')

def live_room(request, session_id):
    """Live session room page"""
    return render(request, 'live/room.html')

def exams_list(request):
    """Exams list page"""
    return render(request, 'exams/list.html')

def exam_take(request, exam_id):
    """Exam taking page"""
    return render(request, 'exams/take.html')

def exam_results(request, exam_id):
    """Exam results page"""
    return render(request, 'exams/results.html')

def exam_create(request):
    """Exam creation page"""
    return render(request, 'exams/create.html')

def search_results(request):
    """Search results page"""
    return render(request, 'search/results.html')

def browse_courses(request):
    """Browse courses by category page"""
    return render(request, 'search/browse.html')

def ai_recommendations(request):
    """AI-powered course recommendations"""
    return render(request, 'ai_recommender/recommendations.html')

def course_resources(request, course_id):
    """Student course resources view"""
    return render(request, 'courses/resources.html')

def instructor_resources(request):
    """Instructor resource management"""
    return render(request, 'instructor/resources.html')

def discussions_list(request, course_id):
    """Course discussions listing"""
    return render(request, 'discussions/list.html')

def discussion_thread(request, course_id, thread_id):
    """Individual discussion thread"""
    return render(request, 'discussions/thread.html')

