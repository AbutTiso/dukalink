from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.conf import settings
import json
import requests

# Import Business from accounts app
from accounts.models import Business

def vendor_list(request):
    """Main vendor listing page"""
    # Get all verified and active vendors
    vendors = Business.objects.filter(
        verification_status='verified',
        is_active=True
    ).exclude(
        latitude__isnull=True,
        longitude__isnull=True
    ).order_by('-created_at')
    
    # Get user's location from session if available
    user_location = request.session.get('user_location', {})
    
    context = {
        'all_vendors': vendors,
        'user_lat': user_location.get('latitude'),
        'user_lng': user_location.get('longitude'),
        'google_maps_key': getattr(settings, 'GOOGLE_MAPS_API_KEY', None),
    }
    return render(request, 'vendors/vendor_list.html', context)

@csrf_exempt
@require_POST
def save_user_location(request):
    """Save user location to session"""
    try:
        data = json.loads(request.body)
        request.session['user_location'] = {
            'latitude': data.get('latitude'),
            'longitude': data.get('longitude'),
            'accuracy': data.get('accuracy', 0),
            'timestamp': timezone.now().isoformat()
        }
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)

def get_nearby_vendors(request):
    """
    Get vendors near user location - like Google Maps
    Returns vendors with distance, travel time, and delivery info
    """
    try:
        lat = float(request.GET.get('latitude'))
        lng = float(request.GET.get('longitude'))
        radius = float(request.GET.get('radius', 10))
        query = request.GET.get('q', '')  # Optional search query
        
        # Use the enhanced find_nearby method
        if query:
            results = Business.search_by_location(query, lat, lng, radius)
        else:
            results = Business.find_nearby(lat, lng, radius)
        
        vendors_data = []
        for item in results:
            business = item['business']
            vendors_data.append({
                'id': business.id,
                'name': business.name,
                'slug': business.slug,
                'location': business.get_location_summary(),
                'full_address': business.formatted_address or business.full_address,
                'distance': item['distance_km'],
                'distance_mi': item.get('distance_mi', round(item['distance_km'] * 0.621371, 1)),
                'drive_time': item.get('drive_time_minutes', int((item['distance_km'] / 30) * 60)),
                'walk_time': item.get('walk_time_minutes', int((item['distance_km'] / 5) * 60)),
                'can_deliver': item.get('can_deliver', item['distance_km'] <= business.delivery_radius),
                'delivery_fee': item.get('delivery_fee'),
                'product_count': business.product_set.count() if hasattr(business, 'product_set') else 0,
                'latitude': business.latitude,
                'longitude': business.longitude,
                'phone': business.phone,
                'county': business.county or 'Nairobi',
                'is_verified': business.is_verified,
                'delivery_radius': business.delivery_radius,
                'place_id': business.place_id,
            })
        
        return JsonResponse({
            'success': True,
            'vendors': vendors_data,
            'count': len(vendors_data),
            'radius': radius,
            'center': {'lat': lat, 'lng': lng},
            'query': query if query else None
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)

def get_client_ip_location(request):
    """Get approximate location from IP address"""
    try:
        # Get client IP
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        
        # Use ip-api.com free service
        response = requests.get(f'http://ip-api.com/json/{ip}', timeout=3)
        
        if response.status_code == 200:
            data = response.json()
            if data.get('status') == 'success':
                return JsonResponse({
                    'success': True,
                    'latitude': data['lat'],
                    'longitude': data['lon'],
                    'city': data['city'],
                    'region': data['regionName'],
                    'country': data['country'],
                    'isp': data.get('isp', '')
                })
        
        return JsonResponse({'success': False}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)

def get_vendors_by_county(request):
    """Filter vendors by county"""
    try:
        county = request.GET.get('county', '')
        if county:
            vendors = Business.get_by_county(county)
            
            vendors_data = []
            for vendor in vendors:
                vendors_data.append({
                    'id': vendor.id,
                    'name': vendor.name,
                    'slug': vendor.slug,
                    'location': vendor.get_location_summary(),
                    'county': vendor.county,
                    'product_count': vendor.product_set.count() if hasattr(vendor, 'product_set') else 0,
                    'latitude': vendor.latitude,
                    'longitude': vendor.longitude,
                })
            
            return JsonResponse({
                'success': True,
                'vendors': vendors_data,
                'count': len(vendors_data)
            })
        else:
            return JsonResponse({
                'success': False,
                'error': 'County parameter required'
            }, status=400)
            
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)

def geocode_address(request):
    """
    Convert address to coordinates - like Google Maps geocoding
    """
    try:
        address = request.GET.get('address', '')
        if not address:
            return JsonResponse({'success': False, 'error': 'Address required'}, status=400)
        
        # Try Google Maps first
        if hasattr(settings, 'GOOGLE_MAPS_API_KEY'):
            url = "https://maps.googleapis.com/maps/api/geocode/json"
            params = {
                'address': f"{address}, Kenya",
                'key': settings.GOOGLE_MAPS_API_KEY
            }
            response = requests.get(url, params=params, timeout=5)
            if response.status_code == 200:
                data = response.json()
                if data['status'] == 'OK' and data['results']:
                    result = data['results'][0]
                    location = result['geometry']['location']
                    return JsonResponse({
                        'success': True,
                        'latitude': location['lat'],
                        'longitude': location['lng'],
                        'formatted_address': result['formatted_address'],
                        'place_id': result['place_id']
                    })
        
        # Fallback to Nominatim
        url = "https://nominatim.openstreetmap.org/search"
        params = {
            'q': f"{address}, Kenya",
            'format': 'json',
            'limit': 1
        }
        headers = {'User-Agent': 'DukaLink/1.0'}
        response = requests.get(url, params=params, headers=headers, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            if data:
                return JsonResponse({
                    'success': True,
                    'latitude': float(data[0]['lat']),
                    'longitude': float(data[0]['lon']),
                    'formatted_address': data[0].get('display_name', address)
                })
        
        return JsonResponse({'success': False, 'error': 'Could not geocode address'}, status=400)
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)

def reverse_geocode(request):
    """
    Convert coordinates to address - like Google Maps reverse geocoding
    """
    try:
        lat = request.GET.get('lat')
        lng = request.GET.get('lng')
        
        if not lat or not lng:
            return JsonResponse({'success': False, 'error': 'Coordinates required'}, status=400)
        
        # Try Google Maps first
        if hasattr(settings, 'GOOGLE_MAPS_API_KEY'):
            url = "https://maps.googleapis.com/maps/api/geocode/json"
            params = {
                'latlng': f"{lat},{lng}",
                'key': settings.GOOGLE_MAPS_API_KEY
            }
            response = requests.get(url, params=params, timeout=5)
            if response.status_code == 200:
                data = response.json()
                if data['status'] == 'OK' and data['results']:
                    return JsonResponse({
                        'success': True,
                        'address': data['results'][0]['formatted_address'],
                        'place_id': data['results'][0]['place_id']
                    })
        
        # Fallback to Nominatim
        url = "https://nominatim.openstreetmap.org/reverse"
        params = {
            'lat': lat,
            'lng': lng,
            'format': 'json'
        }
        headers = {'User-Agent': 'DukaLink/1.0'}
        response = requests.get(url, params=params, headers=headers, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            return JsonResponse({
                'success': True,
                'address': data.get('display_name', '')
            })
        
        return JsonResponse({'success': False, 'error': 'Could not reverse geocode'}, status=400)
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)
    

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Sum, Count, Q
from datetime import timedelta
import json

from accounts.models import Business
from products.models import Product
from orders.models import Order, OrderItem


@login_required
def vendor_analytics(request):
    """Vendor analytics dashboard with real data"""
    
    # Get vendor's business
    try:
        business = Business.objects.get(owner=request.user)
    except Business.DoesNotExist:
        messages.error(request, "You need to register a business first!")
        return redirect("accounts:register_business")
    
    # Check verification
    if not business.is_verified:
        messages.warning(request, "Your account needs to be verified to access analytics.")
        return redirect("vendors:vendor_dashboard")
    
    # Get vendor's products
    vendor_products = Product.objects.filter(business=business, is_available=True)
    product_ids = vendor_products.values_list('id', flat=True)
    
    # Get orders containing vendor's products
    vendor_order_items = OrderItem.objects.filter(
        product_id__in=product_ids
    ).select_related('order', 'product')
    
    # Get unique orders
    order_ids = vendor_order_items.values_list('order_id', flat=True).distinct()
    orders = Order.objects.filter(id__in=order_ids)
    completed_orders = orders.filter(status='completed', paid=True)
    
    # ============== TIME PERIOD FILTERING ==============
    days = int(request.GET.get('range', 30))  # Default to 30 days
    if days == 0:
        start_date = timezone.datetime(2020, 1, 1)  # All time
        range_text = 'All time'
    else:
        start_date = timezone.now() - timedelta(days=days)
        range_text = f'Last {days} days'
    
    # Filtered orders
    filtered_orders = orders.filter(created_at__gte=start_date)
    filtered_completed = completed_orders.filter(created_at__gte=start_date)
    filtered_items = vendor_order_items.filter(order__created_at__gte=start_date)
    
    # ============== KEY METRICS ==============
    
    # 1. Revenue Metrics
    total_revenue = 0
    for item in vendor_order_items.filter(order__status='completed', order__paid=True):
        total_revenue += item.price * item.quantity
    
    filtered_revenue = 0
    for item in filtered_items.filter(order__status='completed', order__paid=True):
        filtered_revenue += item.price * item.quantity
    
    # 2. Order Metrics
    total_orders = orders.count()
    filtered_orders_count = filtered_orders.count()
    
    completed_count = completed_orders.count()
    filtered_completed_count = filtered_completed.count()
    
    pending_count = orders.filter(status='pending').count()
    processing_count = orders.filter(status='processing').count()
    cancelled_count = orders.filter(status='cancelled').count()
    
    # 3. Customer Metrics
    unique_customers = orders.values('customer_phone').distinct().count()
    filtered_customers = filtered_orders.values('customer_phone').distinct().count()
    
    # 4. Product Metrics
    products_sold = vendor_order_items.aggregate(total=Sum('quantity'))['total'] or 0
    filtered_products_sold = filtered_items.aggregate(total=Sum('quantity'))['total'] or 0
    
    # 5. Average Order Value
    avg_order_value = filtered_revenue / filtered_completed_count if filtered_completed_count > 0 else 0
    
    # 6. Growth Calculations
    previous_start = start_date - timedelta(days=days)
    previous_orders = orders.filter(
        created_at__gte=previous_start,
        created_at__lt=start_date
    )
    previous_revenue = 0
    for item in vendor_order_items.filter(
        order__in=previous_orders,
        order__status='completed',
        order__paid=True
    ):
        previous_revenue += item.price * item.quantity
    
    revenue_growth = 0
    if previous_revenue > 0:
        revenue_growth = ((filtered_revenue - previous_revenue) / previous_revenue) * 100
    
    orders_growth = 0
    previous_count = previous_orders.count()
    if previous_count > 0:
        orders_growth = ((filtered_orders_count - previous_count) / previous_count) * 100
    
    # ============== CHART DATA ==============
    
    # 1. Daily Revenue (Last 30 Days)
    daily_labels = []
    daily_revenue = []
    daily_orders = []
    
    for i in range(29, -1, -1):
        day = timezone.now() - timedelta(days=i)
        day_start = day.replace(hour=0, minute=0, second=0)
        day_end = day.replace(hour=23, minute=59, second=59)
        
        day_orders = filtered_completed.filter(created_at__range=[day_start, day_end])
        day_revenue = 0
        for item in vendor_order_items.filter(order__in=day_orders):
            day_revenue += item.price * item.quantity
        
        daily_labels.append(day.strftime('%d %b'))
        daily_revenue.append(float(day_revenue))
        daily_orders.append(day_orders.count())
    
    # 2. Order Status Distribution
    status_data = {
        'pending': pending_count,
        'processing': processing_count,
        'completed': completed_count,
        'cancelled': cancelled_count,
    }
    
    # 3. Top Products
    product_sales = {}
    for item in vendor_order_items.filter(order__status='completed', order__paid=True):
        if item.product.id not in product_sales:
            product_sales[item.product.id] = {
                'id': item.product.id,
                'name': item.product.name,
                'quantity': 0,
                'revenue': 0
            }
        product_sales[item.product.id]['quantity'] += item.quantity
        product_sales[item.product.id]['revenue'] += item.price * item.quantity
    
    top_products = sorted(product_sales.values(), key=lambda x: x['revenue'], reverse=True)[:5]
    
    # 4. Hourly Distribution
    hourly_counts = [0] * 24
    for order in filtered_orders:
        hour = order.created_at.hour
        hourly_counts[hour] += 1
    
    # 5. Payment Methods
    payment_methods = {
        'M-Pesa': filtered_orders.filter(payment_method__icontains='mpesa').count(),
        'Cash on Delivery': filtered_orders.filter(payment_method='cash_on_delivery').count(),
        'Pochi': filtered_orders.filter(payment_method='pochi_biashara').count(),
    }
    
    # 6. Weekly Performance (Last 7 days)
    week_labels = []
    week_revenue = []
    week_orders = []
    
    for i in range(6, -1, -1):
        day = timezone.now() - timedelta(days=i)
        day_start = day.replace(hour=0, minute=0, second=0)
        day_end = day.replace(hour=23, minute=59, second=59)
        
        day_orders = filtered_completed.filter(created_at__range=[day_start, day_end])
        day_revenue = 0
        for item in vendor_order_items.filter(order__in=day_orders):
            day_revenue += item.price * item.quantity
        
        week_labels.append(day.strftime('%a'))
        week_revenue.append(float(day_revenue))
        week_orders.append(day_orders.count())
    
    # ============== CONTEXT ==============
    context = {
        'business': business,
        'range_text': range_text,
        'days': days,
        
        # Key metrics
        'total_revenue': filtered_revenue,
        'all_time_revenue': total_revenue,
        'total_orders': filtered_orders_count,
        'all_time_orders': total_orders,
        'completed_orders': filtered_completed_count,
        'pending_orders': pending_count,
        'processing_orders': processing_count,
        'cancelled_orders': cancelled_count,
        'unique_customers': filtered_customers,
        'all_time_customers': unique_customers,
        'products_sold': filtered_products_sold,
        'all_time_products': products_sold,
        'avg_order_value': avg_order_value,
        'revenue_growth': round(revenue_growth, 1),
        'orders_growth': round(orders_growth, 1),
        
        # Chart data
        'daily_labels': json.dumps(daily_labels),
        'daily_revenue': json.dumps(daily_revenue),
        'daily_orders': json.dumps(daily_orders),
        'week_labels': json.dumps(week_labels),
        'week_revenue': json.dumps(week_revenue),
        'week_orders': json.dumps(week_orders),
        'status_data': json.dumps(status_data),
        'top_products': top_products,
        'hourly_counts': json.dumps(hourly_counts),
        'payment_methods': json.dumps(payment_methods),
        
        # Timestamps
        'today': timezone.now(),
    }
    
    return render(request, 'vendors/analytics.html', context)

