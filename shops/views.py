from django.shortcuts import render, get_object_or_404, redirect
from accounts.models import Business
from products.models import Product

from django.shortcuts import render
from accounts.models import Business
from products.models import Product
from orders.models import Order, OrderItem
from django.db.models import Count, Sum, Q
from django.utils import timezone
from datetime import timedelta

# shops/views.py
from django.shortcuts import render
from accounts.models import Business
from products.models import Product
from orders.models import Order, OrderItem
from django.db.models import Count, Sum, Q
from django.utils import timezone
from datetime import timedelta

def home(request):
    """Public homepage - shows shops and products to customers"""
    
    # Get all active businesses
    businesses = Business.objects.all().order_by('-created_at')[:6]
    
    # Get all products from all businesses
    all_products = Product.objects.select_related('business').filter(
        business__isnull=False
    ).order_by('-created_at')[:12]
    
    # Get featured products (random for now)
    featured_products = Product.objects.select_related('business').filter(
        business__isnull=False
    ).order_by('?')[:8]
    
    # Get popular products (most ordered in last 30 days)
    last_30_days = timezone.now() - timedelta(days=30)
    popular_products = Product.objects.select_related('business').filter(
        orderitem__order__created_at__gte=last_30_days
    ).annotate(
        order_count=Count('orderitem')
    ).order_by('-order_count')[:8]
    
    # Calculate platform stats
    total_vendors = Business.objects.count()
    total_orders = Order.objects.count()
    total_products = Product.objects.count()
    
    # Calculate total revenue
    total_revenue = 0
    completed_items = OrderItem.objects.filter(order__status='completed')
    for item in completed_items:
        total_revenue += item.quantity * item.price
    
    context = {
        'businesses': businesses,
        'all_products': all_products,
        'featured_products': featured_products,
        'popular_products': popular_products,
        'total_vendors': total_vendors,
        'total_orders': total_orders,
        'total_products': total_products,
        'total_revenue': f"{total_revenue:,.0f}",
    }
    
    # IMPORTANT: Specify the full template path with the shops namespace
    return render(request, 'shops/home.html', context)

def shop_detail(request, slug):
    business = get_object_or_404(Business, slug=slug)
    products = Product.objects.filter(business=business, is_available=True)
    
    # ===== SEARCH =====
    query = request.GET.get('q')
    if query:
        products = products.filter(
            models.Q(name__icontains=query) | 
            models.Q(description__icontains=query)
        )
    
    # ===== SORTING =====
    sort = request.GET.get('sort', 'all')
    
    if sort == 'price_low':
        products = products.order_by('price')
    elif sort == 'price_high':
        products = products.order_by('-price')
    elif sort == 'newest':
        products = products.order_by('-created_at')
    else:  # 'all' or default
        products = products.order_by('-created_at')  # Newest first
    
    # ===== PAGINATION =====
    from django.core.paginator import Paginator
    paginator = Paginator(products, 12)  # 12 products per page
    page_number = request.GET.get('page')
    page_products = paginator.get_page(page_number)
    
    # ===== ORDERS COUNT =====
    from orders.models import Order
    total_orders = Order.objects.filter(
        order_items__product__business=business
    ).distinct().count()
    
    return render(request, "shops/shop_detail.html", {
        "business": business,
        "products": page_products,  # This is now paginated!
        "total_orders": total_orders
    })
from django.shortcuts import render

def shop_list(request):
    return render(request, 'shops/shop_list.html')

def register_shop(request):
    return render(request, 'shops/register_shop.html')

