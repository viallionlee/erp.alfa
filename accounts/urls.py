from django.shortcuts import redirect
from django.urls import path
from . import views
from .views import CustomLoginView

urlpatterns = [
    path('profile/', views.profile, name='profile'),
    path('login/', lambda request: redirect('login', permanent=True)),
    path('logout/', views.custom_logout, name='logout'),
]
