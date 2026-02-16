# dashboard/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Sum, Q
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from datetime import timedelta
import json
from django.contrib import messages 
from accounts.models import Business
from products.models import Product
from products.forms import ProductForm
from orders.models import Order, OrderItem

# ================ ORDERS / VENDOR DASHBOARD ================
from django.db.models import Sum, F
@login_required
def vendor_dashboard(request):
    """Main vendor dashboard view with real data"""
    
    # Get vendor's business
    try:
        business = Business.objects.get(owner=request.user)
    except Business.DoesNotExist:
        messages.error(request, "You need to register a business first!")
        return redirect("accounts:register_business")
    
    # ============== VERIFICATION CHECK ==============
    # Check if vendor is verified
    if not business.is_verified:
        if business.verification_status == 'pending':
            messages.warning(
                request, 
                '⏳ Your business is pending verification. Please upload your required documents to complete registration.'
            )
            return redirect('accounts:upload_documents', business_id=business.id)
            
        elif business.verification_status == 'under_review':
            messages.info(
                request, 
                '📋 Your documents are currently under review by our admin team. You will be notified once verified. This usually takes 1-2 business days.'
            )
            return redirect('accounts:document_status')
            
        elif business.verification_status == 'rejected':
            messages.error(
                request, 
                f'❌ Your verification was rejected. Reason: {business.verification_notes or "Documents did not meet the required Kenyan business regulations."} Please upload valid documents.'
            )
            return redirect('accounts:upload_documents', business_id=business.id)
            
        elif business.verification_status == 'info_needed':
            messages.warning(
                request, 
                f'ℹ️ Additional information required: {business.verification_notes or "Please upload missing documents."}'
            )
            return redirect('accounts:upload_documents', business_id=business.id)
    
    # Check if business is rejected
    if business.is_rejected:
        messages.error(
            request, 
            '❌ Your business account has been rejected. Please contact support for more information.'
        )
        return redirect('home')
    
    # Check if business is inactive
    if not business.is_active:
        messages.error(
            request, 
            '❌ Your business account is currently inactive. Please contact support.'
        )
        return redirect('home')
    
    # Check if documents are complete (additional safety check)
    if not business.documents_complete:
        missing_docs = business.missing_documents
        messages.warning(
            request,
            f'📋 Your document upload is incomplete. Missing: {", ".join(missing_docs[:3])}{" and more" if len(missing_docs) > 3 else ""}'
        )
        return redirect('accounts:upload_documents', business_id=business.id)
    
    # ============== DASHBOARD DATA ==============
    # Get vendor's products
    vendor_products = Product.objects.filter(business=business)
    product_ids = vendor_products.values_list('id', flat=True)
    
    # Get orders containing vendor's products
    vendor_order_items = OrderItem.objects.filter(
        product_id__in=product_ids
    ).select_related('order', 'product')
    
    # Get unique orders from these items
    order_ids = vendor_order_items.values_list('order_id', flat=True).distinct()
    orders = Order.objects.filter(id__in=order_ids).prefetch_related(
        'order_items', 'order_items__product'
    ).order_by('-created_at')
    
    # Calculate statistics
    total_orders = orders.count()
    pending_orders = orders.filter(status='pending').count()
    processing_orders = orders.filter(status='processing').count()
    completed_orders = orders.filter(status='completed').count()
    cancelled_orders = orders.filter(status='cancelled').count()
    
    # Calculate revenue (only completed orders)
    completed_order_items = vendor_order_items.filter(order__status='completed')
    total_revenue = 0
    for item in completed_order_items:
        total_revenue += item.price * item.quantity
    
    # Calculate growth from last month
    last_month = timezone.now() - timedelta(days=30)
    previous_orders_count = orders.filter(created_at__lt=last_month).count()
    
    if previous_orders_count > 0:
        orders_growth = ((total_orders - previous_orders_count) / previous_orders_count) * 100
    else:
        orders_growth = 100 if total_orders > 0 else 0
    
    # Prepare order data with vendor-specific items
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
    
    # Pagination
    from django.core.paginator import Paginator
    paginator = Paginator(orders, 10)
    page_number = request.GET.get('page')
    page_orders = paginator.get_page(page_number)
    
    # Get page-specific order data
    page_order_data = []
    for order in page_orders:
        if order.id in order_data_dict:
            page_order_data.append(order_data_dict[order.id])
    
    # Calculate low stock products
    low_stock_products = vendor_products.filter(stock__lte=5, stock__gt=0)[:5]
    out_of_stock = vendor_products.filter(stock=0).count()
    
    # Add verification status to context for template display
    verification_badge = {
        'verified': '✅ Verified',
        'under_review': '📋 Under Review',
        'pending': '⏳ Pending',
        'rejected': '❌ Rejected',
        'info_needed': 'ℹ️ Action Required'
    }
    
    context = {
        'orders': page_orders,
        'order_data': page_order_data,
        'total_orders': total_orders,
        'pending_orders': pending_orders,
        'processing_orders': processing_orders,
        'completed_orders': completed_orders,
        'cancelled_orders': cancelled_orders,
        'total_revenue': total_revenue,
        'orders_growth': round(orders_growth, 1),
        'vendor_products_count': vendor_products.count(),
        'low_stock_products': low_stock_products,
        'out_of_stock': out_of_stock,
        'business': business,
        'verification_status': business.verification_status,
        'verification_badge': verification_badge.get(business.verification_status, ''),
        'documents_complete': business.documents_complete,
        'days_on_platform': business.days_since_registration,
    }
    
    return render(request, "dashboard/vendor_dashboard.html", context)

@login_required
@require_http_methods(["POST"])
def update_order_status(request):
    """AJAX endpoint to update order status"""
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
        
        # Update status
        order.status = new_status
        order.save()
        
        # You can implement these notification functions
        if notify_whatsapp:
            # send_whatsapp_notification(order, new_status, note)
            pass
        if notify_sms:
            # send_sms_notification(order, new_status, note)
            pass
        
        return JsonResponse({
            'success': True,
            'message': f'Order #{order.id} status updated to {new_status}',
            'order_id': order.id,
            'new_status': new_status,
            'status_display': dict(Order.STATUS_CHOICES).get(new_status, new_status.title())
        })
        
    except Order.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Order not found'
        }, status=404)
    except Exception as e:
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
        
        # FIXED: Calculate total revenue correctly
        completed_items = vendor_order_items.filter(order__status='completed')
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
            for item in order_items:
                items_data.append({
                    'product_name': item.product.name,
                    'quantity': item.quantity,
                    'price': float(item.price),
                    'total': float(item.price * item.quantity)  # FIXED: Calculate here
                })
            
            recent_orders_data.append({
                'id': order.id,
                'customer_name': order.customer_name,
                'customer_phone': order.customer_phone,
                'status': order.status,
                'status_display': order.get_status_display(),
                'created_at': order.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                'total_amount': float(sum(item.price * item.quantity for item in order_items)),  # FIXED
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
                'orders_growth': round(orders_growth),
            },
            'recent_orders': recent_orders_data,
            'timestamp': timezone.now().isoformat()
        })
        
    except Exception as e:
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
        
        order = Order.objects.get(id=order_id)
        
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
        for item in order_items:
            items_data.append({
                'product_id': item.product.id,
                'product_name': item.product.name,
                'quantity': item.quantity,
                'price': float(item.price),
                'total': float(item.price * item.quantity)  # FIXED: Calculate total properly
            })
        
        # Calculate total amount correctly
        total_amount = float(sum(item.price * item.quantity for item in order_items))
        
        return JsonResponse({
            'success': True,
            'order': {
                'id': order.id,
                'customer_name': order.customer_name,
                'customer_phone': order.customer_phone,
                'customer_email': order.customer_email,
                'status': order.status,
                'status_display': order.get_status_display(),
                'created_at': order.created_at.strftime('%B %d, %Y at %H:%M'),
                'total_amount': total_amount,  # FIXED: Use calculated value
                'items': items_data,
                'shipping_address': order.shipping_address,
                'payment_method': order.payment_method,
                'payment_status': order.payment_status,
                'notes': order.notes
            }
        })
        
    except Order.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Order not found'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


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
    total_amount = float(sum(item.price * item.quantity for item in order_items))
    
    return render(request, "dashboard/order_detail.html", {
        "order": order,
        "order_items": order_items,
        "total_amount": total_amount,
        "business": business
    })
@login_required
def confirm_vendor_payment(request, order_id):
    """Vendor confirms they received the Pochi payment"""
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
        if not order.items.filter(product__business=business).exists():
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
            order.payment_notes = f'Payment rejected: {reason}'
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
    
    total_amount = sum(item.total_price for item in order_items)
    
    return render(request, "dashboard/receipt.html", {
        "order": order,
        "order_items": order_items,
        "total_amount": total_amount,
        "business": business
    })


# ================ PRODUCT MANAGEMENT ================

@login_required
def dashboard_home(request):
    """MAIN DASHBOARD - Products & Business Management"""
    business = Business.objects.filter(owner=request.user).first()
    if not business:
        return redirect("accounts:register_business")

    products = Product.objects.filter(business=business)
    
    # Get all orders that contain this vendor's products
    vendor_order_items = OrderItem.objects.filter(
        product__business=business
    ).select_related('order', 'product')
    
    # Get unique orders
    order_ids = vendor_order_items.values_list('order_id', flat=True).distinct()
    orders = Order.objects.filter(id__in=order_ids)
    
    # Calculate total orders
    total_orders = orders.count()
    
    # Calculate total revenue (completed orders only)
    # Calculate total price on the fly instead of using a field
    completed_items = vendor_order_items.filter(order__status='completed')
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
        'total_orders': total_orders,
        'total_revenue': f"{total_revenue:,.0f}",  # Format with commas
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
            product.save()
            return redirect("dashboard:dashboard_home")
    else:
        form = ProductForm()

    return render(request, "dashboard/product_form.html", {
        "form": form, 
        "title": "Add Product",
        "business": business
    })


@login_required
def product_edit(request, product_id):
    """Edit an existing product"""
    # Get vendor's business
    business = Business.objects.filter(owner=request.user).first()
    if not business:
        messages.error(request, "You need to register a business first!")
        return redirect("accounts:register_business")
    
    # Get the product (automatically 404 if doesn't exist or doesn't belong to this business)
    product = get_object_or_404(Product, id=product_id, business=business)

    if request.method == "POST":
        form = ProductForm(request.POST, request.FILES, instance=product)
        if form.is_valid():
            form.save()
            messages.success(request, "Product updated successfully!")
            return redirect("dashboard:dashboard_home")
    else:
        form = ProductForm(instance=product)

    return render(request, "dashboard/product_form.html", {
        "form": form, 
        "title": "Edit Product",
        "business": business
    })


@login_required
def product_delete(request, product_id):
    """Delete a product"""
    # Get vendor's business
    business = Business.objects.filter(owner=request.user).first()
    if not business:
        messages.error(request, "You need to register a business first!")
        return redirect("accounts:register_business")
    
    # Get the product (automatically 404 if doesn't exist or doesn't belong to this business)
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

# views.py
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.core import serializers
from orders.models import Order
import json

@require_GET
def get_latest_orders(request):
    """API endpoint for fetching latest orders"""
    
    # Get timestamp from request to fetch only new orders
    last_update = request.GET.get('last_update')
    
    if last_update:
        # Fetch orders updated after timestamp
        orders = Order.objects.filter(updated_at__gt=last_update)
    else:
        # Fetch recent orders (last 5 minutes)
        from django.utils import timezone
        from datetime import timedelta
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
                'username': order.customer.username,
                'email': order.customer.email,
                'initial': order.customer.username[0].upper() if order.customer.username else '?'
            },
            'vendor': {
                'username': order.vendor.username,
                'business': order.vendor.business.name if hasattr(order.vendor, 'business') else order.vendor.username
            },
            'items_count': order.order_items.count(),
            'total_amount': float(order_total),
            'status': order.status,
            'created_at': order.created_at.strftime('%b %d, %Y %H:%M'),
            'updated_at': order.updated_at.isoformat()
        })
    
    # Get all orders for counts (not just recent ones)
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
