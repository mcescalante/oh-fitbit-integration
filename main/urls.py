from django.urls import path

from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('complete/oh', views.complete, name='complete'),
    path('complete/fitbit', views.complete_fitbit, name='complete_fitbit'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('update_data/', views.update_data, name='update_data'),
    path('remove_fitbit/', views.remove_fitbit, name='remove_fitbit'),
    path('about/', views.about, name='about'),
    path('logout/', views.user_logout, name='logout'),
]
