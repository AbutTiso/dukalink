from django.urls import path
from . import views

app_name = 'vendors'

urlpatterns = [
    path('', views.vendor_list, name='vendor_list'),
    path('api/save-location/', views.save_user_location, name='save_location'),
    path('api/nearby-vendors/', views.get_nearby_vendors, name='nearby_vendors'),
    path('api/ip-location/', views.get_client_ip_location, name='ip_location'),
    path('api/vendors-by-county/', views.get_vendors_by_county, name='vendors_by_county'),
    path('api/geocode/', views.geocode_address, name='geocode'),
    path('api/reverse-geocode/', views.reverse_geocode, name='reverse_geocode'),
]