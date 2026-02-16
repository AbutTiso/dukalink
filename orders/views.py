from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.urls import reverse
import json
from products.models import Product
from orders.cart import Cart
from dashboard.views import order_detail  # Import the existing order_detail view from dashboard

# Your existing views
def track_order(request, order_code):
    return render(request, "orders/track_order.html", {"order_code": order_code})

def cart_add(request, product_id):
    """Regular view - redirects back to shop"""
    cart = Cart(request)
    product = get_object_or_404(Product, id=product_id)
    cart.add(product)
    messages.success(request, f"{product.name} added to cart.")
    
    # Check if it's an AJAX request
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'success': True,
            'cart_count': len(cart),
            'cart_total': float(cart.get_total()),
            'message': f"{product.name} added to cart."
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
    return render(request, "orders/cart_detail.html", {"cart": cart})

# ===== NEW AJAX ENDPOINTS FOR REAL-TIME CART UPDATES =====

@require_POST
@csrf_exempt
def cart_add_ajax(request):
    """AJAX view to add item to cart without page refresh"""
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
        for i in range(quantity):
            cart.add(product)
        
        return JsonResponse({
            'success': True,
            'cart_count': len(cart),
            'cart_total': float(cart.get_total()),
            'message': f"{product.name} added to cart.",
            'product_id': product_id,
            'quantity': quantity
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
    """AJAX view to update item quantity"""
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
        
        # Get current quantity
        current_qty = 0
        if str(product_id) in cart.cart:
            current_qty = cart.cart[str(product_id)]['quantity']
        
        if quantity <= 0:
            # Remove if quantity is 0 or negative
            cart.remove(product)
            item_total = 0
        else:
            # Calculate difference and update
            diff = quantity - current_qty
            if diff > 0:
                for i in range(diff):
                    cart.add(product)
            elif diff < 0:
                # Need to decrease quantity - we'd need a decrement method
                # For now, we'll just update directly if you have quantity field
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
            'quantity': quantity
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
            
        cart = Cart(request)
        product = get_object_or_404(Product, id=product_id)
        cart.add(product)
        
        return JsonResponse({
            'success': True,
            'cart_count': len(cart),
            'cart_total': float(cart.get_total()),
            'message': f"{product.name} added to cart."
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
        
        if not product_id:
            return JsonResponse({
                'success': False,
                'error': 'Product ID is required'
            }, status=400)
        
        cart = Cart(request)
        product = get_object_or_404(Product, id=product_id)
        cart.add(product)
        
        return JsonResponse({
            'success': True,
            'cart_count': len(cart),
            'cart_total': float(cart.get_total()),
            'message': f"{product.name} added to cart."
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
            # Decrease by 1 - need to update cart
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
# orders/views.py
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
        
        # Optional: Send notification to vendor
        # send_vendor_notification(order)
        
        return redirect('orders:order_detail', order_id=order.id)
    
    return redirect('orders:pochi_payment_instructions', order_id=order.id)