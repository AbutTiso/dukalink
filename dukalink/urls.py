from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView

urlpatterns = [
    path('admin/', admin.site.urls),

    path('', include("shops.urls")),
    path('dashboard/', include("dashboard.urls")),
    path('accounts/', include("accounts.urls")),
    path('orders/', include("orders.urls")),  # Keep this one
    path('payments/', include("payments.urls")),
    path('products/', include("products.urls")),
    path('about/', TemplateView.as_view(template_name='pages/about.html'), name='about'),
    path('admin-panel/', include('admin_dashboard.urls')),
    path('pages/', include('pages.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)