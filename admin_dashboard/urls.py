from django.urls import path
from . import views

app_name = 'admin_dashboard'

urlpatterns = [
    # Main dashboard
    path('', views.admin_dashboard, name='dashboard'),
    
    # Vendor management
    path('vendors/', views.admin_vendors, name='vendors'),
    path('vendors/<int:vendor_id>/approve/', views.approve_vendor, name='approve_vendor'),
    path('vendors/<int:vendor_id>/suspend/', views.suspend_vendor, name='suspend_vendor'),
    path('vendors/<int:vendor_id>/reject/', views.reject_vendor, name='reject_vendor'),
    path('vendors/<int:vendor_id>/details/', views.vendor_details, name='vendor_details'),
    
    # ============== DOCUMENT VERIFICATION URLs ==============
    # Document verification dashboard
    path('vendor-documents/', views.vendor_documents_list, name='vendor_documents'),
    
    # Review vendor documents (detailed review page)
    path('review-vendor/<int:vendor_id>/', views.review_vendor_documents, name='review_vendor'),
    
    # View individual document - KEEP THIS ONE, REMOVE THE DUPLICATE
    path('vendors/<int:vendor_id>/documents/<str:doc_type>/', 
         views.vendor_document_detail, name='vendor_document_detail'),
    
    # Verify vendor (alternative to approve_vendor)
    path('verify-vendor/<int:vendor_id>/', views.verify_vendor_documents, name='verify_vendor'),
    
    # Bulk verify vendors
    path('vendors/bulk-verify/', views.bulk_verify_vendors, name='bulk_verify'),
    
    # Export vendor data to CSV
    path('vendors/export/', views.export_vendor_data, name='export_vendors'),
    # ========================================================
    
    # Product management
    path('products/', views.admin_products, name='products'),
    
    # Order management
    path('orders/', views.admin_orders, name='orders'),
    
    # Analytics
    path('analytics/', views.admin_analytics, name='analytics'),
    
    # Superadmin management
    path('make-superadmin/<int:user_id>/', views.make_superadmin, name='make_superadmin'),
]