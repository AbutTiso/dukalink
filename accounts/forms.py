from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from django.utils import timezone
from .models import Business

class UserRegistrationForm(UserCreationForm):
    email = forms.EmailField(required=True)
    
    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2']

class UserProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['username', 'email', 'first_name', 'last_name']

class BusinessRegisterForm(forms.Form):
    business_name = forms.CharField(max_length=255)
    phone = forms.CharField(max_length=15)
    location = forms.CharField(max_length=255)
    username = forms.CharField(max_length=150)
    email = forms.EmailField()
    password1 = forms.CharField(widget=forms.PasswordInput, label="Password")
    password2 = forms.CharField(widget=forms.PasswordInput, label="Confirm Password")

    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get("password1")
        password2 = cleaned_data.get("password2")
        
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError("Passwords do not match")
        
        return cleaned_data
    
    def clean_username(self):
        username = self.cleaned_data.get('username')
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError("Username already exists")
        return username
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("Email already registered")
        return email
    
    def clean_phone(self):
        phone = self.cleaned_data.get('phone')
        # Remove any non-digit characters
        phone_clean = ''.join(filter(str.isdigit, phone))
        if len(phone_clean) < 10:
            raise forms.ValidationError("Phone number must be at least 10 digits")
        # Add Kenyan phone validation
        if not phone_clean.startswith('254') and not phone_clean.startswith('0'):
            raise forms.ValidationError("Phone number must start with 0 or 254")
        return phone


class BusinessDocumentForm(forms.ModelForm):
    """Form for vendors to upload business documents"""
    class Meta:
        model = Business
        fields = [
            'business_type',
            'business_description',
            'business_registration_number',
            'business_registration_cert',
            'kra_pin',
            'kra_certificate',
            'tax_compliance_cert',
            'owner_id_number',
            'owner_id_front',
            'owner_id_back',
            'business_permit',
            'permit_expiry_date',
            'additional_docs',
        ]
        widgets = {
            'business_description': forms.Textarea(attrs={
                'rows': 4,
                'class': 'form-control',
                'placeholder': 'Describe your business, products, and services...'
            }),
            'permit_expiry_date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control'
            }),
            'business_registration_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., BRS-2025-123456'
            }),
            'kra_pin': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., P012345678B'
            }),
            'owner_id_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'National ID Number'
            }),
        }
        labels = {
            'business_type': 'Business Category',
            'business_description': 'Business Description',
            'business_registration_number': 'Business Registration Number',
            'business_registration_cert': 'Business Registration Certificate',
            'kra_pin': 'KRA PIN',
            'kra_certificate': 'KRA PIN Certificate',
            'tax_compliance_cert': 'Tax Compliance Certificate (Optional)',
            'owner_id_number': 'National ID/Passport Number',
            'owner_id_front': 'National ID - Front',
            'owner_id_back': 'National ID - Back',
            'business_permit': 'Single Business Permit',
            'permit_expiry_date': 'Permit Expiry Date',
            'additional_docs': 'Additional Documents (Optional)',
        }
        help_texts = {
            'business_registration_number': 'Enter your Business Registration Service (BRS) number',
            'kra_pin': 'Enter your KRA PIN (e.g., P012345678B)',
            'business_permit': 'Upload your Single Business Permit from County Government',
            'owner_id_number': 'Enter your National ID or Passport number',
            'tax_compliance_cert': 'Optional but recommended',
        }

    def clean_kra_pin(self):
        kra_pin = self.cleaned_data.get('kra_pin')
        if kra_pin:
            # Convert to uppercase
            kra_pin = kra_pin.upper()
            # Remove whitespace
            kra_pin = kra_pin.strip()
            # Check format: P followed by 9 digits then A-Z
            if not kra_pin.startswith('P'):
                raise forms.ValidationError('KRA PIN must start with "P"')
            if len(kra_pin) != 11:
                raise forms.ValidationError('KRA PIN must be 11 characters (e.g., P012345678B)')
        return kra_pin

    def clean_owner_id_number(self):
        id_number = self.cleaned_data.get('owner_id_number')
        if id_number:
            # Remove any non-digit characters
            id_number = ''.join(filter(str.isdigit, id_number))
            if len(id_number) < 7 or len(id_number) > 8:
                raise forms.ValidationError('National ID must be 7 or 8 digits')
        return id_number

    def clean_permit_expiry_date(self):
        expiry = self.cleaned_data.get('permit_expiry_date')
        if expiry and expiry < timezone.now().date():
            raise forms.ValidationError('Business permit has expired. Please renew and upload current permit.')
        return expiry

    def clean_business_registration_cert(self):
        cert = self.cleaned_data.get('business_registration_cert')
        if cert:
            # Validate file size (max 5MB)
            if cert.size > 5 * 1024 * 1024:
                raise forms.ValidationError('File size must be less than 5MB')
        return cert

    def clean(self):
        cleaned_data = super().clean()
        # Auto-update documents_uploaded_at when files are uploaded
        if any([
            cleaned_data.get('business_registration_cert'),
            cleaned_data.get('kra_certificate'),
            cleaned_data.get('owner_id_front'),
            cleaned_data.get('owner_id_back'),
            cleaned_data.get('business_permit'),
        ]):
            cleaned_data['documents_uploaded_at'] = timezone.now()
        return cleaned_data


class BusinessVerificationForm(forms.Form):
    """Form for admin to verify vendor documents"""
    verification_status = forms.ChoiceField(
        choices=[
            ('verified', '✅ APPROVE - Documents Verified'),
            ('rejected', '❌ REJECT - Invalid/Incomplete Documents'),
            ('info_needed', 'ℹ️ REQUEST INFO - More Information Needed'),
        ],
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'})
    )
    
    verification_notes = forms.CharField(
        widget=forms.Textarea(attrs={
            'rows': 4,
            'class': 'form-control',
            'placeholder': 'Provide feedback to the vendor...'
        }),
        required=False,
        help_text='Required for rejection or when requesting more information'
    )
    
    notify_vendor = forms.BooleanField(
        required=False,
        initial=True,
        help_text='Send email notification to vendor about this decision'
    )
    
    def clean(self):
        cleaned_data = super().clean()
        status = cleaned_data.get('verification_status')
        notes = cleaned_data.get('verification_notes')
        
        # Require notes for rejection or info request
        if status in ['rejected', 'info_needed'] and not notes:
            raise forms.ValidationError(
                'Please provide verification notes when rejecting or requesting more information.'
            )
        return cleaned_data


class BusinessSearchForm(forms.Form):
    """Form for admin to search vendors"""
    query = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search by business name, owner, email, or KRA PIN...'
        })
    )
    status = forms.ChoiceField(
        required=False,
        choices=[
            ('', 'All Status'),
            ('pending', 'Pending'),
            ('under_review', 'Under Review'),
            ('verified', 'Verified'),
            ('rejected', 'Rejected'),
            ('info_needed', 'More Info Needed'),
        ],
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    documents_status = forms.ChoiceField(
        required=False,
        choices=[
            ('', 'All Documents'),
            ('complete', 'Complete'),
            ('incomplete', 'Incomplete'),
        ],
        widget=forms.Select(attrs={'class': 'form-select'})
    )