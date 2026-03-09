import sys
import traceback
import json
import logging  # ADD THIS IMPORT
from datetime import timedelta

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Sum, Q, F
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods, require_GET
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.contrib import messages

from accounts.models import Business
from products.models import Product, Category
from products.forms import ProductForm
from orders.models import Order, OrderItem

# Configure logger
logger = logging.getLogger(__name__)


# ================ VENDOR DASHBOARD ================
@login_required
def vendor_dashboard(request):
    """Main vendor dashboard"""
    try:
        business = Business.objects.get(owner=request.user)
    except Business.DoesNotExist:
        messages.error(request, "You need to register a business first!")
        return redirect("accounts:register_business")
    
    # Get vendor's products and orders
    vendor_products = Product.objects.filter(business=business)
    product_ids = vendor_products.values_list('id', flat=True)
    
    vendor_order_items = OrderItem.objects.filter(product_id__in=product_ids)
    order_ids = vendor_order_items.values_list('order_id', flat=True).distinct()
    orders = Order.objects.filter(id__in=order_ids).order_by('-created_at')
    
    # Calculate stats
    total_orders = orders.count()
    pending_orders = orders.filter(status='pending').count()
    processing_orders = orders.filter(status='processing').count()
    
    completed_items = vendor_order_items.filter(order__status='completed', order__paid=True)
    total_revenue = sum(item.price * item.quantity for item in completed_items)
    
    # Growth calculation
    last_month = timezone.now() - timedelta(days=30)
    previous_count = orders.filter(created_at__lt=last_month).count()
    orders_growth = ((total_orders - previous_count) / previous_count * 100) if previous_count > 0 else (100 if total_orders > 0 else 0)
    
    # Pagination
    from django.core.paginator import Paginator
    paginator = Paginator(orders, 10)
    page_number = request.GET.get('page')
    page_orders = paginator.get_page(page_number)
    
    # Prepare order data
    order_data_dict = {}
    for item in vendor_order_items:
        order_id = item.order_id
        if order_id not in order_data_dict:
            order_data_dict[order_id] = {
                'order': item.order,
                'vendor_items': [],
                'total_amount': 0
            }
        order_data_dict[order_id]['vendor_items'].append(item)
        order_data_dict[order_id]['total_amount'] += item.price * item.quantity
    
    page_order_data = []
    for order in page_orders:
        if order.id in order_data_dict:
            page_order_data.append(order_data_dict[order.id])
    
    context = {
        'business': business,
        'orders': page_orders,
        'order_data': page_order_data,
        'total_orders': total_orders,
        'pending_orders': pending_orders,
        'processing_orders': processing_orders,
        'total_revenue': total_revenue,
        'orders_growth': round(orders_growth, 1),
        'vendor_products_count': vendor_products.count(),
        'low_stock_products': vendor_products.filter(stock__lte=5, stock__gt=0)[:5],
        'out_of_stock': vendor_products.filter(stock=0).count(),
        'verification_status': business.verification_status,
        'days_on_platform': business.days_since_registration,
    }
    
    return render(request, 'dashboard/vendor_dashboard.html', context)


# ================ API ENDPOINTS ================
@login_required
@require_http_methods(["POST"])
@csrf_exempt
def update_order_status(request):
    """AJAX endpoint to update order status with stock management"""
    try:
        data = json.loads(request.body)
        order_id = data.get('order_id')
        new_status = data.get('status')
        note = data.get('note', '')
        notify_whatsapp = data.get('notify_whatsapp', False)
        notify_sms = data.get('notify_sms', False)
        
        # Get vendor's business
        business = Business.objects.filter(owner=request.user).first()
        if not business:
            return JsonResponse({
                'success': False,
                'error': 'No business found'
            }, status=403)
        
        # Verify vendor owns products in this order
        order = Order.objects.get(id=order_id)
        vendor_products = Product.objects.filter(business=business)
        product_ids = vendor_products.values_list('id', flat=True)
        
        order_items = OrderItem.objects.filter(
            order=order,
            product_id__in=product_ids
        )
        
        if not order_items.exists():
            return JsonResponse({
                'success': False,
                'error': 'You do not have permission to update this order'
            }, status=403)
        
        # Handle stock changes based on status transition
        old_status = order.status
        
        # If order is being cancelled, restore stock
        if new_status == 'cancelled' and old_status != 'cancelled':
            for item in order_items:
                product = item.product
                product.stock += item.quantity
                product.save()
                logger.info(f"Restored stock for {product.name}: {product.stock}")
            messages.info(request, f"Stock restored for cancelled order #{order.id}")
        
        # If order was cancelled and now being reactivated, reduce stock again
        elif old_status == 'cancelled' and new_status != 'cancelled':
            for item in order_items:
                product = item.product
                # Check if enough stock is available
                if product.stock < item.quantity:
                    return JsonResponse({
                        'success': False,
                        'error': f'Cannot reactivate order. Insufficient stock for {product.name}. Available: {product.stock}, Needed: {item.quantity}'
                    }, status=400)
                
                product.stock -= item.quantity
                product.save()
                logger.info(f"Reduced stock for {product.name}: {product.stock}")
        
        # Update status
        order.status = new_status
        
        # Auto-mark as paid when status is 'completed'
        if new_status == 'completed' and not order.paid:
            order.paid = True
            order.payment_confirmed_at = timezone.now()
            order.payment_confirmed_by = request.user
        
        order.save()
        
        # Get status display name
        status_display = dict(Order.STATUS_CHOICES).get(new_status, new_status.title())
        
        # Determine message based on whether paid was also updated
        message = f'Order #{order.id} status updated to {status_display}'
        if new_status == 'completed' and not order.paid:
            message += ' and marked as paid'
        
        # You can implement these notification functions later
        if notify_whatsapp:
            # send_whatsapp_notification(order, new_status, note)
            pass
        if notify_sms:
            # send_sms_notification(order, new_status, note)
            pass
        
        return JsonResponse({
            'success': True,
            'message': message,
            'order_id': order.id,
            'new_status': new_status,
            'status_display': status_display,
            'paid': order.paid
        })
        
    except Order.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Order not found'
        }, status=404)
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON data'
        }, status=400)
    except Exception as e:
        print(f"Error updating order status: {str(e)}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
def get_dashboard_stats(request):
    """AJAX endpoint to get updated statistics"""
    try:
        # Get vendor's business
        business = Business.objects.filter(owner=request.user).first()
        if not business:
            return JsonResponse({
                'success': False,
                'error': 'No business found'
            }, status=403)
        
        # Get vendor's products and orders
        vendor_products = Product.objects.filter(business=business)
        product_ids = vendor_products.values_list('id', flat=True)
        
        vendor_order_items = OrderItem.objects.filter(product_id__in=product_ids)
        order_ids = vendor_order_items.values_list('order_id', flat=True).distinct()
        orders = Order.objects.filter(id__in=order_ids)
        
        # Calculate real-time stats
        total_orders = orders.count()
        pending_orders = orders.filter(status='pending').count()
        processing_orders = orders.filter(status='processing').count()
        completed_orders = orders.filter(status='completed').count()
        
        # Calculate total revenue - using completed AND paid
        completed_items = vendor_order_items.filter(order__status='completed', order__paid=True)
        total_revenue = 0
        for item in completed_items:
            total_revenue += item.price * item.quantity
        
        # Calculate growth
        last_month = timezone.now() - timedelta(days=30)
        previous_orders = orders.filter(created_at__lt=last_month).count()
        
        if previous_orders > 0:
            orders_growth = ((total_orders - previous_orders) / previous_orders) * 100
        else:
            orders_growth = 100 if total_orders > 0 else 0
        
        # Get recent orders for real-time updates
        recent_orders = orders.order_by('-created_at')[:5]
        recent_orders_data = []
        
        for order in recent_orders:
            order_items = vendor_order_items.filter(order=order)
            items_data = []
            order_total = 0
            for item in order_items:
                item_total = item.price * item.quantity
                order_total += item_total
                items_data.append({
                    'product_name': item.product.name,
                    'quantity': item.quantity,
                    'price': float(item.price),
                    'total': float(item_total)
                })
            
            recent_orders_data.append({
                'id': order.id,
                'customer_name': order.customer_name,
                'customer_phone': order.customer_phone,
                'status': order.status,
                'paid': order.paid,
                'status_display': order.get_status_display(),
                'created_at': order.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                'total_amount': float(order_total),
                'items': items_data
            })
        
        return JsonResponse({
            'success': True,
            'stats': {
                'total_orders': total_orders,
                'pending_orders': pending_orders,
                'processing_orders': processing_orders,
                'completed_orders': completed_orders,
                'total_revenue': float(total_revenue),
                'orders_growth': round(orders_growth, 1),
            },
            'recent_orders': recent_orders_data,
            'timestamp': timezone.now().isoformat()
        })
        
    except Exception as e:
        print(f"Error in get_dashboard_stats: {str(e)}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
def order_detail_api(request, order_id):
    """AJAX endpoint to get order details"""
    try:
        # Get vendor's business
        business = Business.objects.filter(owner=request.user).first()
        if not business:
            return JsonResponse({
                'success': False,
                'error': 'No business found'
            }, status=403)
        
        order = get_object_or_404(Order, id=order_id)
        
        # Verify vendor has access
        vendor_products = Product.objects.filter(business=business)
        product_ids = vendor_products.values_list('id', flat=True)
        
        order_items = OrderItem.objects.filter(
            order=order,
            product_id__in=product_ids
        )
        
        if not order_items.exists():
            return JsonResponse({
                'success': False,
                'error': 'Access denied'
            }, status=403)
        
        items_data = []
        order_total = 0
        for item in order_items:
            item_total = item.price * item.quantity
            order_total += item_total
            items_data.append({
                'product_id': item.product.id,
                'product_name': item.product.name,
                'quantity': item.quantity,
                'price': float(item.price),
                'total': float(item_total),
                'current_stock': item.product.stock  # Include current stock
            })
        
        # Format date safely
        created_at_formatted = ''
        if order.created_at:
            created_at_formatted = order.created_at.strftime('%B %d, %Y at %H:%M')
        
        return JsonResponse({
            'success': True,
            'order': {
                'id': order.id,
                'customer_name': order.customer_name or '',
                'customer_phone': order.customer_phone or '',
                'status': order.status,
                'paid': order.paid,
                'status_display': order.get_status_display(),
                'created_at': created_at_formatted,
                'total_amount': float(order_total),
                'items': items_data
            }
        })
        
    except Order.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Order not found'
        }, status=404)
    except Exception as e:
        print(f"❌ API Error in order_detail_api: {str(e)}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


# ================ ORDER PAGES ================
@login_required
def order_detail(request, order_id):
    """Full order detail page"""
    business = Business.objects.filter(owner=request.user).first()
    if not business:
        return redirect("accounts:register_business")
    
    order = get_object_or_404(Order, id=order_id)
    vendor_products = Product.objects.filter(business=business)
    product_ids = vendor_products.values_list('id', flat=True)
    
    order_items = OrderItem.objects.filter(
        order=order,
        product_id__in=product_ids
    )
    
    if not order_items.exists():
        return redirect("dashboard:vendor_dashboard")
    
    # Calculate total amount for vendor's items
    total_amount = 0
    for item in order_items:
        total_amount += item.price * item.quantity
    
    return render(request, "dashboard/order_detail.html", {
        "order": order,
        "order_items": order_items,
        "total_amount": total_amount,
        "business": business,
        "paid": order.paid
    })


@login_required
def confirm_vendor_payment(request, order_id):
    """Vendor confirms they received the payment"""
    if request.method == 'POST':
        try:
            business = Business.objects.get(owner=request.user)
        except Business.DoesNotExist:
            return JsonResponse({
                'success': False, 
                'error': "You don't have a registered business"
            })
        
        order = get_object_or_404(Order, id=order_id)
        
        # Verify this vendor has products in this order
        if not OrderItem.objects.filter(order=order, product__business=business).exists():
            return JsonResponse({
                'success': False, 
                'error': 'You do not have permission to confirm this payment'
            })
        
        try:
            data = json.loads(request.body)
            action = data.get('action')
        except:
            action = request.POST.get('action')
        
        if action == 'confirm':
            order.paid = True
            order.payment_confirmed_by = request.user
            order.payment_confirmed_at = timezone.now()
            order.status = 'processing'
            order.save()
            
            return JsonResponse({
                'success': True,
                'message': f'Payment for Order #{order.id} confirmed!'
            })
            
        elif action == 'reject':
            reason = request.POST.get('rejection_reason', '')
            # Add a note to order
            if hasattr(order, 'notes'):
                order.notes = f'Payment rejected: {reason}'
            order.save()
            
            return JsonResponse({
                'success': True,
                'message': f'Payment for Order #{order.id} rejected'
            })
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'})


@login_required
def order_receipt(request, order_id):
    """Print receipt page"""
    business = Business.objects.filter(owner=request.user).first()
    if not business:
        return redirect("accounts:register_business")
    
    order = get_object_or_404(Order, id=order_id)
    vendor_products = Product.objects.filter(business=business)
    product_ids = vendor_products.values_list('id', flat=True)
    
    order_items = OrderItem.objects.filter(
        order=order,
        product_id__in=product_ids
    )
    
    if not order_items.exists():
        return redirect("dashboard:vendor_dashboard")
    
    # Calculate total amount
    total_amount = 0
    for item in order_items:
        total_amount += item.price * item.quantity
    
    return render(request, "dashboard/receipt.html", {
        "order": order,
        "order_items": order_items,
        "total_amount": total_amount,
        "business": business,
        "paid": order.paid
    })


# ================ PRODUCT MANAGEMENT ================
@login_required
def dashboard_home(request):
    """MAIN DASHBOARD - Products & Business Management"""
    business = Business.objects.filter(owner=request.user).first()
    if not business:
        return redirect("accounts:register_business")

    # Get category filter from request
    category_id = request.GET.get('category')
    
    # Get stock parameter for quick update
    quick_stock = request.GET.get('stock')
    quick_product_id = request.GET.get('product_id')
    
    # Base queryset
    products = Product.objects.filter(business=business).select_related('category')
    
    # Apply category filter if specified
    if category_id:
        products = products.filter(category_id=category_id)
    
    # Get all categories for the filter UI
    categories = Category.objects.all().order_by('name')
    
    # Get all orders that contain this vendor's products
    vendor_order_items = OrderItem.objects.filter(
        product__business=business
    ).select_related('order', 'product')
    
    # Get unique orders
    order_ids = vendor_order_items.values_list('order_id', flat=True).distinct()
    orders = Order.objects.filter(id__in=order_ids)
    
    # Calculate total orders
    total_orders = orders.count()
    
    # Calculate total revenue (completed AND paid orders only)
    completed_items = vendor_order_items.filter(order__status='completed', order__paid=True)
    total_revenue = 0
    for item in completed_items:
        total_revenue += item.quantity * item.price
    
    # Count unique customers
    total_customers = orders.values('customer_phone').distinct().count()
    
    # Count pending orders
    pending_orders = orders.filter(status='pending').count()
    
    # Calculate product percentage (assuming 20 products is 100%)
    product_percentage = min((products.count() / 20) * 100, 100) if products.count() > 0 else 0
    
    context = {
        'business': business,
        'products': products,
        'categories': categories,
        'selected_category': int(category_id) if category_id else None,
        'total_orders': total_orders,
        'total_revenue': f"{total_revenue:,.0f}",
        'total_customers': total_customers,
        'pending_orders': pending_orders,
        'product_percentage': product_percentage,
    }
    
    return render(request, "dashboard/home.html", context)


@login_required
def product_add(request):
    business = Business.objects.filter(owner=request.user).first()
    if not business:
        return redirect("accounts:register_business")

    if request.method == "POST":
        form = ProductForm(request.POST, request.FILES)
        if form.is_valid():
            product = form.save(commit=False)
            product.business = business
            
            # Check if both category and new_category were provided
            if form.cleaned_data.get('new_category') and form.cleaned_data.get('category'):
                messages.warning(
                    request, 
                    f"Category '{form.cleaned_data['new_category']}' was ignored. "
                    f"Using selected category: {form.cleaned_data['category'].name}"
                )
            
            product.save()
            messages.success(request, "Product added successfully!")
            return redirect("dashboard:dashboard_home")
        else:
            # Form has errors, will display in template
            pass
    else:
        form = ProductForm()

    # Get all categories for the template
    categories = Category.objects.all().order_by('name')
    
    return render(request, "dashboard/product_form.html", {
        "form": form, 
        "title": "Add Product",
        "business": business,
        "categories": categories,
        "action": "add"
    })


@login_required
def product_edit(request, product_id):
    """Edit an existing product"""
    business = Business.objects.filter(owner=request.user).first()
    if not business:
        messages.error(request, "You need to register a business first!")
        return redirect("accounts:register_business")
    
    product = get_object_or_404(Product, id=product_id, business=business)
    
    # Handle quick stock update from URL parameter
    quick_stock = request.GET.get('stock')
    if quick_stock is not None:
        try:
            new_stock = int(quick_stock)
            if new_stock >= 0:
                product.stock = new_stock
                product.save()
                messages.success(request, f"Stock updated to {new_stock} for {product.name}")
                return redirect('dashboard:dashboard_home')
        except ValueError:
            messages.error(request, "Invalid stock value")

    if request.method == "POST":
        form = ProductForm(request.POST, request.FILES, instance=product)
        if form.is_valid():
            # Check if both category and new_category were provided
            if form.cleaned_data.get('new_category') and form.cleaned_data.get('category'):
                messages.warning(
                    request, 
                    f"Category '{form.cleaned_data['new_category']}' was ignored. "
                    f"Using selected category: {form.cleaned_data['category'].name}"
                )
            
            form.save()
            messages.success(request, "Product updated successfully!")
            return redirect("dashboard:dashboard_home")
    else:
        form = ProductForm(instance=product)

    categories = Category.objects.all().order_by('name')
    
    return render(request, "dashboard/product_form.html", {
        "form": form, 
        "title": "Edit Product",
        "business": business,
        "categories": categories,
        "product": product,
        "action": "edit"
    })


@login_required
def product_delete(request, product_id):
    """Delete a product"""
    business = Business.objects.filter(owner=request.user).first()
    if not business:
        messages.error(request, "You need to register a business first!")
        return redirect("accounts:register_business")
    
    product = get_object_or_404(Product, id=product_id, business=business)
    
    if request.method == "POST":
        product_name = product.name
        product.delete()
        messages.success(request, f"Product '{product_name}' deleted successfully!")
        return redirect("dashboard:dashboard_home")
    
    return render(request, "dashboard/product_confirm_delete.html", {
        "product": product,
        "business": business
    })


# ================ ADMIN/API ENDPOINTS ================
@require_GET
def get_latest_orders(request):
    """API endpoint for fetching latest orders (for admin)"""
    
    # Get timestamp from request to fetch only new orders
    last_update = request.GET.get('last_update')
    
    if last_update:
        # Fetch orders updated after timestamp
        orders = Order.objects.filter(updated_at__gt=last_update)
    else:
        # Fetch recent orders (last 5 minutes)
        recent = timezone.now() - timedelta(minutes=5)
        orders = Order.objects.filter(updated_at__gte=recent)
    
    orders_data = []
    for order in orders:
        # Calculate order total
        order_total = 0
        for item in order.order_items.all():
            order_total += item.quantity * item.price
            
        orders_data.append({
            'id': order.id,
            'order_id': f"#{order.id:06d}",
            'customer': {
                'username': order.customer.username if order.customer else order.customer_name,
                'initial': (order.customer.username[0].upper() if order.customer and order.customer.username 
                           else order.customer_name[0].upper() if order.customer_name else '?')
            },
            'vendor': {
                'username': order.vendor.username if order.vendor else 'Unknown'
            },
            'items_count': order.order_items.count(),
            'total_amount': float(order_total),
            'status': order.status,
            'paid': order.paid,
            'created_at': order.created_at.strftime('%b %d, %Y %H:%M'),
            'updated_at': order.updated_at.isoformat()
        })
    
    # Get all orders for counts
    all_orders = Order.objects.all()
    
    return JsonResponse({
        'orders': orders_data,
        'orders_count': all_orders.count(),
        'pending_count': all_orders.filter(status='pending').count(),
        'processing_count': all_orders.filter(status='processing').count(),
        'completed_count': all_orders.filter(status='completed').count(),
        'cancelled_count': all_orders.filter(status='cancelled').count(),
        'timestamp': timezone.now().isoformat()
    })