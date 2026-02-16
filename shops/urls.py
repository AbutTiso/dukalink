from django.urls import path
from . import views
app_name = 'shops'  # Add this line

urlpatterns = [
    path('', views.home, name="home"),
    path('b/<slug:slug>/', views.shop_detail, name="shop_detail"),
     path('', views.shop_list, name='shop_list'),
    path('register/', views.register_shop, name='register_shop')

]
