"""
URL configuration for core project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
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
from django.urls import path
from judge import views
from judge import dashboard_views
urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/login/', views.api_login),          # 登录获取 Token
    path('api/problems/', views.api_get_problems), # 获取题库列表
    path('api/dashboard/overview/', dashboard_views.api_dashboard_overview),
    path('api/dashboard/submissions-trend/', dashboard_views.api_submissions_trend),
    path('api/dashboard/status-distribution/', dashboard_views.api_status_distribution),
    path('api/dashboard/user-ranking/', dashboard_views.api_user_ranking),
]