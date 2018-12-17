from django.urls import path

from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('complete/oh', views.complete, name='complete'),
    path('complete/googlefit', views.complete_googlefit, name='complete_googlefit'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('update_data/', views.update_data, name='update_data'),
    path('remove_googlefit/', views.remove_googlefit, name='remove_googlefit')
]
