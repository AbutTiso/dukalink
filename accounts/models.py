from django.db import models
from django.contrib.auth.models import User
from django.utils.text import slugify
from django.utils import timezone

class Business(models.Model):
    owner = models.OneToOneField(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=200)
    slug = models.SlugField(unique=True, blank=True)
    phone = models.CharField(max_length=20)
    location = models.CharField(max_length=255, blank=True, null=True)
    email = models.EmailField(blank=True)
    logo = models.ImageField(upload_to='business_logos/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
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
    
    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name)
            slug = base_slug
            counter = 1
            while Business.objects.filter(slug=slug).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.get_verification_status_display()})"
    
    # ============== PROPERTIES ==============
    @property
    def is_verified(self):
        return self.verification_status == 'verified'
    
    @property
    def documents_complete(self):
        """Check if all required documents are uploaded"""
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
        """Return list of missing required documents"""
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
        """Days since business registration"""
        delta = timezone.now().date() - self.created_at.date()
        return delta.days
    
    @property
    def permit_is_valid(self):
        """Check if business permit is valid (not expired)"""
        if self.permit_expiry_date:
            return self.permit_expiry_date >= timezone.now().date()
        return False
    
    @property
    def uploaded_documents_count(self):
        """Count of uploaded required documents"""
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