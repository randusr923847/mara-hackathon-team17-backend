from django.urls import path
from . import views


urlpatterns = [
    path('gpu_info/', views.gpu_info),
    path('api/compute/add/', views.addCompute),
    path('api/task/add/', views.addTask)
]
