# dashboard/urls.py
from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    # Product Management
    path('', views.dashboard_home, name='dashboard_home'),
    path('vendor/', views.vendor_dashboard, name='vendor_dashboard'),
    path('product/add/', views.product_add, name='product_add'),
    path('product/<int:product_id>/edit/', views.product_edit, name='product_edit'),
    path('product/<int:product_id>/delete/', views.product_delete, name='product_delete'),
    
    # Vendor Dashboard (Orders)
    path('order/<int:order_id>/', views.order_detail, name='order_detail'),
    path('api/admin/orders/latest/', views.get_latest_orders, name='api_latest_orders'),
    path('order/<int:order_id>/receipt/', views.order_receipt, name='order_receipt'),
    path('confirm-payment/<int:order_id>/', views.confirm_vendor_payment, name='confirm_vendor_payment'), 
    # API Endpoints
    path('api/stats/', views.get_dashboard_stats, name='api_stats'),
    path('api/order/<int:order_id>/', views.order_detail_api, name='api_order_detail'),
    path('api/order/update-status/', views.update_order_status, name='api_update_status'),
]