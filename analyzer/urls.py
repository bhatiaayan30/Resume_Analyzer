from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('analyze/', views.analyze, name='analyze'),
    path('history/', views.history, name='history'),
    path('signup/', views.signup_view, name='signup'),
    path('generate-cover-letter/<int:analysis_id>/', views.generate_cover_letter_api, name='generate_cover_letter'),
]
