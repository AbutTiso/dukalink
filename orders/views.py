from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.urls import reverse
import json
from products.models import Product
from orders.cart import Cart
from dashboard.views import order_detail
from functools import wraps

# ===== CUSTOM DECORATOR FOR AJAX LOGIN REQUIREMENT =====
def ajax_login_required(view_func):
    """Decorator for AJAX views that returns JSON login required response"""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({
                'success': False,
                'login_required': True,
                'error': 'Please login to continue',
                'login_url': '/accounts/login/',
                'register_url': '/accounts/register/'
            }, status=403)
        return view_func(request, *args, **kwargs)
    return wrapper

# Your existing views
def track_order(request, order_code):
    return render(request, "orders/track_order.html", {"order_code": order_code})

def cart_add(request, product_id):
    """Regular view - redirects back to shop with quantity support"""
    cart = Cart(request)
    product = get_object_or_404(Product, id=product_id)
    
    # Get quantity from request (default to 1)
    quantity = int(request.POST.get('quantity', request.GET.get('quantity', 1)))
    
    # Check if product is available
    if not product.is_available:
        messages.error(request, f"{product.name} is not available.")
        return redirect("shops:shop_detail", slug=product.business.slug)
    
    # Check if product is in stock
    if product.stock <= 0:
        messages.error(request, f"{product.name} is out of stock.")
        return redirect("shops:shop_detail", slug=product.business.slug)
    
    # Get current quantity in cart
    current_qty = 0
    if str(product_id) in cart.cart:
        current_qty = cart.cart[str(product_id)]['quantity']
    
    # Check if adding more would exceed stock
    if current_qty + quantity > product.stock:
        messages.error(request, f"Only {product.stock} of {product.name} available. You already have {current_qty} in cart.")
        return redirect("shops:shop_detail", slug=product.business.slug)
    
    # Add to cart with specified quantity
    cart.add(product, quantity=quantity)
    
    # Success message based on quantity
    if quantity > 1:
        messages.success(request, f"{quantity} x {product.name} added to cart.")
    else:
        messages.success(request, f"{product.name} added to cart.")
    
    # Check if it's an AJAX request
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'success': True,
            'cart_count': len(cart),
            'cart_total': float(cart.get_total()),
            'message': f"{quantity} x {product.name} added to cart.",
            'stock_left': product.stock - (current_qty + quantity)
        })
    
    return redirect("shops:shop_detail", slug=product.business.slug)

def cart_remove(request, product_id):
    """Regular view - redirects to cart"""
    cart = Cart(request)
    product = get_object_or_404(Product, id=product_id)
    cart.remove(product)
    messages.success(request, f"{product.name} removed from cart.")
    
    # Check if it's an AJAX request
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'success': True,
            'cart_count': len(cart),
            'cart_total': float(cart.get_total()),
            'message': f"{product.name} removed from cart."
        })
    
    return redirect("orders:cart_detail")

def cart_detail(request):
    cart = Cart(request)
    
    # Check stock for all items in cart and show warnings
    stock_warnings = []
    for product_id, item_data in cart.cart.items():
        try:
            product = Product.objects.get(id=product_id)
            if product.stock < item_data['quantity']:
                stock_warnings.append(f"{product.name}: Only {product.stock} available, you have {item_data['quantity']} in cart")
        except Product.DoesNotExist:
            stock_warnings.append(f"Product with ID {product_id} not found")
    
    return render(request, "orders/cart_detail.html", {
        "cart": cart,
        "stock_warnings": stock_warnings
    })

# ===== NEW AJAX ENDPOINTS FOR REAL-TIME CART UPDATES =====

@require_POST
@csrf_exempt
def cart_add_ajax(request):
    """AJAX view to add item to cart without page refresh with quantity support"""
    try:
        data = json.loads(request.body) if request.body else {}
        product_id = data.get('product_id')
        quantity = int(data.get('quantity', 1))
        
        if not product_id:
            return JsonResponse({
                'success': False,
                'error': 'Product ID is required'
            }, status=400)
        
        cart = Cart(request)
        product = get_object_or_404(Product, id=product_id)
        
        # Check if product is available
        if not product.is_available:
            return JsonResponse({
                'success': False,
                'error': f"{product.name} is not available"
            }, status=400)
        
        # Check stock
        if product.stock <= 0:
            return JsonResponse({
                'success': False,
                'error': f"{product.name} is out of stock"
            }, status=400)
        
        # Get current quantity in cart
        current_qty = 0
        if str(product_id) in cart.cart:
            current_qty = cart.cart[str(product_id)]['quantity']
        
        # Check if adding would exceed stock
        if current_qty + quantity > product.stock:
            return JsonResponse({
                'success': False,
                'error': f"Only {product.stock} of {product.name} available. You already have {current_qty} in cart."
            }, status=400)
        
        # Add product with specified quantity
        cart.add(product, quantity=quantity)
        
        return JsonResponse({
            'success': True,
            'cart_count': len(cart),
            'cart_total': float(cart.get_total()),
            'message': f"{quantity} x {product.name} added to cart.",
            'product_id': product_id,
            'quantity': quantity,
            'stock_left': product.stock - (current_qty + quantity)
        })
        
    except Product.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Product not found'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)

@require_POST
@csrf_exempt
def cart_remove_ajax(request):
    """AJAX view to remove item from cart"""
    try:
        data = json.loads(request.body) if request.body else {}
        product_id = data.get('product_id')
        
        if not product_id:
            return JsonResponse({
                'success': False,
                'error': 'Product ID is required'
            }, status=400)
        
        cart = Cart(request)
        product = get_object_or_404(Product, id=product_id)
        cart.remove(product)
        
        return JsonResponse({
            'success': True,
            'cart_count': len(cart),
            'cart_total': float(cart.get_total()),
            'message': f"{product.name} removed from cart.",
            'product_id': product_id
        })
        
    except Product.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Product not found'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)

@require_POST
@csrf_exempt
def cart_update_ajax(request):
    """AJAX view to update item quantity with stock validation"""
    try:
        data = json.loads(request.body) if request.body else {}
        product_id = data.get('product_id')
        quantity = int(data.get('quantity', 1))
        
        if not product_id:
            return JsonResponse({
                'success': False,
                'error': 'Product ID is required'
            }, status=400)
        
        cart = Cart(request)
        product = get_object_or_404(Product, id=product_id)
        
        # Validate stock for new quantity
        if quantity > product.stock:
            return JsonResponse({
                'success': False,
                'error': f"Cannot set quantity to {quantity}. Only {product.stock} available."
            }, status=400)
        
        # Get current quantity
        current_qty = 0
        if str(product_id) in cart.cart:
            current_qty = cart.cart[str(product_id)]['quantity']
        
        if quantity <= 0:
            # Remove if quantity is 0 or negative
            cart.remove(product)
            item_total = 0
        else:
            # Update directly
            if str(product.id) in cart.cart:
                cart.cart[str(product.id)]['quantity'] = quantity
                cart.save()
            
            item_total = float(product.price * quantity)
        
        return JsonResponse({
            'success': True,
            'cart_count': len(cart),
            'cart_total': float(cart.get_total()),
            'item_total': item_total,
            'product_id': product_id,
            'quantity': quantity,
            'stock_left': product.stock - quantity
        })
        
    except Product.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Product not found'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)

def cart_count_ajax(request):
    """Get current cart count and total via AJAX"""
    cart = Cart(request)
    return JsonResponse({
        'success': True,
        'cart_count': len(cart),
        'cart_total': float(cart.get_total())
    })

# ===== EXISTING API ENDPOINTS - Keep these =====

@require_POST
@csrf_exempt
def cart_add_api(request):
    """API endpoint to add product to cart - Works with /api/cart/add/ AND /orders/api/cart/add/"""
    return handle_cart_add_api(request)

@require_POST
@csrf_exempt
def cart_add_api_alt(request):
    """Alternative API endpoint - Works with /orders/cart/add/<id>/ for AJAX"""
    try:
        # Try to get product_id from URL first
        if hasattr(request, 'resolver_match') and request.resolver_match:
            product_id = request.resolver_match.kwargs.get('product_id')
        else:
            # Fallback to JSON body
            data = json.loads(request.body) if request.body else {}
            product_id = data.get('product_id')
        
        if not product_id:
            return JsonResponse({
                'success': False,
                'error': 'Product ID is required'
            }, status=400)
        
        # Get quantity from request
        data = json.loads(request.body) if request.body else {}
        quantity = int(data.get('quantity', 1))
            
        cart = Cart(request)
        product = get_object_or_404(Product, id=product_id)
        
        # Add product with specified quantity
        cart.add(product, quantity=quantity)
        
        return JsonResponse({
            'success': True,
            'cart_count': len(cart),
            'cart_total': float(cart.get_total()),
            'message': f"{quantity} x {product.name} added to cart.",
            'quantity': quantity
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)

def handle_cart_add_api(request):
    """Shared logic for cart addition"""
    try:
        data = json.loads(request.body) if request.body else {}
        product_id = data.get('product_id')
        quantity = int(data.get('quantity', 1))
        
        if not product_id:
            return JsonResponse({
                'success': False,
                'error': 'Product ID is required'
            }, status=400)
        
        cart = Cart(request)
        product = get_object_or_404(Product, id=product_id)
        
        # Add product with specified quantity
        cart.add(product, quantity=quantity)
        
        return JsonResponse({
            'success': True,
            'cart_count': len(cart),
            'cart_total': float(cart.get_total()),
            'message': f"{quantity} x {product.name} added to cart.",
            'quantity': quantity
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)

@require_POST
@csrf_exempt
def cart_remove_api(request):
    """API endpoint to remove product from cart"""
    try:
        data = json.loads(request.body)
        product_id = data.get('product_id')
        
        if not product_id:
            return JsonResponse({
                'success': False,
                'error': 'Product ID is required'
            }, status=400)
        
        cart = Cart(request)
        product = get_object_or_404(Product, id=product_id)
        cart.remove(product)
        
        return JsonResponse({
            'success': True,
            'cart_count': len(cart),
            'cart_total': float(cart.get_total()),
            'message': f"{product.name} removed from cart."
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)

def cart_count_api(request):
    """API endpoint to get cart count"""
    cart = Cart(request)
    return JsonResponse({
        'success': True,
        'cart_count': len(cart),
        'cart_total': str(cart.get_total()) if hasattr(cart, 'get_total') else '0'
    })

# ===== DUMMY ENDPOINTS FOR SERVICE WORKER =====

def dummy_api(request):
    """Silence service worker requests"""
    return JsonResponse({})

def dummy_notifications(request):
    """Silence notification requests"""
    return JsonResponse({'notifications': []})

def cart_decrement(request, product_id):
    """Decrease product quantity by 1"""
    cart = Cart(request)
    product = get_object_or_404(Product, id=product_id)
    
    # Get current quantity from cart
    product_id_str = str(product_id)
    if product_id_str in cart.cart:
        current_qty = cart.cart[product_id_str]['quantity']
        if current_qty > 1:
            # Decrease by 1
            cart.cart[product_id_str]['quantity'] = current_qty - 1
            cart.save()
        else:
            # Remove if quantity would be 0
            cart.remove(product)
    
    messages.success(request, f"Cart updated.")
    
    # Check if AJAX
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'success': True,
            'cart_count': len(cart),
            'cart_total': float(cart.get_total())
        })
    
    return redirect("orders:cart_detail")

# orders/views.py (continued)
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import Order

@login_required
def customer_order_detail(request, order_id):
    """Customer view their own order"""
    order = get_object_or_404(Order, id=order_id, customer=request.user)
    
    return render(request, 'orders/customer_order_detail.html', {
        'order': order,
        'order_items': order.order_items.all()
    })

@login_required
def confirm_pochi_payment(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    
    if request.method == 'POST':
        transaction_code = request.POST.get('transaction_code')
        screenshot = request.FILES.get('payment_screenshot')
        
        # Validate transaction code format (MPesa codes start with letters)
        if not transaction_code or len(transaction_code) < 8:
            messages.error(request, 'Please enter a valid M-Pesa transaction code')
            return redirect('orders:pochi_payment_instructions', order_id=order.id)
        
        # Save to order
        order.transaction_code = transaction_code
        if screenshot:
            order.payment_screenshot = screenshot
        order.save()
        
        # Mark as pending verification
        messages.success(request, 'Payment information submitted! Vendor will confirm shortly.')
        
        return redirect('orders:order_detail', order_id=order.id)
    
    return redirect('orders:pochi_payment_instructions', order_id=order.id)


# ===== CART CLEAR AJAX ENDPOINT =====
@require_POST
@csrf_exempt
def cart_clear_ajax(request):
    """AJAX endpoint to clear the entire cart"""
    try:
        cart = Cart(request)
        cart.clear()
        
        return JsonResponse({
            'success': True,
            'cart_count': 0,
            'cart_total': 0,
            'message': 'Cart cleared successfully'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)