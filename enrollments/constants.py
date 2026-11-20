LESSON_COMPLETION_THRESHOLD = 0.8
# Enrollment statuses that mean "the student owns this course". A completed
# course is still owned: it must never be charged again and must stay
# accessible (see AUDIT_REPORT.md PAY-01 / LRN-03).
ACCESS_STATUSES = ('active', 'completed')
