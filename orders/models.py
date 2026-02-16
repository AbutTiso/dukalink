from django.db import models
from products.models import Product
from django.contrib.auth.models import User

from django.db import models
from django.conf import settings
from django.contrib.auth.models import User

class Order(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    
    PAYMENT_METHOD_CHOICES = [
        ('mpesa_till', 'M-Pesa Till Number'),
        ('mpesa_paybill', 'M-Pesa Paybill'),
        ('pochi_biashara', 'Pochi La Biashara'),
        ('cash_on_delivery', 'Cash on Delivery'),
    ]
    
    # Vendor field (foreign key to User)
    vendor = models.ForeignKey(User, on_delete=models.CASCADE, related_name='vendor_orders', null=True)
    
    # Customer info
    customer_name = models.CharField(max_length=255)
    customer_phone = models.CharField(max_length=15)
    customer = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='customer_orders')
    
    total = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Payment fields
    paid = models.BooleanField(default=False)
    payment_method = models.CharField(max_length=50, choices=PAYMENT_METHOD_CHOICES, blank=True)
    payment_reference = models.CharField(max_length=100, blank=True)
    checkout_request_id = models.CharField(max_length=100, blank=True)  # Link to M-Pesa transaction
    
    # New fields for Pochi payments and manual payment confirmation
    transaction_code = models.CharField(max_length=50, blank=True, null=True)
    payment_screenshot = models.ImageField(upload_to='payment_screenshots/', blank=True, null=True)
    payment_confirmed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='confirmed_payments'
    )
    payment_confirmed_at = models.DateTimeField(null=True, blank=True)
    
    # Session tracking for cart clearing
    session_key = models.CharField(max_length=40, blank=True, null=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Order #{self.id} - {self.customer_name}"
    
    @property
    def items(self):
        """Convenience property to get order items"""
        return self.order_items.all()
    
    @property
    def is_payment_confirmed(self):
        """Check if payment has been confirmed"""
        return self.payment_confirmed_at is not None and self.payment_confirmed_by is not None
    
    def confirm_payment(self, user):
        """Mark payment as confirmed by a user"""
        from django.utils import timezone
        self.paid = True
        self.payment_confirmed_by = user
        self.payment_confirmed_at = timezone.now()
        self.save()

class OrderItem(models.Model):
    order = models.ForeignKey(Order, related_name="order_items", on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    vendor = models.ForeignKey(User, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    def total_price(self):
        return self.quantity * self.price

    def __str__(self):
        return f"{self.product.name} x {self.quantity}"
    
# Add to orders/models.py
class VendorPayment(models.Model):
    """Track payments to individual vendors for an order"""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    
    order = models.ForeignKey('Order', on_delete=models.CASCADE)
    vendor = models.ForeignKey(User, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    commission_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    net_amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    mpesa_receipt = models.CharField(max_length=50, blank=True)
    transaction_id = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return f"Payment to {self.vendor.username} for Order #{self.order.id}: KES {self.net_amount}"