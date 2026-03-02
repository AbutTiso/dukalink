from django.db import models
from django.contrib.auth.models import User
from django.utils.text import slugify
from django.utils import timezone
from math import radians, sin, cos, sqrt, asin
import requests
import time
from django.conf import settings
import urllib.parse

class Business(models.Model):
    owner = models.OneToOneField(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=200)
    slug = models.SlugField(unique=True, blank=True)
    phone = models.CharField(max_length=20)
    location = models.CharField(max_length=255, blank=True, null=True)
    email = models.EmailField(blank=True)
    logo = models.ImageField(upload_to='business_logos/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    # ============== LOCATION FIELDS ==============
    latitude = models.FloatField(
        blank=True, 
        null=True,
        help_text="Vendor's location latitude (e.g., -1.286389 for Nairobi)"
    )
    longitude = models.FloatField(
        blank=True, 
        null=True,
        help_text="Vendor's location longitude (e.g., 36.817223 for Nairobi)"
    )
    
    # Kenyan administrative divisions
    county = models.CharField(
        max_length=100, 
        blank=True, 
        null=True,
        help_text="County (e.g., Nairobi, Mombasa, Kisumu)"
    )
    sub_county = models.CharField(
        max_length=100, 
        blank=True, 
        null=True,
        help_text="Sub-county/Constituency"
    )
    ward = models.CharField(
        max_length=100, 
        blank=True, 
        null=True,
        help_text="Ward/Location"
    )
    landmark = models.CharField(
        max_length=200, 
        blank=True, 
        null=True,
        help_text="Nearby landmark for easier finding"
    )
    delivery_radius = models.FloatField(
        default=10.0,
        help_text="Maximum delivery distance in kilometers"
    )
    
    # Location visibility settings
    show_exact_location = models.BooleanField(
        default=False,
        help_text="Show exact location on map or just approximate area"
    )
    
    # Enhanced geocoding fields
    place_id = models.CharField(
        max_length=255, 
        blank=True, 
        null=True,
        help_text="Google Maps Place ID for accurate location"
    )
    formatted_address = models.TextField(
        blank=True, 
        null=True,
        help_text="Full formatted address from geocoding service"
    )
    last_geocoded_at = models.DateTimeField(
        blank=True, 
        null=True,
        help_text="When this business was last geocoded"
    )
    geocoding_attempts = models.IntegerField(
        default=0,
        help_text="Number of geocoding attempts"
    )
    
    # Status fields
    is_approved = models.BooleanField(default=False)
    is_rejected = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    
    # ============== BUSINESS VERIFICATION DOCUMENTS ==============
    BUSINESS_TYPES = [
        ('retail', 'Retail Shop'),
        ('wholesale', 'Wholesale'),
        ('manufacturer', 'Manufacturer'),
        ('distributor', 'Distributor'),
        ('service', 'Service Provider'),
        ('restaurant', 'Restaurant/Food'),
        ('electronics', 'Electronics'),
        ('fashion', 'Fashion/Clothing'),
        ('agriculture', 'Agriculture/Fresh Produce'),
        ('other', 'Other'),
    ]
    
    business_type = models.CharField(max_length=20, choices=BUSINESS_TYPES, default='retail')
    business_description = models.TextField(blank=True, null=True)
    
    # Kenyan Business Registration Documents
    business_registration_number = models.CharField(max_length=50, blank=True, null=True)
    business_registration_cert = models.FileField(
        upload_to='vendor_docs/registration/',
        blank=True, 
        null=True,
        help_text="Certificate of Business Registration/BRS (PDF or Image)"
    )
    
    # KRA Documents
    kra_pin = models.CharField(max_length=20, blank=True, null=True, help_text="KRA PIN (e.g., P012345678B)")
    kra_certificate = models.FileField(
        upload_to='vendor_docs/kra/',
        blank=True, 
        null=True,
        help_text="KRA PIN Certificate (PDF or Image)"
    )
    
    # Tax Compliance
    tax_compliance_cert = models.FileField(
        upload_to='vendor_docs/tax/',
        blank=True, 
        null=True,
        help_text="Tax Compliance Certificate (PDF or Image)"
    )
    
    # ID Documents
    owner_id_number = models.CharField(max_length=20, blank=True, null=True, help_text="National ID/Passport Number")
    owner_id_front = models.ImageField(
        upload_to='vendor_docs/id_front/',
        blank=True, 
        null=True,
        help_text="National ID Front Image"
    )
    owner_id_back = models.ImageField(
        upload_to='vendor_docs/id_back/',
        blank=True, 
        null=True,
        help_text="National ID Back Image"
    )
    
    # Business Permit (County Government)
    business_permit = models.FileField(
        upload_to='vendor_docs/permits/',
        blank=True, 
        null=True,
        help_text="Single Business Permit from County Government"
    )
    permit_expiry_date = models.DateField(blank=True, null=True)
    
    # Additional Documents
    additional_docs = models.FileField(
        upload_to='vendor_docs/additional/',
        blank=True, 
        null=True,
        help_text="Additional supporting documents (optional)"
    )
    
    # ============== VERIFICATION WORKFLOW ==============
    VERIFICATION_STATUS = [
        ('pending', '⏳ Pending Verification'),
        ('under_review', '📋 Under Review'),
        ('verified', '✅ Verified'),
        ('rejected', '❌ Rejected'),
        ('info_needed', 'ℹ️ More Info Needed')
    ]
    
    verification_status = models.CharField(
        max_length=20,
        choices=VERIFICATION_STATUS,
        default='pending'
    )
    verification_notes = models.TextField(
        blank=True, 
        null=True,
        help_text="Admin notes about verification decision"
    )
    verified_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='verified_businesses'
    )
    verified_at = models.DateTimeField(blank=True, null=True)
    
    # ============== DOCUMENT TRACKING ==============
    documents_uploaded_at = models.DateTimeField(blank=True, null=True)
    documents_updated_at = models.DateTimeField(auto_now=True)
    
    # ============== AUTO-GEOCODING ==============
    _skip_geocode = False
    
    def save(self, *args, **kwargs):
        # Auto-generate slug
        if not self.slug:
            base_slug = slugify(self.name)
            slug = base_slug
            counter = 1
            while Business.objects.filter(slug=slug).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        
        # Auto-geocode if location exists but coordinates are missing
        if not self._skip_geocode and self.location and (not self.latitude or not self.longitude):
            self.geocode_with_precision()
            
        super().save(*args, **kwargs)
    
    def geocode_with_precision(self, force=False):
        """
        Advanced geocoding with multiple services for maximum accuracy
        Like Google Maps - finds exact locations
        """
        if not self.location:
            return False
            
        # Don't retry too many times
        if self.geocoding_attempts > 3 and not force:
            return False
            
        self.geocoding_attempts += 1
        
        # Build precise address
        address_parts = []
        if self.location:
            address_parts.append(self.location)
        if self.landmark:
            address_parts.append(f"near {self.landmark}")
        if self.ward:
            address_parts.append(self.ward)
        if self.sub_county:
            address_parts.append(self.sub_county)
        if self.county:
            address_parts.append(self.county)
        
        # Always add Kenya for context
        address_parts.append("Kenya")
        full_address = ", ".join(address_parts)
        
        # Try geocoding services in order of preference
        coordinates = None
        formatted_addr = None
        place_id = None
        
        # 1. Try Geoapify (free, generous limits)
        if hasattr(settings, 'GEOAPIFY_API_KEY'):
            coordinates, formatted_addr = self._geocode_with_geoapify(full_address)
        
        # 2. Try LocationIQ (if available)
        if not coordinates and hasattr(settings, 'LOCATIONIQ_API_KEY'):
            coordinates, formatted_addr = self._geocode_with_locationiq(full_address)
        
        # 3. Try OpenStreetMap (free, rate-limited)
        if not coordinates:
            coordinates, formatted_addr = self._geocode_with_nominatim(full_address)
        
        # 4. Fallback to Kenya database
        if not coordinates:
            coordinates = self._geocode_with_kenya_database()
            if coordinates:
                formatted_addr = f"{self.location or ''}, {self.county or ''}, Kenya"
        
        if coordinates:
            self.latitude, self.longitude = coordinates
            self.formatted_address = formatted_addr or full_address
            self.last_geocoded_at = timezone.now()
            return True
            
        return False
    
    def _geocode_with_geoapify(self, address):
        """Use Geoapify API (free tier - 3000 requests/day)"""
        api_key = getattr(settings, 'GEOAPIFY_API_KEY', None)
        if not api_key:
            return None, None
            
        try:
            url = "https://api.geoapify.com/v1/geocode/search"
            params = {
                'text': address,
                'apiKey': api_key,
                'format': 'json',
                'limit': 1,
                'filter': 'countrycode:ke'  # Limit to Kenya
            }
            
            response = requests.get(url, params=params, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('results') and len(data['results']) > 0:
                    result = data['results'][0]
                    lat = result['lat']
                    lon = result['lon']
                    formatted = result.get('formatted', address)
                    return (lat, lon), formatted
            else:
                print(f"Geoapify error: {response.status_code}")
        except Exception as e:
            print(f"Geoapify error: {e}")
        return None, None
    
    def _geocode_with_locationiq(self, address):
        """Use LocationIQ API (good free alternative)"""
        api_key = getattr(settings, 'LOCATIONIQ_API_KEY', None)
        if not api_key:
            return None, None
            
        try:
            url = "https://us1.locationiq.com/v1/search.php"
            params = {
                'key': api_key,
                'q': address,
                'format': 'json',
                'countrycodes': 'ke',
                'limit': 1,
                'addressdetails': 1
            }
            
            response = requests.get(url, params=params, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                if data and len(data) > 0:
                    lat = float(data[0]['lat'])
                    lon = float(data[0]['lon'])
                    display_name = data[0].get('display_name', address)
                    return (lat, lon), display_name
        except Exception as e:
            print(f"LocationIQ error: {e}")
        return None, None
    
    def _geocode_with_nominatim(self, address):
        """Use OpenStreetMap Nominatim (free, rate-limited)"""
        try:
            url = "https://nominatim.openstreetmap.org/search"
            params = {
                'q': address,
                'format': 'json',
                'limit': 1,
                'countrycodes': 'ke',
                'addressdetails': 1
            }
            headers = {
                'User-Agent': 'DukaLink/1.0 (https://dukalink.co.ke)'
            }
            
            response = requests.get(url, params=params, headers=headers, timeout=5)
            time.sleep(1)  # Respect rate limits
            
            if response.status_code == 200:
                data = response.json()
                if data and len(data) > 0:
                    lat = float(data[0]['lat'])
                    lon = float(data[0]['lon'])
                    display_name = data[0].get('display_name', address)
                    return (lat, lon), display_name
        except Exception as e:
            print(f"Nominatim error: {e}")
        return None, None
    
    def _geocode_with_kenya_database(self):
        """Fallback: Enhanced Kenyan towns database with more locations"""
        kenya_locations = {
            # Major cities with neighborhoods
            'nairobi': (-1.286389, 36.817223),
            'nairobi cbd': (-1.283333, 36.816667),
            'westlands': (-1.269167, 36.812778),
            'kilimani': (-1.283333, 36.783333),
            'kileleshwa': (-1.283333, 36.783333),
            'lavington': (-1.283333, 36.766667),
            'karen': (-1.316667, 36.683333),
            'langata': (-1.366667, 36.733333),
            'south b': (-1.333333, 36.866667),
            'south c': (-1.333333, 36.866667),
            'buruburu': (-1.283333, 36.883333),
            'donholm': (-1.300000, 36.883333),
            'umoja': (-1.300000, 36.883333),
            'kayole': (-1.266667, 36.916667),
            'embakasi': (-1.316667, 36.900000),
            'ruiru': (-1.150000, 36.966667),
            'juja': (-1.100000, 37.016667),
            'thika': (-1.039444, 37.089443),
            'kiambu': (-1.166667, 36.833333),
            'limuru': (-1.100000, 36.650000),
            
            # Mombasa
            'mombasa': (-4.043477, 39.668205),
            'nyali': (-4.033333, 39.700000),
            'bamburi': (-4.000000, 39.716667),
            'shanzu': (-3.983333, 39.733333),
            'kisauni': (-4.033333, 39.666667),
            'likoni': (-4.083333, 39.650000),
            
            # Kisumu
            'kisumu': (-0.102225, 34.761715),
            'milimani': (-0.100000, 34.750000),
            'kondele': (-0.116667, 34.766667),
            'nyalenda': (-0.116667, 34.750000),
            
            # Nakuru
            'nakuru': (-0.303099, 36.080026),
            'nakuru town': (-0.303099, 36.080026),
            'lanet': (-0.283333, 36.133333),
            'naivasha': (-0.716667, 36.433333),
            'gilgil': (-0.500000, 36.333333),
            
            # Eldoret
            'eldoret': (0.514277, 35.269780),
            'eldoret town': (0.514277, 35.269780),
            'langas': (0.500000, 35.266667),
        }
        
        search_text = f"{self.location or ''} {self.landmark or ''} {self.ward or ''} {self.county or ''}".lower()
        
        # Try exact matches first
        for location, coords in kenya_locations.items():
            if location in search_text:
                return coords
        
        # Then try partial matches
        for location, coords in kenya_locations.items():
            words = location.split()
            for word in words:
                if len(word) > 3 and word in search_text:
                    return coords
        
        return None
    
    @classmethod
    def batch_geocode(cls, limit=None):
        """
        Batch geocode all businesses without coordinates
        Returns (success_count, failed_count)
        """
        businesses = cls.objects.filter(
            location__isnull=False
        ).exclude(
            location=''
        ).filter(
            latitude__isnull=True,
            longitude__isnull=True
        )
        
        if limit:
            businesses = businesses[:limit]
        
        success = 0
        failed = 0
        
        for business in businesses:
            # Set flag to prevent recursion
            business._skip_geocode = True
            if business.geocode_with_precision():
                business.save()
                success += 1
            else:
                failed += 1
            business._skip_geocode = False
            
            # Small delay to respect rate limits
            time.sleep(1.1)
        
        return success, failed

    def __str__(self):
        location_info = f" - {self.location}" if self.location else ""
        return f"{self.name}{location_info} ({self.get_verification_status_display()})"
    
    # ============== LOCATION METHODS ==============
    def distance_to(self, lat2, lon2):
        """
        Calculate distance to another point in kilometers using Haversine formula
        Returns None if business location is not set
        """
        if not self.latitude or not self.longitude:
            return None
            
        # Earth's radius in kilometers
        R = 6371
        
        lat1, lon1 = radians(self.latitude), radians(self.longitude)
        lat2, lon2 = radians(lat2), radians(lon2)
        
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * asin(sqrt(a))
        
        return round(R * c, 1)  # Round to 1 decimal place
    
    def get_location_summary(self):
        """Return a formatted location summary"""
        parts = []
        if self.landmark:
            parts.append(f"Near {self.landmark}")
        if self.ward:
            parts.append(self.ward)
        if self.sub_county:
            parts.append(self.sub_county)
        if self.county:
            parts.append(self.county)
        elif self.location:
            return self.location
        
        return ", ".join(parts) if parts else self.location or "Location not set"
    
    def get_coordinates(self):
        """Return coordinates as tuple if available"""
        if self.latitude and self.longitude:
            return (self.latitude, self.longitude)
        return None
    
    def is_deliverable_to(self, lat, lon):
        """
        Check if location is within delivery radius
        Returns tuple: (bool, distance)
        """
        distance = self.distance_to(lat, lon)
        if distance is not None:
            return (distance <= self.delivery_radius, distance)
        return (False, None)
    
    @classmethod
    def get_nearby_vendors(cls, latitude, longitude, radius_km=10, verified_only=True):
        """
        Get vendors within specified radius
        Uses Python-side filtering (works with any database)
        """
        # Base queryset
        vendors = cls.objects.all()
        
        if verified_only:
            vendors = vendors.filter(verification_status='verified', is_active=True)
        
        # Filter out vendors without coordinates
        vendors = vendors.exclude(latitude__isnull=True, longitude__isnull=True)
        
        # Calculate distances and filter
        nearby = []
        for vendor in vendors:
            distance = vendor.distance_to(latitude, longitude)
            if distance and distance <= radius_km:
                nearby.append({
                    'vendor': vendor,
                    'distance': distance
                })
        
        # Sort by distance
        nearby.sort(key=lambda x: x['distance'])
        
        return nearby
    
    @classmethod
    def find_nearby(cls, latitude, longitude, radius_km=10, limit=50):
        """
        Find businesses near a location, sorted by distance
        Like Google Maps - returns results with distance and estimated time
        """
        # Get all verified active businesses with coordinates
        businesses = cls.objects.filter(
            verification_status='verified',
            is_active=True
        ).exclude(
            latitude__isnull=True,
            longitude__isnull=True
        )
        
        # Calculate distances and add metadata
        results = []
        for business in businesses:
            distance = business.distance_to(latitude, longitude)
            if distance and distance <= radius_km:
                # Calculate estimated travel time (rough estimate)
                # Assuming average speed of 30 km/h in city
                drive_time_minutes = int((distance / 30) * 60)
                
                results.append({
                    'business': business,
                    'distance_km': distance,
                    'distance_mi': round(distance * 0.621371, 1),
                    'drive_time_minutes': drive_time_minutes,
                    'walk_time_minutes': int((distance / 5) * 60),
                    'can_deliver': distance <= business.delivery_radius,
                    'delivery_fee': cls._estimate_delivery_fee(distance)
                })
        
        # Sort by distance (closest first)
        results.sort(key=lambda x: x['distance_km'])
        
        return results[:limit]
    
    @staticmethod
    def _estimate_delivery_fee(distance_km):
        """Estimate delivery fee based on distance"""
        if distance_km <= 2:
            return 100
        elif distance_km <= 5:
            return 200
        elif distance_km <= 10:
            return 350
        elif distance_km <= 20:
            return 500
        else:
            return None
    
    @classmethod
    def get_by_county(cls, county):
        """Get vendors in a specific county"""
        return cls.objects.filter(
            county__iexact=county,
            verification_status='verified',
            is_active=True
        )
    
    # ============== PROPERTIES ==============
    @property
    def is_verified(self):
        return self.verification_status == 'verified'
    
    @property
    def documents_complete(self):
        required_docs = [
            self.business_registration_cert,
            self.kra_certificate,
            self.owner_id_front,
            self.owner_id_back,
            self.business_permit
        ]
        return all(doc for doc in required_docs)
    
    @property
    def missing_documents(self):
        missing = []
        if not self.business_registration_cert:
            missing.append('Business Registration Certificate')
        if not self.kra_certificate:
            missing.append('KRA PIN Certificate')
        if not self.owner_id_front:
            missing.append('National ID - Front')
        if not self.owner_id_back:
            missing.append('National ID - Back')
        if not self.business_permit:
            missing.append('Business Permit')
        return missing
    
    @property
    def days_since_registration(self):
        delta = timezone.now().date() - self.created_at.date()
        return delta.days
    
    @property
    def permit_is_valid(self):
        if self.permit_expiry_date:
            return self.permit_expiry_date >= timezone.now().date()
        return False
    
    @property
    def uploaded_documents_count(self):
        count = 0
        if self.business_registration_cert:
            count += 1
        if self.kra_certificate:
            count += 1
        if self.owner_id_front:
            count += 1
        if self.owner_id_back:
            count += 1
        if self.business_permit:
            count += 1
        return count
    
    @property
    def full_address(self):
        parts = []
        if self.location:
            parts.append(self.location)
        if self.landmark:
            parts.append(f"near {self.landmark}")
        if self.ward:
            parts.append(self.ward)
        if self.sub_county:
            parts.append(self.sub_county)
        if self.county:
            parts.append(self.county)
        
        return ", ".join(parts) if parts else "Address not provided"
    
    @property
    def map_link(self):
        if self.latitude and self.longitude:
            return f"https://www.google.com/maps?q={self.latitude},{self.longitude}"
        elif self.location:
            encoded = urllib.parse.quote(self.location)
            return f"https://www.google.com/maps/search/?api=1&query={encoded}"
        return None
    
    @property
    def whatsapp_location(self):
        if self.latitude and self.longitude:
            return f"https://maps.google.com/?q={self.latitude},{self.longitude}"
        return self.full_address
    
    class Meta:
        indexes = [
            models.Index(fields=['county', 'verification_status']),
            models.Index(fields=['latitude', 'longitude']),
        ]
        ordering = ['-created_at']