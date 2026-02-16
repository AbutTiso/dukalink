# admin_dashboard/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Count, Sum, Avg, Q, F
from django.db.models.functions import TruncMonth, TruncDay, TruncHour
from django.db.models import ExpressionWrapper, fields
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from datetime import timedelta
import json

from accounts.models import Business, User
from accounts.forms import BusinessVerificationForm
from products.models import Product
from orders.models import Order, OrderItem

@staff_member_required
def admin_dashboard(request):
    """Main admin dashboard with overview stats"""
    
    # ===== REAL-TIME STATS =====
    total_vendors = Business.objects.count()
    
    # FIXED: Remove is_vendor, count buyers as users who don't own businesses
    vendor_owner_ids = Business.objects.values_list('owner_id', flat=True)
    total_buyers = User.objects.filter(
        is_staff=False, 
        is_superuser=False
    ).exclude(
        id__in=vendor_owner_ids
    ).count()
    
    total_products = Product.objects.count()
    total_orders = Order.objects.count()
    
    # Revenue - FIXED: Remove total_price, calculate manually
    completed_items = OrderItem.objects.filter(order__status='completed')
    total_revenue = 0
    for item in completed_items:
        total_revenue += item.quantity * item.price
    
    # ===== TODAY'S STATS =====
    today = timezone.now().date()
    today_orders = Order.objects.filter(created_at__date=today).count()
    
    today_revenue = 0
    today_items = OrderItem.objects.filter(
        order__status='completed',
        order__created_at__date=today
    )
    for item in today_items:
        today_revenue += item.quantity * item.price
    
    # ===== WEEKLY STATS =====
    week_ago = timezone.now() - timedelta(days=7)
    weekly_orders = Order.objects.filter(created_at__gte=week_ago).count()
    weekly_new_vendors = Business.objects.filter(created_at__gte=week_ago).count()
    weekly_new_products = Product.objects.filter(created_at__gte=week_ago).count()
    
    # ===== PENDING APPROVALS =====
    pending_shops = Business.objects.filter(is_approved=False).count()
    pending_orders = Order.objects.filter(status='pending').count()
    
    # ===== TOP PERFORMERS =====
    # FIXED: Remove Sum of total_price, just get order count first
    top_vendors = Business.objects.annotate(
    order_count=Count('products__orderitem', distinct=True)  # 'products' is correct
).order_by('-order_count')[:5]
    
    # Calculate revenue separately for top vendors
    for vendor in top_vendors:
        vendor_revenue = 0
        vendor_items = OrderItem.objects.filter(
            product__business=vendor,
            order__status='completed'
        )
        for item in vendor_items:
            vendor_revenue += item.quantity * item.price
        vendor.revenue = vendor_revenue
    
    # FIXED: Remove Sum of total_price for products
    top_products = Product.objects.annotate(
        order_count=Count('orderitem', distinct=True)
    ).order_by('-order_count')[:5]
    
    # Calculate revenue separately for top products
    for product in top_products:
        product_revenue = 0
        product_items = OrderItem.objects.filter(
            product=product,
            order__status='completed'
        )
        for item in product_items:
            product_revenue += item.quantity * item.price
        product.revenue = product_revenue
    
    # ===== RECENT ACTIVITIES =====
    recent_orders = Order.objects.select_related('customer', 'vendor').order_by('-created_at')[:10]
    recent_shops = Business.objects.order_by('-created_at')[:10]
    recent_products = Product.objects.select_related('business').order_by('-created_at')[:10]
    
    # Calculate totals for recent orders
    for order in recent_orders:
        order_total = 0
        for item in order.order_items.all():
            order_total += item.quantity * item.price
        order.total_amount = order_total
    
    context = {
        'total_vendors': total_vendors,
        'total_buyers': total_buyers,
        'total_products': total_products,
        'total_orders': total_orders,
        'total_revenue': f"{total_revenue:,.0f}",
        'today_orders': today_orders,
        'today_revenue': f"{today_revenue:,.0f}",
        'weekly_orders': weekly_orders,
        'weekly_new_vendors': weekly_new_vendors,
        'weekly_new_products': weekly_new_products,
        'pending_shops': pending_shops,
        'pending_orders': pending_orders,
        'top_vendors': top_vendors,
        'top_products': top_products,
        'recent_orders': recent_orders,
        'recent_shops': recent_shops,
        'recent_products': recent_products,
    }
    return render(request, 'admin_dashboard/dashboard.html', context)
@staff_member_required
def admin_vendors(request):
    """Manage all vendors"""
    vendors = Business.objects.all().select_related('owner').annotate(
        product_count=Count('products', distinct=True),
        order_count=Count('products__orderitem', distinct=True),
    ).order_by('-created_at')
    
    # Calculate revenue separately for each vendor
    for vendor in vendors:
        vendor_revenue = 0
        vendor_items = OrderItem.objects.filter(
            product__business=vendor,
            order__status='completed'
        )
        for item in vendor_items:
            vendor_revenue += item.quantity * item.price
        vendor.revenue = vendor_revenue
        
        # IMPORTANT: Add default values for template fields that don't exist in model
        vendor.business_type = 'Retail'  # Your model doesn't have this field
        vendor.address = vendor.location  # Your model uses 'location', not 'address'
    
    # Stats for header cards
    pending_count = Business.objects.filter(is_approved=False).count()  # FIXED: Use Business.objects, not vendors
    total_products = Product.objects.count()
    
    # Calculate total revenue
    total_revenue = 0
    completed_items = OrderItem.objects.filter(order__status='completed')
    for item in completed_items:
        total_revenue += item.quantity * item.price
    
    context = {
        'vendors': vendors,
        'pending_count': pending_count,
        'total_products': total_products,
        'total_revenue': f"{total_revenue:,.0f}",
    }
    
    return render(request, 'admin_dashboard/vendors.html', context)
@staff_member_required
def admin_products(request):
    """Manage all products"""
    products = Product.objects.all().select_related('business').annotate(
        order_count=Count('orderitem', distinct=True)
    ).order_by('-created_at')
    
    # Calculate revenue separately for each product
    for product in products:
        product_revenue = 0
        product_items = OrderItem.objects.filter(
            product=product,
            order__status='completed'
        )
        for item in product_items:
            product_revenue += item.quantity * item.price
        product.revenue = product_revenue
    
    # STATS FOR TEMPLATE CARDS - All compatible with your model
    total_products = products.count()
    total_out_of_stock = products.filter(stock=0).count()
    total_low_stock = products.filter(stock__lte=5, stock__gt=0).count()
    total_in_stock = products.filter(stock__gt=0).count()
    
    # Calculate total platform revenue
    total_revenue = 0
    completed_items = OrderItem.objects.filter(order__status='completed')
    for item in completed_items:
        total_revenue += item.quantity * item.price
    
    # Products by business (optional)
    top_businesses = Business.objects.annotate(
        product_count=Count('products')
    ).order_by('-product_count')[:5]
    
    context = {
        'products': products,
        'total_products': total_products,
        'total_out_of_stock': total_out_of_stock,
        'total_low_stock': total_low_stock,
        'total_in_stock': total_in_stock,
        'total_revenue': f"{total_revenue:,.0f}",
        'top_businesses': top_businesses,
    }
    
    return render(request, 'admin_dashboard/products.html', context)
@staff_member_required
def admin_orders(request):
    """Manage all orders"""
    orders = Order.objects.all().select_related('customer', 'vendor').prefetch_related(
        'order_items__product'
    ).order_by('-created_at')
    
    # Calculate total for each order
    for order in orders:
        order_total = 0
        for item in order.order_items.all():
            order_total += item.quantity * item.price
        order.total_amount = order_total
    
    # Calculate counts for filter cards
    context = {
        'orders': orders,
        'pending_count': orders.filter(status='pending').count(),
        'processing_count': orders.filter(status='processing').count(),
        'completed_count': orders.filter(status='completed').count(),
        'cancelled_count': orders.filter(status='cancelled').count(),
    }
    
    return render(request, 'admin_dashboard/orders.html', context)
# Try to import Category if it exists
try:
    from products.models import Category
    CATEGORY_EXISTS = True
except ImportError:
    CATEGORY_EXISTS = False

@staff_member_required
def admin_analytics(request):
    """Detailed analytics for admin dashboard"""
    
    # Date range (last 6 months)
    six_months_ago = timezone.now() - timedelta(days=180)
    thirty_days_ago = timezone.now() - timedelta(days=30)
    
    # ===== REVENUE DATA (Monthly for last 6 months) =====
    monthly_revenue = OrderItem.objects.filter(
        order__status='completed',
        order__paid=True,
        order__created_at__gte=six_months_ago
    ).annotate(
        month=TruncMonth('order__created_at')
    ).values('month').annotate(
        total=Sum(F('quantity') * F('price'))
    ).order_by('month')
    
    months = []
    revenue_data = []
    for item in monthly_revenue:
        months.append(item['month'].strftime('%b %Y'))
        revenue_data.append(float(item['total']))
    
    # ===== ORDER STATUS DISTRIBUTION =====
    order_status = {
        'pending': Order.objects.filter(status='pending').count(),
        'processing': Order.objects.filter(status='processing').count(),
        'completed': Order.objects.filter(status='completed').count(),
        'cancelled': Order.objects.filter(status='cancelled').count(),
    }
    
    # ===== KEY METRICS =====
    total_users = User.objects.filter(is_active=True).count()
    total_vendors = Business.objects.filter(is_approved=True).count()
    total_products = Product.objects.filter(is_available=True).count()
    total_orders = Order.objects.count()
    
    # Revenue metrics
    total_revenue = OrderItem.objects.filter(
        order__status='completed',
        order__paid=True
    ).aggregate(
        total=Sum(F('quantity') * F('price'))
    )['total'] or 0
    
    monthly_revenue_total = OrderItem.objects.filter(
        order__status='completed',
        order__paid=True,
        order__created_at__gte=thirty_days_ago
    ).aggregate(
        total=Sum(F('quantity') * F('price'))
    )['total'] or 0
    
    # Growth percentages
    previous_month = timezone.now() - timedelta(days=60)
    last_month_revenue = OrderItem.objects.filter(
        order__status='completed',
        order__paid=True,
        order__created_at__year=previous_month.year,
        order__created_at__month=previous_month.month
    ).aggregate(
        total=Sum(F('quantity') * F('price'))
    )['total'] or 0
    
    if last_month_revenue > 0:
        revenue_growth = round((monthly_revenue_total - last_month_revenue) / last_month_revenue * 100, 1)
    else:
        revenue_growth = 0
    
    # Completion rate
    completed_orders = Order.objects.filter(status='completed').count()
    completion_rate = round((completed_orders / total_orders * 100) if total_orders > 0 else 0, 1)
    
    # Average order value
    avg_order_value = Order.objects.filter(
        status='completed',
        paid=True
    ).aggregate(avg=Avg('total'))['avg'] or 0
    
    # ===== VENDOR STATISTICS =====
    top_vendors = Business.objects.filter(
        is_approved=True
    ).annotate(
        total_sales=Sum('products__orderitem__quantity', filter=Q(products__orderitem__order__status='completed')),
        total_revenue=Sum(F('products__orderitem__quantity') * F('products__orderitem__price'), 
                         filter=Q(products__orderitem__order__status='completed'))
    ).order_by('-total_revenue')[:5]
    
    vendor_stats = []
    for vendor in top_vendors:
        vendor_stats.append({
            'name': vendor.name,
            'sales': vendor.total_sales or 0,
            'revenue': float(vendor.total_revenue or 0)
        })
    
    # Total vendor revenue
    total_vendor_revenue = OrderItem.objects.filter(
        product__business__is_approved=True,
        order__status='completed'
    ).aggregate(
        total=Sum(F('quantity') * F('price'))
    )['total'] or 0
    
    # ===== PRODUCT CATEGORIES - WITH ERROR HANDLING =====
    category_names = []
    category_sales = []
    
    if CATEGORY_EXISTS:
        try:
            top_categories = Category.objects.annotate(
                total_sold=Sum('product__orderitem__quantity', filter=Q(product__orderitem__order__status='completed'))
            ).filter(total_sold__gt=0).order_by('-total_sold')[:5]
            
            for cat in top_categories:
                category_names.append(cat.name)
                category_sales.append(cat.total_sold or 0)
        except Exception as e:
            # If any error occurs with categories, just use empty data
            pass
    
    # ===== DAILY ORDERS (Last 7 days) =====
    last_7_days = timezone.now() - timedelta(days=7)
    daily_orders = Order.objects.filter(
        created_at__gte=last_7_days
    ).annotate(
        day=TruncDay('created_at')
    ).values('day').annotate(
        count=Count('id')
    ).order_by('day')
    
    days = []
    order_counts = []
    for item in daily_orders:
        days.append(item['day'].strftime('%a, %b %d'))
        order_counts.append(item['count'])
    
    # ===== HOURLY ORDER DISTRIBUTION =====
    hourly_orders = Order.objects.filter(
        created_at__gte=thirty_days_ago
    ).annotate(
        hour=TruncHour('created_at')
    ).values('hour').annotate(
        count=Count('id')
    ).order_by('hour')
    
    hours = list(range(24))
    hourly_counts = [0] * 24
    
    for item in hourly_orders:
        if item['hour']:
            hour = item['hour'].hour
            hourly_counts[hour] = item['count']
    
    # ===== PAYMENT METHODS =====
    mpesa_orders = Order.objects.filter(payment_method='MPESA', paid=True).count()
    cash_orders = Order.objects.filter(payment_method='CASH', paid=True).count()
    
    # ===== AVERAGE PROCESSING TIME =====
    completed_orders_with_time = Order.objects.filter(
        status='completed',
        paid=True
    ).annotate(
        processing_time=ExpressionWrapper(
            F('updated_at') - F('created_at'),
            output_field=fields.DurationField()
        )
    )
    
    avg_time = completed_orders_with_time.aggregate(
        avg=Avg('processing_time')
    )['avg']
    
    if avg_time:
        hours = avg_time.total_seconds() / 3600
        avg_processing_time = round(hours, 1)
    else:
        avg_processing_time = 0
    
    # ===== RECENT ACTIVITY =====
    recent_orders = Order.objects.filter(
        status='completed',
        paid=True
    ).order_by('-updated_at')[:10]
    
    recent_activity = []
    for order in recent_orders:
        recent_activity.append({
            'order_id': order.id,
            'customer': order.customer_name,
            'amount': float(order.total),
            'time': order.updated_at
        })
    
    context = {
        # Chart data
        'months': json.dumps(months),
        'revenue_data': json.dumps(revenue_data),
        'order_status': order_status,
        'days': json.dumps(days),
        'order_counts': json.dumps(order_counts),
        'hours': json.dumps(hours),
        'hourly_counts': json.dumps(hourly_counts),
        'category_names': json.dumps(category_names),
        'category_sales': json.dumps(category_sales),
        
        # Key metrics
        'total_users': total_users,
        'total_vendors': total_vendors,
        'total_products': total_products,
        'total_orders': total_orders,
        'total_revenue': float(total_revenue),
        'monthly_revenue': float(monthly_revenue_total),
        'revenue_growth': revenue_growth,
        'completion_rate': completion_rate,
        'avg_order_value': float(avg_order_value),
        'avg_processing_time': avg_processing_time,
        
        # Vendor stats
        'top_vendors': vendor_stats,
        'total_vendor_revenue': float(total_vendor_revenue),
        
        # Payment methods
        'mpesa_orders': mpesa_orders,
        'cash_orders': cash_orders,
        
        # Recent activity
        'recent_activity': recent_activity,
        
        # Timestamps
        'today': timezone.now(),
    }
    
    return render(request, 'admin_dashboard/analytics.html', context)
@staff_member_required
def make_superadmin(request, user_id):
    """Promote a user to superadmin"""
    if not request.user.is_superuser:
        messages.error(request, 'Only superadmins can promote other users!')
        return redirect('admin_dashboard:dashboard')
    
    user = get_object_or_404(User, id=user_id)
    user.is_staff = True
    user.is_superuser = True
    user.save()
    
    messages.success(request, f'{user.username} is now a superadmin!')
    return redirect('admin_dashboard:vendors')


@staff_member_required
@csrf_exempt
def approve_vendor(request, vendor_id):
    """Approve a vendor shop"""
    if request.method == 'POST':
        try:
            vendor = get_object_or_404(Business, id=vendor_id)
            vendor.is_approved = True
            vendor.save()
            
            return JsonResponse({
                'success': True,
                'message': f'{vendor.name} has been approved successfully!'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=400)
    return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)

@staff_member_required
@csrf_exempt
def suspend_vendor(request, vendor_id):
    """Suspend/reject a vendor shop"""
    if request.method == 'POST':
        try:
            vendor = get_object_or_404(Business, id=vendor_id)
            vendor.is_approved = False
            vendor.save()
            
            return JsonResponse({
                'success': True,
                'message': f'{vendor.name} has been suspended.'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=400)
    return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)

@staff_member_required
def vendor_details(request, vendor_id):
    """Get vendor details for modal"""
    try:
        vendor = get_object_or_404(Business, id=vendor_id)
        
        # Calculate stats
        product_count = Product.objects.filter(business=vendor).count()
        order_count = OrderItem.objects.filter(product__business=vendor).values('order').distinct().count()
        
        revenue = 0
        completed_items = OrderItem.objects.filter(
            product__business=vendor,
            order__status='completed'
        )
        for item in completed_items:
            revenue += item.quantity * item.price
        
        return JsonResponse({
            'success': True,
            'vendor': {
                'id': vendor.id,
                'name': vendor.name,
                'business_type': 'Retail',  # Your model doesn't have this, provide default
                'phone': vendor.phone,
                'address': vendor.location,  # FIXED: Use location, not address
                'is_approved': vendor.is_approved,
                'created_at': vendor.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                'joined_date': vendor.created_at.strftime('%B %d, %Y'),
                'product_count': product_count,
                'order_count': order_count,
                'revenue': f"{revenue:,.0f}",
                'owner': {
                    'username': vendor.owner.username,
                    'email': vendor.owner.email,
                    'first_name': vendor.owner.first_name,
                    'last_name': vendor.owner.last_name,
                }
            }
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)
@staff_member_required
@csrf_exempt
def reject_vendor(request, vendor_id):
    """Reject a vendor shop"""
    if request.method == 'POST':
        try:
            vendor = get_object_or_404(Business, id=vendor_id)
            vendor.is_approved = False
            vendor.is_active = False  # Optional: deactivate the vendor
            vendor.save()
            
            return JsonResponse({
                'success': True,
                'message': f'{vendor.name} has been rejected.'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=400)
    return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)

###########
#Verification Documents views
##########################

@staff_member_required
def verify_vendor_documents(request, vendor_id):
    """Admin view to review and verify vendor documents"""
    vendor = get_object_or_404(Business, id=vendor_id)
    
    if request.method == "POST":
        form = BusinessVerificationForm(request.POST)
        if form.is_valid():
            status = form.cleaned_data['verification_status']
            notes = form.cleaned_data['verification_notes']
            notify = form.cleaned_data['notify_vendor']
            
            vendor.verification_status = status
            vendor.verification_notes = notes
            vendor.verified_by = request.user
            vendor.verified_at = timezone.now()
            
            # Auto-update approval status based on verification
            if status == 'verified':
                vendor.is_approved = True
                vendor.is_rejected = False
                message = f'{vendor.name} has been verified and approved!'
            elif status == 'rejected':
                vendor.is_approved = False
                vendor.is_rejected = True
                message = f'{vendor.name} has been rejected.'
            else:  # info_needed
                vendor.is_approved = False
                vendor.is_rejected = False
                message = f'More information requested from {vendor.name}.'
            
            vendor.save()
            
            # TODO: Send email notification if notify is True
            
            messages.success(request, message)
            return redirect('admin_dashboard:vendor_documents')
    else:
        form = BusinessVerificationForm()
    
    return render(request, 'admin_dashboard/verify_vendor.html', {
        'vendor': vendor,
        'form': form
    })


@staff_member_required
def vendor_documents_list(request):
    """List all vendors pending document verification"""
    # Pending verification (need review)
    pending_vendors = Business.objects.filter(
        verification_status__in=['pending', 'under_review']
    ).select_related('owner', 'verified_by').order_by('-created_at')
    
    # Recently verified
    verified_vendors = Business.objects.filter(
        verification_status='verified'
    ).select_related('owner', 'verified_by').order_by('-verified_at')[:20]
    
    # Rejected vendors
    rejected_vendors = Business.objects.filter(
        verification_status='rejected'
    ).select_related('owner', 'verified_by').order_by('-verified_at')[:20]
    
    # Vendors needing more info - FIXED: changed 'updated_at' to 'documents_updated_at'
    info_needed_vendors = Business.objects.filter(
        verification_status='info_needed'
    ).select_related('owner').order_by('-documents_updated_at')[:20]
    
    # Statistics
    total_pending = pending_vendors.count()
    total_verified_today = Business.objects.filter(
        verification_status='verified',
        verified_at__date=timezone.now().date()
    ).count()
    
    # ADD THESE for the dashboard template
    pending_documents = Business.objects.filter(
        verification_status__in=['pending', 'under_review']
    ).count()
    
    info_needed_count = Business.objects.filter(
        verification_status='info_needed'
    ).count()
    
    verified_this_week = Business.objects.filter(
        verification_status='verified',
        verified_at__gte=timezone.now() - timedelta(days=7)
    ).count()
    
    rejected_this_week = Business.objects.filter(
        verification_status='rejected',
        verified_at__gte=timezone.now() - timedelta(days=7)
    ).count()
    
    recent_verifications = Business.objects.filter(
        verification_status__in=['verified', 'rejected']
    ).exclude(
        verified_at__isnull=True
    ).select_related('owner', 'verified_by').order_by('-verified_at')[:10]
    
    context = {
        'pending_vendors': pending_vendors,
        'verified_vendors': verified_vendors,
        'rejected_vendors': rejected_vendors,
        'info_needed_vendors': info_needed_vendors,
        'total_pending': total_pending,
        'total_verified_today': total_verified_today,
        # ADD THESE for the dashboard template
        'pending_documents': pending_documents,
        'info_needed_count': info_needed_count,
        'verified_this_week': verified_this_week,
        'rejected_this_week': rejected_this_week,
        'recent_verifications': recent_verifications,
    }
    
    return render(request, 'admin_dashboard/vendor_documents.html', context)
@staff_member_required
def review_vendor_documents(request, vendor_id):
    """Admin view to review and verify vendor documents"""
    vendor = get_object_or_404(Business, id=vendor_id)
    
    # Calculate days pending
    days_pending = (timezone.now().date() - vendor.created_at.date()).days
    
    # Check if documents are complete
    missing_docs = vendor.missing_documents
    documents_complete = vendor.documents_complete
    uploaded_count = vendor.uploaded_documents_count
    
    if request.method == "POST":
        form = BusinessVerificationForm(request.POST)
        if form.is_valid():
            status = form.cleaned_data['verification_status']
            notes = form.cleaned_data['verification_notes']
            notify = form.cleaned_data['notify_vendor']
            
            # Update vendor verification status
            vendor.verification_status = status
            vendor.verification_notes = notes
            vendor.verified_by = request.user
            vendor.verified_at = timezone.now()
            
            # Update approval status based on verification
            if status == 'verified':
                vendor.is_approved = True
                vendor.is_rejected = False
                message = f'✅ {vendor.name} has been verified and approved!'
            elif status == 'rejected':
                vendor.is_approved = False
                vendor.is_rejected = True
                message = f'❌ {vendor.name} has been rejected.'
            else:  # info_needed
                vendor.is_approved = False
                vendor.is_rejected = False
                message = f'ℹ️ More information requested from {vendor.name}.'
            
            vendor.save()
            
            messages.success(request, message)
            return redirect('admin_dashboard:vendor_documents')
    else:
        # Pre-fill form with current status
        initial_data = {
            'verification_status': vendor.verification_status,
            'verification_notes': vendor.verification_notes,
        }
        form = BusinessVerificationForm(initial=initial_data)
    
    context = {
        'vendor': vendor,
        'form': form,
        'missing_documents': missing_docs,
        'documents_complete': documents_complete,
        'uploaded_count': uploaded_count,
        'days_pending': days_pending,
    }
    
    return render(request, 'admin_dashboard/review_vendor.html', context)

@staff_member_required
def vendor_document_detail(request, vendor_id, doc_type):
    """View specific document in detail with actual image/document display"""
    vendor = get_object_or_404(Business, id=vendor_id)
    
    # Format dates for display
    permit_expiry_text = "Not set"
    if vendor.permit_expiry_date:
        permit_expiry_text = vendor.permit_expiry_date.strftime('%B %d, %Y')
    
    documents_uploaded_text = "N/A"
    if vendor.documents_uploaded_at:
        documents_uploaded_text = vendor.documents_uploaded_at.strftime('%B %d, %Y at %H:%M')
    
    document_mapping = {
        'registration': {
            'field': vendor.business_registration_cert,
            'name': 'Business Registration Certificate',
            'icon': 'fa-certificate',
            'description': 'Certificate of Business Registration/BRS',
            'number': vendor.business_registration_number
        },
        'kra': {
            'field': vendor.kra_certificate,
            'name': 'KRA PIN Certificate',
            'icon': 'fa-file-invoice',
            'description': f'KRA PIN: {vendor.kra_pin or "Not provided"}',
            'pin': vendor.kra_pin
        },
        'tax': {
            'field': vendor.tax_compliance_cert,
            'name': 'Tax Compliance Certificate',
            'icon': 'fa-file-invoice-dollar',
            'description': 'Tax Compliance Certificate (Optional)'
        },
        'id_front': {
            'field': vendor.owner_id_front,
            'name': 'National ID - Front',
            'icon': 'fa-id-card',
            'description': f'ID Number: {vendor.owner_id_number or "Not provided"}',
            'id_number': vendor.owner_id_number
        },
        'id_back': {
            'field': vendor.owner_id_back,
            'name': 'National ID - Back',
            'icon': 'fa-id-card',
            'description': 'National ID - Back Side'
        },
        'permit': {
            'field': vendor.business_permit,
            'name': 'Business Permit',
            'icon': 'fa-file-signature',
            'description': f'Expires: {permit_expiry_text}',
            'expiry_date': permit_expiry_text,
            'is_valid': vendor.permit_is_valid
        },
        'additional': {
            'field': vendor.additional_docs,
            'name': 'Additional Documents',
            'icon': 'fa-folder-open',
            'description': 'Supporting documents'
        }
    }
    
    doc_info = document_mapping.get(doc_type)
    
    if not doc_info or not doc_info['field']:
        messages.error(request, "Document not found.")
        return redirect('admin_dashboard:review_vendor', vendor_id=vendor.id)
    
    document = doc_info['field']
    file_url = document.url
    file_name = document.name.split('/')[-1]
    file_size = document.size
    
    # Check if it's an image
    is_image = False
    if hasattr(document, 'url'):
        ext = file_name.split('.')[-1].lower() if '.' in file_name else ''
        is_image = ext in ['jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp']
    
    context = {
        'vendor': vendor,
        'document': document,
        'doc_info': doc_info,
        'file_url': file_url,
        'file_name': file_name,
        'file_size': file_size,
        'is_image': is_image,
        'doc_type': doc_type,
        'documents_uploaded_text': documents_uploaded_text,
    }
    
    return render(request, 'admin_dashboard/document_view.html', context)

@staff_member_required
@csrf_exempt
def bulk_verify_vendors(request):
    """Bulk verify multiple vendors at once"""
    if request.method == 'POST':
        import json
        data = json.loads(request.body)
        vendor_ids = data.get('vendor_ids', [])
        action = data.get('action', '')
        
        if not vendor_ids:
            return JsonResponse({'success': False, 'error': 'No vendors selected'})
        
        vendors = Business.objects.filter(id__in=vendor_ids)
        count = vendors.count()
        
        if action == 'verify':
            vendors.update(
                verification_status='verified',
                is_approved=True,
                is_rejected=False,
                verified_by=request.user,
                verified_at=timezone.now(),
                verification_notes='Bulk verified by admin'
            )
            message = f'✅ {count} vendor(s) verified successfully!'
        elif action == 'reject':
            vendors.update(
                verification_status='rejected',
                is_approved=False,
                is_rejected=True,
                verified_by=request.user,
                verified_at=timezone.now(),
                verification_notes='Bulk rejected by admin'
            )
            message = f'❌ {count} vendor(s) rejected.'
        else:
            return JsonResponse({'success': False, 'error': 'Invalid action'})
        
        return JsonResponse({'success': True, 'message': message})
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'}, status=405)


@staff_member_required
def export_vendor_data(request):
    """Export vendor verification data to CSV"""
    import csv
    from django.http import HttpResponse
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="vendors-{timezone.now().date()}.csv"'
    
    writer = csv.writer(response)
    writer.writerow([
        'Business Name', 'Owner', 'Email', 'Phone', 'Business Type',
        'Registration Date', 'Verification Status', 'Verified By', 'Verified Date',
        'KRA PIN', 'ID Number', 'Permit Expiry', 'Documents Complete'
    ])
    
    vendors = Business.objects.select_related('owner', 'verified_by').all()
    
    for vendor in vendors:
        writer.writerow([
            vendor.name,
            vendor.owner.username,
            vendor.owner.email,
            vendor.phone,
            vendor.get_business_type_display(),
            vendor.created_at.date(),
            vendor.get_verification_status_display(),
            vendor.verified_by.username if vendor.verified_by else '',
            vendor.verified_at.date() if vendor.verified_at else '',
            vendor.kra_pin or '',
            vendor.owner_id_number or '',
            vendor.permit_expiry_date or '',
            'Yes' if vendor.documents_complete else 'No'
        ])
    
    return response