# vendors/admin.py
from django.contrib import admin
from django.utils import timezone
from accounts.models import Business  # Change this to local import

@admin.register(Business)
class BusinessAdmin(admin.ModelAdmin):
    list_display = ['name', 'owner', 'county', 'verification_status', 'is_active']
    list_filter = ['verification_status', 'is_active', 'county', 'business_type']
    search_fields = ['name', 'owner__username', 'county', 'location']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('owner', 'name', 'slug', 'phone', 'email', 'logo')
        }),
        ('Location Information', {
            'fields': ('location', 'latitude', 'longitude', 'county', 'sub_county', 
                      'ward', 'landmark', 'delivery_radius', 'show_exact_location'),
            'classes': ('wide',),
            'description': 'Enter location details. For accurate distance calculation, provide latitude and longitude.'
        }),
        ('Business Details', {
            'fields': ('business_type', 'business_description')
        }),
        ('Verification Documents', {
            'fields': ('business_registration_number', 'business_registration_cert',
                      'kra_pin', 'kra_certificate', 'tax_compliance_cert',
                      'owner_id_number', 'owner_id_front', 'owner_id_back',
                      'business_permit', 'permit_expiry_date', 'additional_docs'),
            'classes': ('wide', 'collapse'),
        }),
        ('Verification Status', {
            'fields': ('verification_status', 'verification_notes', 'verified_by', 'verified_at'),
            'classes': ('wide',),
        }),
        ('Status', {
            'fields': ('is_approved', 'is_rejected', 'is_active')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'documents_uploaded_at', 'documents_updated_at'),
            'classes': ('collapse',),
        }),
    )
    
    readonly_fields = ['slug', 'created_at', 'documents_updated_at', 'verified_at']
    
    actions = ['mark_as_verified', 'mark_as_rejected']
    
    def mark_as_verified(self, request, queryset):
        queryset.update(
            verification_status='verified',
            verified_by=request.user,
            verified_at=timezone.now()
        )
    mark_as_verified.short_description = "Mark selected businesses as verified"
    
    def mark_as_rejected(self, request, queryset):
        queryset.update(verification_status='rejected', verified_by=request.user)
    mark_as_rejected.short_description = "Mark selected businesses as rejected"