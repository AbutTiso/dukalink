from django.shortcuts import render

from django.shortcuts import render, get_object_or_404
from django.core.paginator import Paginator
from .models import Product

def product_list(request):
    products = Product.objects.all()
    
    # Search functionality
    query = request.GET.get('q')
    if query:
        products = products.filter(name__icontains=query) | products.filter(description__icontains=query)
    
    # Pagination
    paginator = Paginator(products, 12)  # Show 12 products per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'products/product_list.html', {'products': page_obj})

# products/views.py
from django.shortcuts import render, get_object_or_404
from .models import Product

def product_detail(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    
    # Get related products from same business
    related_products = Product.objects.filter(
        business=product.business
    ).exclude(id=product.id)[:4]
    
    context = {
        'product': product,
        'related_products': related_products,
    }
    return render(request, 'products/product_detail.html', context)

def product_list(request):
    products = Product.objects.filter(
        business__isnull=False
    ).select_related('business').order_by('-created_at')
    
    context = {
        'products': products,
    }
    return render(request, 'products/product_list.html', context)

from django.shortcuts import render
from django.db.models import Q
from .models import Product

def product_search(request):
    """Search products by name, description, or shop"""
    query = request.GET.get('q', '')
    sort = request.GET.get('sort', 'relevance')
    
    # Start with all available products - use is_available instead of is_active
    products = Product.objects.filter(is_available=True)  # ← CHANGED: is_active to is_available
    
    # Apply search filter if query exists
    if query:
        products = products.filter(
            Q(name__icontains=query) |
            Q(description__icontains=query) |
            Q(business__name__icontains=query)
        ).distinct()
    
    # Apply sorting
    if sort == 'price_low':
        products = products.order_by('price')
    elif sort == 'price_high':
        products = products.order_by('-price')
    elif sort == 'newest':
        products = products.order_by('-created_at')
    else:  # relevance - default ordering
        products = products.order_by('-created_at')
    
    context = {
        'products': products,
        'query': query,
        'sort': sort,
        'total_results': products.count(),
    }
    
    return render(request, 'products/product_search.html', context)


# Also update your product_list view if you want search there too
def product_list(request):
    """Display all products with optional search"""
    products = Product.objects.filter(is_available=True)  # ← CHANGED: is_active to is_available
    
    # Handle search query
    query = request.GET.get('q')
    if query:
        products = products.filter(
            Q(name__icontains=query) |
            Q(description__icontains=query) |
            Q(business__name__icontains=query)
        ).distinct()
    
    context = {
        'products': products,
        'query': query,
    }
    return render(request, 'products/product_list.html', context)