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