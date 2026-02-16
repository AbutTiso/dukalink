from django.urls import path
from . import views

# Option 1: With namespace
app_name = 'products'

urlpatterns = [
    path('', views.product_list, name='product_list'),
     path('<int:product_id>/', views.product_detail, name='product_detail'),  
       path('search/', views.product_search, name='product_search'),
]

# OR Option 2: Without namespace
# urlpatterns = [
#     path('', views.product_list, name='product_list'),
# ]