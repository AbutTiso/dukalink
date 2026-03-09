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

# admin_dashboard/views.py - COMPLETELY FIXED VERSION

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

# Try to import VendorPayment - it should be in orders.models
try:
    from orders.models import VendorPayment
    VENDOR_PAYMENT_EXISTS = True
except ImportError:
    VENDOR_PAYMENT_EXISTS = False
    # Create a dummy class to avoid NameError
    class VendorPayment:
        class objects:
            @staticmethod
            def filter(*args, **kwargs):
                return []
            def aggregate(self, *args, **kwargs):
                return {'commission_amount__sum': 0, 'net_amount__sum': 0}

# Try to import ContactMessage - might be in a different app
CONTACT_EXISTS = False
try:
    from contact.models import ContactMessage
    CONTACT_EXISTS = True
except ImportError:
    try:
        from accounts.models import ContactMessage
        CONTACT_EXISTS = True
    except ImportError:
        try:
            from orders.models import ContactMessage
            CONTACT_EXISTS = True
        except ImportError:
            CONTACT_EXISTS = False


@staff_member_required
def admin_analytics(request):
    """Detailed analytics for admin dashboard with REAL data from your models"""
    
    # Get date range from request (default: 6 months)
    days = int(request.GET.get('range', 180))
    if days == 0:
        start_date = timezone.datetime(2020, 1, 1)  # All time
        range_text = 'All time'
    else:
        start_date = timezone.now() - timedelta(days=days)
        range_text = f'Last {days} days'
    
    # ===== BASE QUERYSETS FILTERED BY DATE =====
    orders = Order.objects.filter(created_at__gte=start_date)
    completed_orders = orders.filter(status='completed', paid=True)
    pending_orders = orders.filter(status='pending')
    processing_orders = orders.filter(status='processing')
    
    # OrderItems for completed orders (filtered by date)
    completed_items = OrderItem.objects.filter(
        order__in=completed_orders
    )
    
    # ===== ALL TIME METRICS (Matches Admin Dashboard EXACTLY) =====
    # Remove paid=True filter to match admin_dashboard view
    all_time_completed_items = OrderItem.objects.filter(
        order__status='completed'  # Only filter by status, same as admin dashboard
    )
    
    # Calculate ALL TIME revenue (same as admin dashboard)
    all_time_revenue = 0
    for item in all_time_completed_items:
        all_time_revenue += item.quantity * item.price
    
    # ALL TIME orders - remove paid=True filter
    all_time_orders = Order.objects.filter(status='completed').count()
    
    # ===== KEY METRICS (Filtered by date range) =====
    
    # 1. User Metrics (these are always all time - users don't get filtered)
    vendor_owner_ids = Business.objects.values_list('owner_id', flat=True)
    total_users = User.objects.filter(is_active=True).count()
    total_buyers = User.objects.filter(
        is_staff=False, 
        is_superuser=False
    ).exclude(
        id__in=vendor_owner_ids
    ).count()
    
    # 2. Vendor Metrics (all time - vendors don't get filtered by order date)
    total_vendors = Business.objects.filter(is_approved=True).count()
    pending_vendors = Business.objects.filter(verification_status='pending').count()
    verified_vendors = Business.objects.filter(verification_status='verified').count()
    rejected_vendors = Business.objects.filter(verification_status='rejected').count()
    info_needed_vendors = Business.objects.filter(verification_status='info_needed').count()
    
    # 3. Product Metrics (all time)
    total_products = Product.objects.filter(is_available=True).count()
    out_of_stock = Product.objects.filter(stock=0, is_available=True).count()
    low_stock = Product.objects.filter(stock__lte=5, stock__gt=0, is_available=True).count()
    
    # 4. Order Metrics (filtered by date range)
    total_orders = orders.count()
    total_completed = completed_orders.count()
    completion_rate = round((total_completed / total_orders * 100) if total_orders > 0 else 0, 1)
    
    # 5. Revenue Metrics - Filtered by date range
    filtered_revenue = 0
    for item in completed_items:
        filtered_revenue += item.quantity * item.price
    
    # Monthly revenue (last 30 days)
    thirty_days_ago = timezone.now() - timedelta(days=30)
    monthly_items = OrderItem.objects.filter(
        order__in=completed_orders.filter(created_at__gte=thirty_days_ago)
    )
    monthly_revenue = 0
    for item in monthly_items:
        monthly_revenue += item.quantity * item.price
    
    # Revenue growth (comparing last 30 days to previous 30 days)
    previous_month_start = thirty_days_ago - timedelta(days=30)
    previous_month_items = OrderItem.objects.filter(
        order__in=Order.objects.filter(
            status='completed', 
            paid=True,
            created_at__gte=previous_month_start,
            created_at__lt=thirty_days_ago
        )
    )
    previous_month_revenue = 0
    for item in previous_month_items:
        previous_month_revenue += item.quantity * item.price
    
    if previous_month_revenue > 0:
        revenue_growth = round((monthly_revenue - previous_month_revenue) / previous_month_revenue * 100, 1)
    else:
        revenue_growth = 0
    
    # 6. Average Order Value (filtered by date range)
    if total_completed > 0:
        avg_order_value = filtered_revenue / total_completed
    else:
        avg_order_value = 0
    
    # 7. Payment Methods (filtered by date range)
    mpesa_orders = completed_orders.filter(
        Q(payment_method__icontains='mpesa') | 
        Q(payment_method__in=['mpesa_till', 'mpesa_paybill'])
    ).count()
    
    cash_orders = completed_orders.filter(payment_method='cash_on_delivery').count()
    pochi_orders = completed_orders.filter(payment_method='pochi_biashara').count()
    
    # 8. Commission Data - ONLY if VendorPayment exists (filtered by date range)
    total_commission = 0
    total_paid_to_vendors = 0
    
    if VENDOR_PAYMENT_EXISTS:
        try:
            vendor_payments = VendorPayment.objects.filter(
                order__in=completed_orders,
                status='completed'
            )
            total_commission = vendor_payments.aggregate(Sum('commission_amount'))['commission_amount__sum'] or 0
            total_paid_to_vendors = vendor_payments.aggregate(Sum('net_amount'))['net_amount__sum'] or 0
        except Exception as e:
            print(f"VendorPayment error: {e}")
            total_commission = 0
            total_paid_to_vendors = 0
    
    # 9. Customer Messages - ONLY if ContactMessage exists
    unread_messages = 0
    total_messages = 0
    
    if CONTACT_EXISTS:
        try:
            unread_messages = ContactMessage.objects.filter(is_read=False).count()
            total_messages = ContactMessage.objects.filter(created_at__gte=start_date).count()
        except Exception as e:
            print(f"ContactMessage error: {e}")
            unread_messages = 0
            total_messages = 0
    
    # ===== CHART DATA (All filtered by date range) =====
    
    # 1. REVENUE CHART (Monthly - filtered by date range)
    monthly_revenue_data = {}
    current = start_date.replace(day=1)
    end = timezone.now().replace(day=1)
    
    while current <= end:
        month_str = current.strftime('%b %Y')
        monthly_revenue_data[month_str] = 0
        # Move to next month
        if current.month == 12:
            current = current.replace(year=current.year + 1, month=1)
        else:
            current = current.replace(month=current.month + 1)
    
    # Aggregate revenue by month
    for item in completed_items:
        month_str = item.order.created_at.strftime('%b %Y')
        if month_str in monthly_revenue_data:
            monthly_revenue_data[month_str] += item.quantity * item.price
    
    months = list(monthly_revenue_data.keys())
    revenue_data = list(monthly_revenue_data.values())
    
    # 2. ORDER STATUS CHART (filtered by date range)
    order_status = {
        'pending': orders.filter(status='pending').count(),
        'processing': orders.filter(status='processing').count(),
        'completed': orders.filter(status='completed').count(),
        'cancelled': orders.filter(status='cancelled').count(),
    }
    
    # 3. TOP VENDORS (Businesses) - Filtered by date range
    vendors_with_sales = []
    for vendor in Business.objects.filter(is_approved=True)[:20]:  # Limit to top 20 for performance
        # Get vendor's completed order items for the selected period
        vendor_items = OrderItem.objects.filter(
            product__business=vendor,
            order__in=completed_orders
        )
        
        # Calculate totals
        total_sales = 0
        total_rev = 0
        for item in vendor_items:
            total_sales += item.quantity
            total_rev += item.quantity * item.price
        
        # Only include vendors with sales
        if total_rev > 0:
            # Calculate growth
            previous_period_items = OrderItem.objects.filter(
                product__business=vendor,
                order__in=Order.objects.filter(
                    status='completed',
                    paid=True,
                    created_at__gte=start_date - timedelta(days=days),
                    created_at__lt=start_date
                )
            )
            prev_sales = sum(item.quantity for item in previous_period_items)
            current_sales = total_sales
            growth = round(((current_sales - prev_sales) / prev_sales * 100) if prev_sales > 0 else 0, 1)
            
            vendors_with_sales.append({
                'name': vendor.name,
                'logo': vendor.logo.url if vendor.logo and hasattr(vendor.logo, 'url') else None,
                'sales': total_sales,
                'revenue': float(total_rev),
                'orders': vendor_items.values('order').distinct().count(),
                'growth': growth if growth > 0 else None,
            })
    
    # Sort by revenue and get top 5
    top_vendors = sorted(vendors_with_sales, key=lambda x: x['revenue'], reverse=True)[:5]
    total_vendor_revenue = sum(v['revenue'] for v in top_vendors)
    
    # 4. RECENT ACTIVITY (filtered by date range)
    recent_orders = Order.objects.filter(
        status='completed',
        paid=True,
        created_at__gte=start_date
    ).select_related(
        'customer'
    ).prefetch_related(
        'order_items__product__business'
    ).order_by('-updated_at')[:10]
    
    recent_activity = []
    for order in recent_orders:
        # Calculate order total
        order_total = 0
        vendors = set()
        items_count = 0
        
        for item in order.order_items.all():
            order_total += item.quantity * item.price
            items_count += item.quantity
            if item.product and item.product.business:
                vendors.add(item.product.business.name)
        
        recent_activity.append({
            'order_id': order.id,
            'customer': order.customer_name,
            'amount': float(order_total),
            'items': items_count,
            'vendors': ', '.join(list(vendors)[:2]) + ('...' if len(vendors) > 2 else ''),
            'time': order.updated_at
        })
    
    # 5. TOP PRODUCTS (filtered by date range)
    product_sales = {}
    for item in completed_items:
        product = item.product
        if product and product.id not in product_sales:
            product_sales[product.id] = {
                'name': product.name,
                'business': product.business.name if product.business else 'Unknown',
                'quantity': 0,
                'revenue': 0
            }
        if product and product.id in product_sales:
            product_sales[product.id]['quantity'] += item.quantity
            product_sales[product.id]['revenue'] += item.quantity * item.price
    
    top_products = sorted(product_sales.values(), key=lambda x: x['revenue'], reverse=True)[:5]
    
    # 6. CATEGORIES (by Business Type) - filtered by date range
    category_data = {}
    for vendor in Business.objects.filter(is_approved=True):
        vendor_items = OrderItem.objects.filter(
            product__business=vendor,
            order__in=completed_orders
        )
        total_sold = sum(item.quantity for item in vendor_items)
        if total_sold > 0:
            biz_type = vendor.get_business_type_display() if vendor.business_type else 'Other'
            if biz_type not in category_data:
                category_data[biz_type] = 0
            category_data[biz_type] += total_sold
    
    category_names = list(category_data.keys())
    category_sales = list(category_data.values())
    
    # 7. HOURLY DISTRIBUTION (filtered by date range)
    hourly_counts = [0] * 24
    for order in completed_orders:
        hour = order.created_at.hour
        hourly_counts[hour] += 1
    
    hours = list(range(24))
    
    # 8. LAST 7 DAYS (filtered by date range)
    last_7_days = []
    order_counts = []
    revenue_by_day = []
    
    for i in range(6, -1, -1):
        day = timezone.now() - timedelta(days=i)
        day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day.replace(hour=23, minute=59, second=59, microsecond=999999)
        
        day_orders = completed_orders.filter(created_at__range=[day_start, day_end])
        count = day_orders.count()
        
        # Calculate day revenue
        day_revenue = 0
        for order in day_orders:
            for item in order.order_items.all():
                day_revenue += item.quantity * item.price
        
        last_7_days.append(day.strftime('%a, %d %b'))
        order_counts.append(count)
        revenue_by_day.append(float(day_revenue))
    
    # 9. GEOGRAPHIC DISTRIBUTION (by County) - all time
    county_data = {}
    for vendor in Business.objects.filter(county__isnull=False).exclude(county=''):
        if vendor.county not in county_data:
            county_data[vendor.county] = 0
        county_data[vendor.county] += 1
    
    # Sort and get top 10 counties
    sorted_counties = sorted(county_data.items(), key=lambda x: x[1], reverse=True)[:10]
    counties = [item[0] for item in sorted_counties]
    vendor_counts = [item[1] for item in sorted_counties]
    
    # 10. PAYMENT METHODS BREAKDOWN (filtered by date range)
    payment_methods = {
        'M-Pesa (Till)': orders.filter(payment_method='mpesa_till').count(),
        'M-Pesa (Paybill)': orders.filter(payment_method='mpesa_paybill').count(),
        'Pochi Biashara': orders.filter(payment_method='pochi_biashara').count(),
        'Cash on Delivery': orders.filter(payment_method='cash_on_delivery').count(),
    }
    
    # 11. VERIFICATION STATUS - all time
    verification_status = {
        'pending': Business.objects.filter(verification_status='pending').count(),
        'under_review': Business.objects.filter(verification_status='under_review').count(),
        'verified': Business.objects.filter(verification_status='verified').count(),
        'rejected': Business.objects.filter(verification_status='rejected').count(),
        'info_needed': Business.objects.filter(verification_status='info_needed').count(),
    }
    
    # 12. AVERAGE PROCESSING TIME (filtered by date range)
    processing_times = []
    for order in completed_orders.filter(updated_at__isnull=False):
        if order.updated_at and order.created_at:
            time_diff = order.updated_at - order.created_at
            hours = time_diff.total_seconds() / 3600
            if hours > 0:
                processing_times.append(hours)
    
    avg_processing_time = round(sum(processing_times) / len(processing_times), 1) if processing_times else 0
    
    # 13. DOCUMENT STATS - all time
    vendors_with_docs = Business.objects.exclude(
        business_registration_cert=''
    ).exclude(
        business_registration_cert__isnull=True
    ).count()
    
    vendors_with_kra = Business.objects.exclude(
        kra_certificate=''
    ).exclude(
        kra_certificate__isnull=True
    ).count()
    
    # ===== PREPARE CONTEXT FOR TEMPLATE =====
    context = {
        # Chart data (JSON serialized)
        'months': json.dumps(months),
        'revenue_data': json.dumps([float(r) for r in revenue_data]),
        'order_status': order_status,
        'days': json.dumps(last_7_days),
        'order_counts': json.dumps(order_counts),
        'revenue_by_day': json.dumps(revenue_by_day),
        'hours': json.dumps(hours),
        'hourly_counts': json.dumps(hourly_counts),
        'category_names': json.dumps(category_names),
        'category_sales': json.dumps(category_sales),
        'counties': json.dumps(counties),
        'vendor_counts': json.dumps(vendor_counts),
        'payment_methods': payment_methods,
        'verification_status': verification_status,
        
        # Key metrics - ALL TIME (matches admin dashboard)
        'all_time_revenue': float(all_time_revenue),
        'all_time_orders': all_time_orders,
        'total_users': total_users,
        'total_buyers': total_buyers,
        'total_vendors': total_vendors,
        'pending_vendors': pending_vendors,
        'verified_vendors': verified_vendors,
        'rejected_vendors': rejected_vendors,
        'info_needed_vendors': info_needed_vendors,
        'total_products': total_products,
        'out_of_stock': out_of_stock,
        'low_stock': low_stock,
        
        # Filtered metrics (for the selected period)
        'filtered_revenue': float(filtered_revenue),
        'total_orders': total_orders,
        'completed_orders': total_completed,
        'completion_rate': completion_rate,
        'monthly_revenue': float(monthly_revenue),
        'revenue_growth': revenue_growth,
        'avg_order_value': float(avg_order_value),
        'avg_processing_time': avg_processing_time,
        
        # Vendor stats (filtered)
        'top_vendors': top_vendors,
        'total_vendor_revenue': float(total_vendor_revenue),
        'top_products': top_products,
        
        # Payment stats (filtered)
        'mpesa_orders': mpesa_orders,
        'cash_orders': cash_orders,
        'pochi_orders': pochi_orders,
        'total_commission': float(total_commission),
        'total_paid_to_vendors': float(total_paid_to_vendors),
        
        # Document stats (all time)
        'vendors_with_docs': vendors_with_docs,
        'vendors_with_kra': vendors_with_kra,
        
        # Customer messages (filtered)
        'unread_messages': unread_messages,
        'total_messages': total_messages,
        
        # Recent activity (filtered)
        'recent_activity': recent_activity,
        
        # Metadata
        'today': timezone.now(),
        'range_text': range_text,
        'days': days,
    }
    
    return render(request, 'admin_dashboard/analytics.html', context)


# Add this API endpoint for real-time updates
@staff_member_required
def analytics_live_data(request):
    """Return latest metrics for real-time updates"""
    last_minute = timezone.now() - timedelta(minutes=1)
    
    new_orders = Order.objects.filter(created_at__gte=last_minute).count()
    
    new_revenue = 0
    new_items = OrderItem.objects.filter(
        order__in=Order.objects.filter(
            status='completed',
            paid=True,
            created_at__gte=last_minute
        )
    )
    for item in new_items:
        new_revenue += item.quantity * item.price
    
    return JsonResponse({
        'new_orders': new_orders,
        'new_revenue': float(new_revenue),
        'timestamp': timezone.now().isoformat(),
    })

    
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