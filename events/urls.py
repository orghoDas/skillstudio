from django.urls import path
from . import views

app_name = 'events'

urlpatterns = [
    # Event Management
    path('', views.EventListCreateView.as_view(), name='event-list'),
    path('<int:pk>/', views.EventDetailView.as_view(), name='event-detail'),
    
    # Event Registration
    path('<int:event_id>/register/', views.register_event, name='register-event'),
    path('registration/<int:registration_id>/cancel/', views.cancel_registration, name='cancel-registration'),
    path('my-registrations/', views.my_registrations, name='my-registrations'),
    
    # Event Feedback
    path('<int:event_id>/feedback/', views.submit_feedback, name='submit-feedback'),
    path('<int:event_id>/feedbacks/', views.event_feedbacks, name='event-feedbacks'),
    
    # Instructor Views
    path('<int:event_id>/analytics/', views.event_analytics_view, name='event-analytics'),
    path('<int:event_id>/registrations/', views.event_registrations_list, name='event-registrations'),
    path('registration/<int:registration_id>/attendance/', views.mark_user_attendance, name='mark-attendance'),
    
    # Event Resources
    path('<int:event_id>/resources/upload/', views.upload_event_resource, name='upload-resource'),
    path('<int:event_id>/resources/', views.event_resources_list, name='event-resources'),
    
    # Discovery
    path('upcoming/', views.upcoming_events_view, name='upcoming-events'),
    path('featured/', views.featured_events_view, name='featured-events'),
]
