from django.shortcuts import render, get_object_or_404, redirect
from django.core.paginator import Paginator
from django.db.models import Q
from django.urls import reverse
from .models import Product, Category

def product_list(request):
    """Display all products with search, filtering, and sorting"""
    # Start with all available products
    products = Product.objects.filter(is_available=True).select_related('business', 'category')
    
    # Get all categories for filter sidebar
    categories = Category.objects.all().order_by('name')
    
    # Handle search query
    query = request.GET.get('q', '')
    if query:
        products = products.filter(
            Q(name__icontains=query) |
            Q(description__icontains=query) |
            Q(business__name__icontains=query)
        ).distinct()
    
    # Handle category filter
    category_id = request.GET.get('category')
    if category_id:
        products = products.filter(category_id=category_id)
    
    # Handle sorting
    sort = request.GET.get('sort', 'newest')
    
    if sort == 'price_low':
        products = products.order_by('price')
    elif sort == 'price_high':
        products = products.order_by('-price')
    elif sort == 'newest':
        products = products.order_by('-created_at')
    elif sort == 'name_asc':
        products = products.order_by('name')
    elif sort == 'name_desc':
        products = products.order_by('-name')
    else:
        products = products.order_by('-created_at')
    
    # Pagination - 12 products per page
    paginator = Paginator(products, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'products': page_obj,
        'categories': categories,
        'query': query,
        'current_sort': sort,
        'selected_category': int(category_id) if category_id else None,
        'total_results': products.count(),
    }
    
    return render(request, 'products/product_list.html', context)


def product_detail(request, product_id):
    """Display single product details"""
    product = get_object_or_404(Product, id=product_id)
    
    # Get related products from same business or same category
    related_products = Product.objects.filter(
        Q(business=product.business) | Q(category=product.category),
        is_available=True
    ).exclude(id=product.id).distinct()[:4]
    
    context = {
        'product': product,
        'related_products': related_products,
    }
    return render(request, 'products/product_detail.html', context)


def product_search(request):
    """Search products - redirects to product_list with search query"""
    query = request.GET.get('q', '')
    sort = request.GET.get('sort', 'newest')
    category = request.GET.get('category', '')
    
    # Build redirect URL with query and sort parameters
    url = reverse('products:product_list')
    params = []
    if query:
        params.append(f'q={query}')
    if sort:
        params.append(f'sort={sort}')
    if category:
        params.append(f'category={category}')
    
    if params:
        url += '?' + '&'.join(params)
    
    return redirect(url)


def products_by_category(request, category_slug):
    """Display products filtered by category slug"""
    category = get_object_or_404(Category, slug=category_slug)
    products = Product.objects.filter(category=category, is_available=True)
    
    # Get all categories for filter sidebar
    categories = Category.objects.all().order_by('name')
    
    # Pagination
    paginator = Paginator(products, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'products': page_obj,
        'categories': categories,
        'selected_category': category.id,
        'category': category,
        'total_results': products.count(),
    }
    
    return render(request, 'products/category_products.html', context)