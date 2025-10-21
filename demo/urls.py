from django.urls import path
from . import views

urlpatterns = [
    path('demoextract/', views.demoextract_page, name='demoextract_page'),
    path('demoextract/data/', views.demoextract_data, name='demoextract_data'),
    path('extract_skudemo/', views.extract_skudemo, name='extract_skudemo'),
]
