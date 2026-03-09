# dashboard/urls.py
from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    # Main dashboard
    path('', views.dashboard_home, name='dashboard_home'),
    path('vendor/', views.vendor_dashboard, name='vendor_dashboard'),
    
    # Product management
    path('products/add/', views.product_add, name='product_add'),
    path('products/edit/<int:product_id>/', views.product_edit, name='product_edit'),
    path('products/delete/<int:product_id>/', views.product_delete, name='product_delete'),
    
    # Order pages
    path('order/<int:order_id>/', views.order_detail, name='order_detail'),
    path('order/<int:order_id>/receipt/', views.order_receipt, name='order_receipt'),
    
    # API endpoints
    path('api/order/<int:order_id>/', views.order_detail_api, name='order_detail_api'),
    path('api/order/update-status/', views.update_order_status, name='update_order_status'),
    path('api/stats/', views.get_dashboard_stats, name='get_dashboard_stats'),
    path('api/order/<int:order_id>/confirm-payment/', views.confirm_vendor_payment, name='confirm_vendor_payment'),
    
    # Public API (for admin)
    path('api/latest-orders/', views.get_latest_orders, name='latest_orders'),
]