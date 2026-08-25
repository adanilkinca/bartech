from django.urls import path

from . import views

app_name = 'catalog'

urlpatterns = [
    path('cocktails/', views.cocktail_list, name='cocktail-list'),
    path('cocktails/<slug:slug>/', views.cocktail_detail, name='cocktail-detail'),
    path('ingredients/', views.ingredient_list, name='ingredient-list'),
    path('ingredients/<slug:slug>/', views.ingredient_detail, name='ingredient-detail'),
]