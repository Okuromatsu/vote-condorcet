"""
URL routing for voting app
==========================

Maps URL patterns to view functions for:
- Creating polls
- Voting on polls
- Viewing results
- API endpoints

All URLs are protected with CSRF tokens and input validation.
"""

from django.urls import path
from . import views

app_name = 'voting'

urlpatterns = [
    # Home page / poll list
    path('', views.index, name='index'),
    
    # About Condorcet voting
    path('about/', views.about_condorcet, name='about_condorcet'),
    
    # Poll creation
    path('create/', views.create_poll, name='create_poll'),
    
    # Poll confirmation (after creation)
    path('poll/<uuid:poll_id>/confirm/<str:creator_code>/', views.poll_confirmation, name='poll_confirmation'),
    
    # Creator dashboard
    path('creator/<str:creator_code>/', views.creator_dashboard, name='creator_dashboard'),
    
    # Creator dashboard login
    path('dashboard/login/', views.dashboard_login, name='dashboard_login'),
    
    # Voting interface
    path('vote/<uuid:poll_id>/', views.vote_poll, name='vote_poll'),
    
    # Results display
    path('results/<uuid:poll_id>/', views.results_poll, name='results_poll'),
    
    # Share link generation
    path('api/share/<uuid:poll_id>/', views.poll_share_link, name='share_link'),
    
    # API endpoint for results (JSON)
    path('api/results/<uuid:poll_id>/', views.poll_api_results, name='api_results'),
]
