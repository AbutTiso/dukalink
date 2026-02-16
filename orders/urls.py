from django.urls import path, re_path
from . import views

app_name = 'orders'

urlpatterns = [
    # Regular cart views
    path('cart/', views.cart_detail, name='cart_detail'),
    path('cart/add/<int:product_id>/', views.cart_add, name='cart_add'),
    path('cart/remove/<int:product_id>/', views.cart_remove, name='cart_remove'),
    path('cart/count/', views.cart_count_api, name='cart_count'),
    
    # NEW AJAX endpoints
    path('ajax/cart/add/', views.cart_add_ajax, name='cart_add_ajax'),
    path('ajax/cart/remove/', views.cart_remove_ajax, name='cart_remove_ajax'),
    path('ajax/cart/update/', views.cart_update_ajax, name='cart_update_ajax'),
    path('ajax/cart/count/', views.cart_count_ajax, name='cart_count_ajax'),
    
    # Order views
    path('<int:order_id>/', views.order_detail, name='order_detail'),
    path('my-order/<int:order_id>/', views.customer_order_detail, name='customer_order_detail'),
    # Order tracking
    path('track/<str:order_code>/', views.track_order, name='track_order'),
    
    # API endpoints
    path('api/cart/add/', views.cart_add_api, name='cart_add_api'),
    path('api/cart/remove/', views.cart_remove_api, name='cart_remove_api'),
    path('api/cart/count/', views.cart_count_api, name='cart_count_api'),
    path('api/cart/add/<int:product_id>/', views.cart_add_api_alt, name='cart_add_api_with_id'),
    path('cart/decrement/<int:product_id>/', views.cart_decrement, name='cart_decrement'),
    
    # Silence service worker requests
    path('navbar-notifications/', views.dummy_notifications, name='dummy_notifications'),
    re_path(r'^api/sync/.*$', views.dummy_api, name='dummy_sync'),
]