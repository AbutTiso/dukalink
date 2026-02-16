from django.urls import path
from . import views

app_name = 'accounts'  # Add this line

urlpatterns = [
    path("register/", views.register_choice, name="register_choice"),  # Choice page
    path("register/business/", views.register_business, name="register_business"),
    path("register/user/", views.register, name="register_user"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path('profile/', views.profile, name='profile'),
    path('my-orders/', views.my_orders, name='my_orders'),
    path('upload-documents/<int:business_id>/', views.upload_documents, name='upload_documents'),
    path('document-status/', views.document_status, name='document_status'),
]