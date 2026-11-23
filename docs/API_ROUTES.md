# API routes

> Generated from the URLconf by `python manage.py api_routes --write`; do not
> edit by hand. `core.tests` fails when this file is out of date.

Paths use Django converter syntax (`<int:pk>`, `<slug:slug>`). **Auth** lists
the view's DRF permission classes (`AllowAny` = public). Authenticated calls
from the browser use the httpOnly JWT cookie plus the `X-CSRFToken` header;
other clients send `Authorization: Bearer <access token>`.


## `/api/accounts/`

| Path | Methods | Auth | View |
|---|---|---|---|
| `/api/accounts/token/` | POST | AllowAny | `accounts.custom_token.CustomTokenObtainPairView` |
| `/api/accounts/token/refresh/` | POST | AllowAny | `accounts.custom_token.CookieTokenRefreshView` |
| `/api/accounts/register/` | POST | AllowAny | `accounts.views.RegisterView` |
| `/api/accounts/logout/` | POST | AllowAny | `accounts.views.LogoutView` |
| `/api/accounts/change-password/` | POST | IsAuthenticated | `accounts.views.ChangePasswordView` |
| `/api/accounts/me/` | GET PATCH | IsAuthenticated | `accounts.views.MeView` |
| `/api/accounts/profile/` | GET PUT PATCH | IsAuthenticated | `accounts.views.ProfileView` |
| `/api/accounts/users/` | GET | IsAdmin | `accounts.views.UserListView` |
| `/api/accounts/users/<int:id>/` | GET | IsAdmin | `accounts.views.UserDetailView` |
| `/api/accounts/users/<int:user_id>/role/` | PATCH | IsAdmin | `accounts.views.UpdateUserRoleView` |
| `/api/accounts/users/<int:user_id>/promote/` | POST | IsAdmin | `accounts.views.PromoteToInstructorView` |
| `/api/accounts/users/<int:user_id>/deactivate/` | POST | IsAdmin | `accounts.views.DeactivateUserView` |
| `/api/accounts/users/<int:user_id>/activate/` | POST | IsAdmin | `accounts.views.ActivateUserView` |
| `/api/accounts/api-keys/` | GET POST | IsAuthenticated | `accounts.views.APIKeyListCreateView` |
| `/api/accounts/api-keys/<int:id>/` | GET DELETE | IsAuthenticated | `accounts.views.APIKeyDetailView` |
| `/api/accounts/api-keys/<int:key_id>/revoke/` | PATCH | IsAuthenticated | `accounts.views.APIKeyRevokeView` |
| `/api/accounts/api-keys/<int:key_id>/toggle/` | PATCH | IsAuthenticated | `accounts.views.APIKeyRevokeView` |
| `/api/accounts/instructor-only/` | GET | IsInstructor | `accounts.views.InstructorOnlyView` |

## `/api/assessments/`

| Path | Methods | Auth | View |
|---|---|---|---|
| `/api/assessments/quiz/lesson/<int:lesson_id>/` | GET | IsAuthenticated | `assessments.views.QuizDetailView` |
| `/api/assessments/quiz/<int:quiz_id>/start/` | POST | IsAuthenticated | `assessments.views.StartQuizView` |
| `/api/assessments/quiz/attempt/<int:attempt_id>/submit/` | POST | IsAuthenticated | `assessments.views.SubmitQuizView` |
| `/api/assessments/quiz/lesson/<int:lesson_id>/manage/` | GET POST | IsAuthenticated | `assessments.views_quiz_management.ManageQuizView` |
| `/api/assessments/analytics/course/<int:course_id>/overview/` | GET | IsAuthenticated | `assessments.view_analytics.InstructorAssessmentOverviewView` |
| `/api/assessments/analytics/quiz/<int:quiz_id>/questions/` | GET | IsAuthenticated | `assessments.view_analytics.QuizQuestionAnalyticsView` |
| `/api/assessments/quiz/<int:quiz_id>/attempt/start/` | POST | IsAuthenticated | `assessments.views_attempt.StartQuizAttemptView` |
| `/api/assessments/quiz/attempt/<int:attempt_id>/answer/submit/` | POST | IsAuthenticated | `assessments.views_attempt.SubmitQuizAnswerView` |

## `/api/certificates/`

| Path | Methods | Auth | View |
|---|---|---|---|
| `/api/certificates/` | GET | IsAuthenticated | `certificates.views.MyCertificatesListView` |
| `/api/certificates/my/` | GET | IsAuthenticated | `certificates.views.MyCertificatesListView` |
| `/api/certificates/my/<int:course_id>/` | GET | IsAuthenticated | `certificates.views.MyCertificateDetailView` |
| `/api/certificates/<uuid:certificate_id>/download/` | GET | IsAuthenticated | `certificates.views.DownloadCertificateView` |
| `/api/certificates/download/<int:course_id>/` | GET | IsAuthenticated | `certificates.views.DownloadCertificateView` |
| `/api/certificates/verify/<str:code>/` | GET | AllowAny | `certificates.views.VerifyCertificateView` |
| `/api/certificates/regenerate/<uuid:certificate_id>/` | POST | IsAuthenticated, IsAdmin | `certificates.views.regenerate_certificate` |

## `/api/courses/`

| Path | Methods | Auth | View |
|---|---|---|---|
| `/api/courses/categories/` | GET | AllowAny | `courses.views.CategoryListView` |
| `/api/courses/categories/create/` | POST | IsAdmin | `courses.views.CategoryCreateView` |
| `/api/courses/tags/` | GET POST | IsAuthenticated | `courses.views.TagListCreateView` |
| `/api/courses/` | GET | AllowAny | `courses.views.CourseListView` |
| `/api/courses/create/` | POST | IsAuthenticated, IsInstructor | `courses.views.CourseCreateView` |
| `/api/courses/instructor/courses/` | GET | IsAuthenticated, IsInstructor | `courses.views.InstructorCoursesView` |
| `/api/courses/admin/course-stats/` | GET | IsAuthenticated, IsAdmin | `courses.views_analytics.AdminCourseStatsView` |
| `/api/courses/<int:id>/` | GET | AllowAny | `courses.views.CourseDetailView` |
| `/api/courses/<int:id>/update/` | PUT PATCH | IsAuthenticated | `courses.views.CourseUpdateView` |
| `/api/courses/<int:id>/delete/` | DELETE | IsAuthenticated | `courses.views.CourseDeleteView` |
| `/api/courses/<int:course_id>/submit/` | POST | IsAuthenticated | `courses.views.SubmitCourseForReviewView` |
| `/api/courses/<int:course_id>/publish/` | POST | IsAuthenticated, IsAdmin | `courses.views.PublishCourseView` |
| `/api/courses/<int:course_id>/reject/` | POST | IsAuthenticated, IsAdmin | `courses.views.RejectCourseView` |
| `/api/courses/<int:course_id>/archive/` | POST | IsAuthenticated | `courses.views.ArchiveCourseView` |
| `/api/courses/<int:course_id>/new-version/` | POST | IsAuthenticated | `courses.views.NewCourseVersionView` |
| `/api/courses/<int:course_id>/curriculum/` | GET | AllowAny | `courses.views.CourseCurriculumView` |
| `/api/courses/<int:course_id>/resume/` | GET | IsAuthenticated | `courses.views.ResumeLearningView` |
| `/api/courses/<int:course_id>/modules/` | GET POST | AllowAny | `courses.views.ModuleListView` |
| `/api/courses/<int:course_id>/sections/` | GET POST | AllowAny | `courses.views.ModuleListView` |
| `/api/courses/modules/create/` | POST | IsAuthenticated | `courses.views.ModuleCreateView` |
| `/api/courses/modules/<int:id>/update/` | GET PUT PATCH DELETE | IsAuthenticated | `courses.views.ModuleUpdateView` |
| `/api/courses/modules/<int:id>/delete/` | DELETE | IsAuthenticated | `courses.views.ModuleDeleteView` |
| `/api/courses/modules/<int:module_id>/lessons/` | GET POST | AllowAny | `courses.views.LessonListView` |
| `/api/courses/sections/<int:id>/` | GET PUT PATCH DELETE | IsAuthenticated | `courses.views.ModuleUpdateView` |
| `/api/courses/sections/<int:id>/lessons/` | GET POST | AllowAny | `courses.views.LessonListView` |
| `/api/courses/lessons/create/` | POST | IsAuthenticated | `courses.views.LessonCreateView` |
| `/api/courses/lessons/<int:id>/` | GET PUT PATCH DELETE | IsAuthenticated | `courses.views.LessonRetrieveUpdateView` |
| `/api/courses/lessons/<int:id>/update/` | PUT PATCH | IsAuthenticated | `courses.views.LessonUpdateView` |
| `/api/courses/lessons/<int:id>/delete/` | DELETE | IsAuthenticated | `courses.views.LessonDeleteView` |
| `/api/courses/lessons/<int:lesson_id>/content/` | GET | AllowAny | `courses.views.LessonDetailView` |
| `/api/courses/<slug:slug>/sections/` | GET POST | AllowAny | `courses.views.ModuleListView` |
| `/api/courses/<slug:slug>/` | GET | AllowAny | `courses.views.CourseDetailView` |

## `/api/enrollments/`

| Path | Methods | Auth | View |
|---|---|---|---|
| `/api/enrollments/` | GET | IsAuthenticated | `enrollments.views.EnrollmentListView` |
| `/api/enrollments/my-enrollments/` | GET | IsAuthenticated | `enrollments.views.EnrollmentListView` |
| `/api/enrollments/enrollments/<int:pk>/` | GET | IsAuthenticated | `enrollments.views.EnrollmentDetailView` |
| `/api/enrollments/enroll/` | POST | IsAuthenticated | `enrollments.views.EnrollCourseView` |
| `/api/enrollments/enrollments/<int:enrollment_id>/cancel/` | PATCH | IsAuthenticated | `enrollments.views.CancelEnrollmentView` |
| `/api/enrollments/my-learning/` | GET | IsAuthenticated | `enrollments.views.MyLearningView` |
| `/api/enrollments/completed-courses/` | GET | IsAuthenticated | `enrollments.views.CompletedCoursesView` |
| `/api/enrollments/courses/<int:course_id>/progress/` | GET | IsAuthenticated | `enrollments.views.CourseProgressView` |
| `/api/enrollments/lessons/<int:lesson_id>/progress/` | GET | IsAuthenticated | `enrollments.views.LessonProgressView` |
| `/api/enrollments/lessons/<int:lesson_id>/watch-time/` | PATCH | IsAuthenticated | `enrollments.views.LessonWatchTimeView` |
| `/api/enrollments/courses/<int:course_id>/resume-lesson/` | GET | IsAuthenticated | `enrollments.views.ResumeLessonView` |
| `/api/enrollments/courses/<int:course_id>/lessons/<int:lesson_id>/next/` | GET | IsAuthenticated | `enrollments.views.NextLessonView` |
| `/api/enrollments/lessons/<int:lesson_id>/complete/` | POST | IsAuthenticated | `enrollments.views.CompleteLessonView` |
| `/api/enrollments/wishlist/` | GET | IsAuthenticated | `enrollments.views.WishlistListView` |
| `/api/enrollments/wishlist/add/` | POST | IsAuthenticated | `enrollments.views.AddToWishlistView` |
| `/api/enrollments/wishlist/<int:pk>/remove/` | DELETE | IsAuthenticated | `enrollments.views.RemoveFromWishlistView` |
| `/api/enrollments/wishlist/check/<int:course_id>/` | GET | IsAuthenticated | `enrollments.views.CheckWishlistView` |
| `/api/enrollments/stats/` | GET | IsAuthenticated | `enrollments.views.EnrollmentStatsView` |
| `/api/enrollments/learning-dashboard/` | GET | IsAuthenticated | `enrollments.views.LearningProgressDashboardView` |
| `/api/enrollments/instructor/courses/<int:course_id>/lesson-analytics-csv/` | GET | IsAuthenticated, IsInstructor | `enrollments.views.InstructorLessonAnalyticsCSVView` |

## `/api/exams/`

| Path | Methods | Auth | View |
|---|---|---|---|
| `/api/exams/questions/` | GET POST | IsAuthenticated, IsInstructor | `exams.views.QuestionBankListView` |
| `/api/exams/questions/<int:pk>/` | GET PUT PATCH DELETE | IsAuthenticated, IsInstructor | `exams.views.QuestionBankDetailView` |
| `/api/exams/` | GET POST | IsAuthenticated | `exams.views.ExamListCreateView` |
| `/api/exams/<int:pk>/` | GET PUT PATCH DELETE | IsAuthenticated | `exams.views.ExamDetailView` |
| `/api/exams/course/<int:course_id>/` | GET | IsAuthenticated | `exams.views.CourseExamListView` |
| `/api/exams/<int:exam_id>/start/` | POST | IsAuthenticated | `exams.views.start_exam` |
| `/api/exams/<int:exam_id>/submit/` | POST | IsAuthenticated | `exams.views.submit_exam` |
| `/api/exams/<int:exam_id>/save-answers/` | POST | IsAuthenticated | `exams.views.save_exam_answers` |
| `/api/exams/<int:exam_id>/attempts/` | GET | IsAuthenticated | `exams.views.ExamHistoryView` |
| `/api/exams/attempt/<int:attempt_id>/result/` | GET | IsAuthenticated | `exams.views.exam_result_detail` |
| `/api/exams/<int:exam_id>/analytics/` | GET | IsAuthenticated, IsInstructor | `exams.views.exam_analytics` |
| `/api/exams/<int:exam_id>/all-attempts/` | GET | IsAuthenticated, IsInstructor | `exams.views.InstructorExamAttemptsView` |
| `/api/exams/<int:exam_id>/publish/` | POST | IsAuthenticated, IsInstructor | `exams.views.publish_exam` |
| `/api/exams/<int:exam_id>/archive/` | POST | IsAuthenticated, IsInstructor | `exams.views.archive_exam` |

## `/api/instructors/`

| Path | Methods | Auth | View |
|---|---|---|---|
| `/api/instructors/dashboard/` | GET | IsAuthenticated, IsInstructor | `instructors.views.InstructorDashboardView` |
| `/api/instructors/profile/` | GET PUT PATCH | IsAuthenticated, IsInstructor | `instructors.views.InstructorProfileView` |
| `/api/instructors/students/` | GET | IsAuthenticated, IsInstructor | `instructors.views.InstructorStudentsView` |
| `/api/instructors/featured/` | GET | AllowAny | `instructors.views.FeaturedInstructorsView` |

## `/api/payments/`

| Path | Methods | Auth | View |
|---|---|---|---|
| `/api/payments/` | GET | IsAuthenticated | `payments.views.PaymentListView` |
| `/api/payments/<int:payment_id>/` | GET | IsAuthenticated | `payments.views.PaymentDetailView` |
| `/api/payments/<int:payment_id>/cancel/` | POST | IsAuthenticated | `payments.views.PaymentCancelView` |
| `/api/payments/refunds/` | GET | IsAuthenticated | `payments.views.RefundListView` |
| `/api/payments/refunds/request/` | POST | IsAuthenticated | `payments.views.RefundRequestView` |
| `/api/payments/refunds/<int:refund_id>/approve/` | POST | IsAuthenticated, IsAdmin | `payments.views.RefundApproveView` |
| `/api/payments/refunds/<int:refund_id>/reject/` | POST | IsAuthenticated, IsAdmin | `payments.views.RefundRejectView` |
| `/api/payments/payouts/` | GET | IsAuthenticated, IsInstructor | `payments.views.PayoutListView` |
| `/api/payments/payouts/request/` | POST | IsAuthenticated, IsInstructor | `payments.views.PayoutRequestView` |
| `/api/payments/payouts/balance/` | GET | IsAuthenticated, IsInstructor | `payments.views.PayoutBalanceView` |
| `/api/payments/payouts/<int:payout_id>/cancel/` | POST | IsAuthenticated, IsInstructor | `payments.views.PayoutCancelView` |
| `/api/payments/payouts/<int:payout_id>/approve/` | POST | IsAuthenticated, IsAdmin | `payments.views.PayoutApproveView` |
| `/api/payments/payouts/<int:payout_id>/complete/` | POST | IsAuthenticated, IsAdmin | `payments.views.PayoutCompleteView` |
| `/api/payments/payouts/<int:payout_id>/reject/` | POST | IsAuthenticated, IsAdmin | `payments.views.PayoutRejectView` |
| `/api/payments/coupons/` | GET | IsAuthenticated | `payments.views.CouponListView` |
| `/api/payments/coupons/create/` | POST | IsAuthenticated, IsAdmin | `payments.views.CouponCreateView` |
| `/api/payments/coupons/validate/` | POST | IsAuthenticated | `payments.views.CouponValidateView` |
| `/api/payments/coupons/<int:coupon_id>/deactivate/` | DELETE | IsAuthenticated, IsAdmin | `payments.views.CouponDeactivateView` |
| `/api/payments/stats/` | GET | IsAuthenticated, IsAdmin | `payments.views.PaymentStatsView` |
| `/api/payments/instructor/earnings/` | GET | IsAuthenticated, IsInstructor | `payments.views.InstructorEarningsView` |
| `/api/payments/webhooks/stripe/` | POST | AllowAny | `payments.webhooks.StripeWebhookView` |

## `/api/schema/`

| Path | Methods | Auth | View |
|---|---|---|---|
| `/api/schema/` | GET | AllowAny | `drf_spectacular.views.SpectacularAPIView` |

## `/api/students/`

| Path | Methods | Auth | View |
|---|---|---|---|
| `/api/students/dashboard/` | GET | IsAuthenticated, IsStudent | `students.views.StudentDashboardView` |
| `/api/students/activity-feed/` | GET | IsAuthenticated, IsStudent | `students.views.StudentActivityFeedView` |
| `/api/students/profile/` | GET PUT PATCH | IsAuthenticated, IsStudent | `students.views.StudentProfileView` |
| `/api/students/notes/` | GET POST | IsAuthenticated, IsStudent | `students.views.StudentNoteListCreateView` |
| `/api/students/notes/<uuid:id>/` | GET PUT PATCH DELETE | IsAuthenticated, IsStudent | `students.views.StudentNoteDetailView` |
| `/api/students/bookmarks/` | GET POST | IsAuthenticated, IsStudent | `students.views.StudentBookmarkListCreateView` |
| `/api/students/bookmarks/<uuid:id>/` | GET PUT PATCH DELETE | IsAuthenticated, IsStudent | `students.views.StudentBookmarkDetailView` |
| `/api/students/wallet/` | GET | IsAuthenticated | `students.views.WalletView` |
| `/api/students/wallet/transactions/` | GET | IsAuthenticated | `students.views.WalletTransactionsView` |
