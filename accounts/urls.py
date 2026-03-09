from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    # Registration choice page
    path("register/", views.register_choice, name="register_choice"),
    
    # Business (vendor) registration
    path("register/business/", views.register_business, name="register_business"),
    
    # Regular user (buyer) registration
    path('register/user/', views.register_user, name='register_user'),
    
    # Authentication
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    
    # Dashboard redirect
    path('dashboard/', views.dashboard_redirect, name='dashboard_redirect'),
    
    # User profile and orders
    path('profile/', views.profile, name='profile'),
    path('my-orders/', views.my_orders, name='my_orders'),
    
    # Vendor document management
    path('upload-documents/<int:business_id>/', views.upload_documents, name='upload_documents'),
    path('document-status/', views.document_status, name='document_status'),
]