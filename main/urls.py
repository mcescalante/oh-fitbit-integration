from django.urls import path

from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('complete/oh', views.complete, name='complete'),
    path('complete/fitbit', views.complete_fitbit, name='complete_fitbit'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('remove_fitbit/', views.remove_fitbit, name='remove_fitbit')
]
