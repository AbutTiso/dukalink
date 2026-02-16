from django.urls import path
from . import views

app_name = 'payments'

urlpatterns = [
    # Checkout page - shows form (GET) and processes payment (POST)
    path('checkout/', views.checkout, name='checkout'),
    
    # M-Pesa callback URLs (for Safaricom to call)
    path('mpesa-callback/', views.mpesa_callback, name='mpesa_callback'),
    path('mpesa-timeout/', views.mpesa_timeout, name='mpesa_timeout'),
    
    # Payment status checking (for AJAX polling)
    path('status/<str:checkout_request_id>/', views.payment_status, name='payment_status'),
    
    # Success page after payment completion
    path('success/<int:order_id>/', views.payment_success, name='payment_success'),
    path('pochi-payments/', views.vendor_pochi_payments, name='vendor_pochi_payments'),
    path('confirm-vendor-payment/<int:order_id>/', views.confirm_vendor_payment, name='confirm_vendor_payment'),
    path('pochi-instructions/<int:order_id>/', views.pochi_payment_instructions, name='pochi_payment_instructions'), 
    path('process-next-payment/', views.process_next_vendor_payment, name='process_next_vendor_payment'),
    path('confirm-pochi-payment/<int:order_id>/', views.confirm_pochi_payment, name='confirm_pochi_payment'),
]