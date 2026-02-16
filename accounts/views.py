from django.shortcuts import render, redirect
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from orders.models import Order
from .models import Business
from .forms import BusinessRegisterForm, UserRegistrationForm, UserProfileForm, BusinessDocumentForm

def register_business(request):
    if request.method == "POST":
        form = BusinessRegisterForm(request.POST)

        if form.is_valid():
            business_name = form.cleaned_data["business_name"]
            phone = form.cleaned_data["phone"]
            location = form.cleaned_data["location"]

            username = form.cleaned_data["username"]
            email = form.cleaned_data["email"]
            password = form.cleaned_data["password1"]

            # Create user
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password
            )

            # Create business with pending verification
            business = Business.objects.create(
                owner=user,
                name=business_name,
                phone=phone,
                location=location,
                verification_status='pending',  # Start as pending verification
                is_approved=False,             # Not approved until documents verified
                is_rejected=False
            )

            # Auto login after signup
            user = authenticate(username=username, password=password)
            if user:
                login(request, user)

            messages.success(
                request, 
                '🎉 Business registered successfully! Please upload your business documents to complete verification and start selling.'
            )
            
            # Redirect to document upload page instead of dashboard
            return redirect('accounts:upload_documents', business_id=business.id)

        else:
            # Form is invalid - show errors
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")

    else:
        form = BusinessRegisterForm()

    return render(request, "accounts/register_business.html", {"form": form})

def login_view(request):
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")

        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            return redirect("dashboard:dashboard_home")
        else:
            messages.error(request, "Invalid username or password")

    return render(request, "accounts/login.html")

def logout_view(request):
    logout(request)
    return redirect("/")

@login_required
def profile(request):
    """User profile view with business ownership check"""
    
    # Check if user owns a business
    try:
        business = Business.objects.get(owner=request.user)
        is_vendor = True
    except Business.DoesNotExist:
        business = None
        is_vendor = False
    
    if request.method == 'POST':
        form = UserProfileForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profile updated successfully!')
            
            # Redirect based on user type - FIXED: Added namespace
            if is_vendor:
                return redirect('dashboard:vendor_dashboard')
            return redirect('accounts:profile')  # ← CHANGED: 'profile' → 'accounts:profile'
    else:
        form = UserProfileForm(instance=request.user)
    
    # Get recent orders if user is a customer
    recent_orders = None
    if not is_vendor:
        recent_orders = Order.objects.filter(
            customer=request.user
        ).order_by('-created_at')[:5]
    
    context = {
        'form': form,
        'is_vendor': is_vendor,
        'business': business,
        'recent_orders': recent_orders,
    }
    
    return render(request, 'accounts/profile.html', context)

# Optional: Add a registration view for regular users (not businesses)
def register(request):
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, 'Registration successful!')
            return redirect('home')
    else:
        form = UserRegistrationForm()
    return render(request, 'accounts/register_user.html', {'form': form})

# Optional: Add my_orders view
@login_required
def my_orders(request):
    """View for customers to see their order history"""
    orders = Order.objects.filter(
        customer=request.user  # Changed from 'user' to 'customer'
    ).select_related('vendor').prefetch_related(
        'order_items__product'
    ).order_by('-created_at')
    
    # Calculate total for each order
    for order in orders:
        order_total = 0
        for item in order.order_items.all():
            order_total += item.quantity * item.price
        order.total_amount = order_total
    
    # Pagination
    from django.core.paginator import Paginator
    paginator = Paginator(orders, 10)
    page_number = request.GET.get('page')
    page_orders = paginator.get_page(page_number)
    
    context = {
        'orders': page_orders,
    }
    
    return render(request, 'accounts/my_orders.html', context)
# In views.py
def register_choice(request):
    """Page to choose between customer and business registration"""
    # GET request - show the choice page
    return render(request, 'accounts/register_choice.html')
from django.shortcuts import render, redirect, get_object_or_404
@login_required
def upload_documents(request, business_id):
    """Vendor document upload page"""
    business = get_object_or_404(Business, id=business_id, owner=request.user)
    
    if request.method == "POST":
        form = BusinessDocumentForm(request.POST, request.FILES, instance=business)
        if form.is_valid():
            business.verification_status = 'under_review'
            form.save()
            messages.success(request, 'Documents uploaded successfully! Your application is now under review.')
            return redirect('accounts:document_status')
    else:
        form = BusinessDocumentForm(instance=business)
    
    return render(request, 'accounts/upload_documents.html', {
        'form': form,
        'business': business
    })


@login_required
def document_status(request):
    """View for vendors to check document verification status"""
    try:
        business = Business.objects.get(owner=request.user)
    except Business.DoesNotExist:
        messages.error(request, 'No business found')
        return redirect('accounts:register_business')
    
    return render(request, 'accounts/document_status.html', {
        'business': business
    })