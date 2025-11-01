"""
URL configuration for erp_alfa project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.shortcuts import render
from django.http import JsonResponse
from orders.models import Order
from products.models import Product
from django.db.models import Q
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views
import os
from django.contrib.auth.decorators import login_required
from .views import home, CustomLoginView, api_notification_counts, favicon
from .mobile_views import mobile_home
from accounts import views as account_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', login_required(home), name='home'),
    path('favicon.ico', favicon, name='favicon'),
    path('inventory/', include('inventory.urls')),
    path('orders/', include('orders.urls')),
    path('products/', include('products.urls')),
    path('fullfilment/', include('fullfilment.urls')),
    path('purchaseorder/', include('purchasing.urls')),
    path('finance/', include('finance.urls')),
    path('mobile/', mobile_home, name='mobile_home'),
    path('login/', CustomLoginView.as_view(), name='login'),  # Update ini
    path('logout/', account_views.custom_logout, name='logout'),
    path('accounts/', include('accounts.urls')),
    path('api/notification-counts/', api_notification_counts, name='api_notification_counts'),
]

# Serve static and media files during development
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATICFILES_DIRS[0])
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
