import logging
import json
import urllib.parse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.urls import reverse

from orders.cart import Cart
from orders.models import Order, OrderItem, VendorPayment
from products.models import Product
from accounts.models import Business
from .mpesa import stk_push, query_status, mpesa_client, format_phone_number
from .models import MpesaPayment

logger = logging.getLogger(__name__)

# -----------------------------
# WhatsApp notification helper
# -----------------------------
def send_whatsapp_order(vendor_phone, customer_name, items, total):
    """Generate WhatsApp deep link for order notification"""
    message = f"🛍️ *New Order Received!*\n\n"
    message += f"👤 *Customer:* {customer_name}\n"
    message += f"📦 *Items:*\n"
    
    for item in items:
        item_total = float(item['price']) * int(item['quantity'])
        message += f"  • {item['name']} x{item['quantity']} = KES {item_total:,.2f}\n"
    
    message += f"\n💰 *Total:* KES {total:,.2f}\n"
    message += f"\n✅ Please confirm this order."
    
    # Encode for URL
    message_encoded = urllib.parse.quote(message)
    whatsapp_link = f"https://wa.me/{vendor_phone}?text={message_encoded}"
    return whatsapp_link

# -----------------------------
# Helper: Group cart items by vendor
# -----------------------------
def group_cart_by_vendor(cart):
    """Group cart items by vendor and calculate per-vendor totals"""
    vendor_items = {}
    
    for product_id, item_data in cart.cart.items():
        try:
            product = Product.objects.get(id=product_id)
            vendor = product.business.owner if hasattr(product, 'business') and product.business else None
            
            if not vendor:
                logger.warning(f"Product {product_id} has no vendor, skipping")
                continue
            
            vendor_id = vendor.id
            if vendor_id not in vendor_items:
                vendor_items[vendor_id] = {
                    'vendor': vendor,
                    'items': [],
                    'total': 0,
                    'business': product.business
                }
            
            item_total = float(item_data.get('price', product.price)) * int(item_data.get('quantity', 1))
            vendor_items[vendor_id]['items'].append({
                'product': product,
                'quantity': item_data.get('quantity', 1),
                'price': float(item_data.get('price', product.price)),
                'item_total': item_total
            })
            vendor_items[vendor_id]['total'] += item_total
            
        except Product.DoesNotExist:
            logger.warning(f"Product {product_id} not found, skipping")
            continue
    
    return vendor_items

# -----------------------------
# Checkout view - Multi-vendor support
# -----------------------------
@login_required
def checkout(request):
    # Get cart from session
    cart = Cart(request)
    
    # Check if cart is empty
    if len(cart) == 0:
        messages.error(request, "Your cart is empty")
        return redirect("products:product_list")
    
    # Group items by vendor
    vendor_items = group_cart_by_vendor(cart)
    
    if not vendor_items:
        messages.error(request, "Your cart contains invalid items")
        return redirect("products:product_list")
    
    # Calculate total across all vendors
    total_amount = sum(data['total'] for data in vendor_items.values())
    
    # GET request - display checkout form
    if request.method == "GET":
        # Show checkout summary with vendor breakdown
        return render(request, "payments/checkout_form.html", {
            "cart": cart,
            "vendor_items": vendor_items,
            "total": total_amount,
            "vendor_count": len(vendor_items)
        })
    
    # POST request - process checkout
    if request.method == "POST":
        payment_method = request.POST.get('payment_method')
        phone = request.POST.get("phone", "").strip()
        customer_name = request.POST.get("name", request.user.get_full_name() or request.user.username).strip()
        
        # ===== VALIDATION =====
        if not payment_method:
            messages.error(request, "Please select a payment method")
            return redirect("payments:checkout")
        
        if not phone:
            messages.error(request, "Phone number is required")
            return redirect("payments:checkout")
        
        # Handle different payment methods
        if payment_method == 'pochi_biashara':
            return handle_pochi_payment(request, cart, vendor_items, customer_name, phone)
        
        elif payment_method in ['mpesa_till', 'mpesa_paybill']:
            return handle_mpesa_payment(request, cart, vendor_items, customer_name, phone, total_amount)
        
        elif payment_method == 'cash_on_delivery':
            return handle_cod_payment(request, cart, vendor_items, customer_name, phone, total_amount)
        
        else:
            messages.error(request, "Invalid payment method selected")
            return redirect("payments:checkout")

# -----------------------------
# Handle Pochi payment (direct to vendor)
# -----------------------------
def handle_pochi_payment(request, cart, vendor_items, customer_name, phone):
    """Handle Pochi La Biashara payment - show instructions per vendor"""
    
    created_orders = []
    
    try:
        with transaction.atomic():
            for vendor_id, vendor_data in vendor_items.items():
                # Create separate order for each vendor
                order = Order.objects.create(
                    customer_name=customer_name,
                    customer_phone=phone,
                    customer=request.user,
                    total=vendor_data['total'],
                    status='pending',
                    paid=False,
                    payment_method='pochi_biashara',
                    session_key=request.session.session_key
                )
                
                # Create order items
                for item in vendor_data['items']:
                    OrderItem.objects.create(
                        order=order,
                        product=item['product'],
                        vendor=vendor_data['vendor'],
                        quantity=item['quantity'],
                        price=item['price']
                    )
                
                created_orders.append(order)
                logger.info(f"Created Pochi order #{order.id} for vendor {vendor_data['vendor'].username}")
        
        # Clear cart
        cart.clear()
        
        # Store orders in session for tracking
        request.session['pochi_orders'] = [order.id for order in created_orders]
        
        # Show multi-vendor payment instructions
        return render(request, 'payments/pochi_multi_instructions.html', {
            'orders': created_orders,
            'vendor_data': vendor_items,
            'customer_name': customer_name,
            'customer_phone': phone
        })
        
    except Exception as e:
        logger.error(f"Failed to create Pochi orders: {str(e)}")
        messages.error(request, "Failed to process your order. Please try again.")
        return redirect("payments:checkout")

# -----------------------------
# Handle M-Pesa payment (sequential per vendor)
# -----------------------------
def handle_mpesa_payment(request, cart, vendor_items, customer_name, phone, total_amount):
    """Handle M-Pesa payment - process sequentially per vendor"""
    
    created_orders = []
    
    try:
        with transaction.atomic():
            for vendor_id, vendor_data in vendor_items.items():
                # Create separate order for each vendor
                order = Order.objects.create(
                    customer_name=customer_name,
                    customer_phone=phone,
                    customer=request.user,
                    total=vendor_data['total'],
                    status='pending',
                    paid=False,
                    payment_method='mpesa_pending',
                    session_key=request.session.session_key
                )
                
                # Create order items
                for item in vendor_data['items']:
                    OrderItem.objects.create(
                        order=order,
                        product=item['product'],
                        vendor=vendor_data['vendor'],
                        quantity=item['quantity'],
                        price=item['price']
                    )
                
                created_orders.append(order)
                logger.info(f"Created M-Pesa order #{order.id} for vendor {vendor_data['vendor'].username}")
        
        # Store orders in session for sequential processing
        request.session['mpesa_orders'] = [order.id for order in created_orders]
        request.session['current_payment_index'] = 0
        
        # Clear cart
        cart.clear()
        
        # Start first payment
        return redirect('payments:process_next_vendor_payment')
        
    except Exception as e:
        logger.error(f"Failed to create M-Pesa orders: {str(e)}")
        messages.error(request, "Failed to process your order. Please try again.")
        return redirect("payments:checkout")

# -----------------------------
# Process next vendor payment (sequential)
# -----------------------------
@login_required
def process_next_vendor_payment(request):
    """Process payment for one vendor at a time"""
    
    mpesa_orders = request.session.get('mpesa_orders', [])
    current_index = request.session.get('current_payment_index', 0)
    
    if not mpesa_orders or current_index >= len(mpesa_orders):
        # All payments done
        if 'mpesa_orders' in request.session:
            del request.session['mpesa_orders']
        if 'current_payment_index' in request.session:
            del request.session['current_payment_index']
        
        messages.success(request, "All payments completed successfully!")
        return redirect('products:product_list')
    
    order_id = mpesa_orders[current_index]
    order = get_object_or_404(Order, id=order_id, customer=request.user)
    vendor = order.items.first().vendor
    
    if request.method == "GET":
        # Show payment page for this vendor
        context = {
            'order': order,
            'vendor': vendor,
            'amount': order.total,
            'current': current_index + 1,
            'total': len(mpesa_orders),
            'business': order.items.first().product.business
        }
        return render(request, 'payments/vendor_payment.html', context)
    
    if request.method == "POST":
        phone = request.POST.get('phone', '').strip()
        if not phone:
            messages.error(request, "Phone number is required")
            return redirect('payments:process_next_vendor_payment')
        
        # Process STK push for this vendor
        return process_single_vendor_payment(request, order, phone, current_index, len(mpesa_orders))

# -----------------------------
# Process single vendor payment
# -----------------------------
def process_single_vendor_payment(request, order, phone, current_index, total_orders):
    """Process STK push for a single vendor order"""
    
    formatted_phone = format_phone_number(phone)
    if not formatted_phone:
        messages.error(request, "Invalid phone number format")
        return redirect('payments:process_next_vendor_payment')
    
    try:
        # Use vendor-specific account reference
        vendor = order.items.first().vendor if order.items.exists() else None
        account_ref = f"V{vendor.id if vendor else 0}O{order.id}"
        
        response = stk_push(
            formatted_phone, 
            int(order.total), 
            account_ref, 
            f"Payment to {vendor.username if vendor else 'Vendor'}"
        )
        
        logger.info(f"STK Push Response for Order #{order.id}: {response}")
        
        if response.get("success") and response.get("ResponseCode") == "0":
            checkout_request_id = response.get("CheckoutRequestID")
            
            # Create payment record
            payment = MpesaPayment.objects.create(
                user=request.user,
                order=order,
                checkout_request_id=checkout_request_id,
                merchant_request_id=response.get("MerchantRequestID", ""),
                phone_number=formatted_phone,
                amount=order.total,
                status='PENDING',
                customer_name=order.customer_name
            )
            
            # Link payment to order
            order.checkout_request_id = checkout_request_id
            order.payment_method = 'mpesa_till'
            order.save()
            
            # Update session for next payment
            request.session['current_payment_index'] = current_index + 1
            
            # Generate next URL if there are more payments
            next_url = None
            if current_index + 1 < total_orders:
                next_url = reverse('payments:process_next_vendor_payment')
            
            # Show waiting page - PASS BOTH order.id AND order_id for template compatibility
            return render(request, 'payments/payment_waiting.html', {
                'order': order,
                'order_id': order.id,  # Explicitly pass order_id
                'orderId': order.id,    # Also pass orderId for JavaScript
                'vendor': vendor,
                'checkout_request_id': checkout_request_id,
                'current': current_index + 1,
                'total': total_orders,
                'phone': formatted_phone,
                'total_amount': order.total,
                'next_url': next_url
            })
        else:
            # Payment failed - don't delete order, just show error
            error_message = response.get("error", response.get("errorMessage", "Failed to initiate payment"))
            messages.error(request, f"Payment failed: {error_message}")
            
            # Return to payment page to try again
            return redirect('payments:process_next_vendor_payment')
            
    except Exception as e:
        logger.exception(f"Error in vendor payment: {str(e)}")
        messages.error(request, f"Payment failed: {str(e)}")
        return redirect('payments:process_next_vendor_payment')
# -----------------------------
# Handle Cash on Delivery
# -----------------------------
def handle_cod_payment(request, cart, vendor_items, customer_name, phone, total_amount):
    """Handle Cash on Delivery - create all orders"""
    
    created_orders = []
    
    try:
        with transaction.atomic():
            for vendor_id, vendor_data in vendor_items.items():
                order = Order.objects.create(
                    customer_name=customer_name,
                    customer_phone=phone,
                    customer=request.user,
                    total=vendor_data['total'],
                    status='processing',
                    paid=False,
                    payment_method='cash_on_delivery',
                    session_key=request.session.session_key
                )
                
                for item in vendor_data['items']:
                    OrderItem.objects.create(
                        order=order,
                        product=item['product'],
                        vendor=vendor_data['vendor'],
                        quantity=item['quantity'],
                        price=item['price']
                    )
                
                created_orders.append(order)
        
        cart.clear()
        
        messages.success(request, f"Orders placed successfully! Pay on delivery.")
        return redirect('payments:order_success', order_id=created_orders[0].id)
        
    except Exception as e:
        logger.error(f"Failed to create COD orders: {str(e)}")
        messages.error(request, "Failed to process your order. Please try again.")
        return redirect("payments:checkout")

# -----------------------------
# Original functions preserved below
# -----------------------------

def process_mpesa_payment(request, order, cart, phone, customer_name, total):
    """Handle M-Pesa STK push payment (original - kept for backward compatibility)"""
    # Format phone number
    formatted_phone = format_phone_number(phone)
    if not formatted_phone:
        messages.error(request, "Invalid phone number format")
        return redirect("payments:checkout")
    
    try:
        # Use order ID as account reference
        account_ref = f"ORDER{order.id}"
        response = stk_push(formatted_phone, int(total), account_ref, "Payment for order")
        
        logger.info(f"STK Push Response: {response}")
        
        # Check if STK push was successful
        if response.get("success") and response.get("ResponseCode") == "0":
            checkout_request_id = response.get("CheckoutRequestID")
            
            # Create payment record
            payment = MpesaPayment.objects.create(
                user=request.user if request.user.is_authenticated else None,
                order=order,
                checkout_request_id=checkout_request_id,
                merchant_request_id=response.get("MerchantRequestID", ""),
                phone_number=formatted_phone,
                amount=total,
                status='PENDING',
                customer_name=customer_name
            )
            
            # Link payment to order
            order.checkout_request_id = checkout_request_id
            order.save()
            
            # Store in session for tracking
            request.session['checkout_request_id'] = checkout_request_id
            request.session['order_id'] = order.id
            
            # Generate WhatsApp links for vendors (optional)
            whatsapp_links = generate_vendor_whatsapp_links(cart, customer_name, total)
            
            # Render WAITING page
            return render(
                request,
                "payments/payment_waiting.html",
                {
                    "whatsapp_links": whatsapp_links,
                    "checkout_request_id": checkout_request_id,
                    "order_id": order.id,
                    "total": total,
                    "customer_name": customer_name,
                    "phone": formatted_phone,
                    "payment_method": "M-Pesa"
                }
            )
        else:
            # STK push failed - delete the order
            order.delete()
            error_message = response.get("error", response.get("errorMessage", "Failed to initiate payment"))
            messages.error(request, f"Payment failed: {error_message}")
            return redirect("payments:checkout")
            
    except Exception as e:
        # Delete order if payment fails
        order.delete()
        logger.exception(f"Error in checkout payment: {str(e)}")
        messages.error(request, f"Payment failed: {str(e)}")
        return redirect("payments:checkout")


def generate_vendor_whatsapp_links(cart, customer_name, total):
    """Generate WhatsApp links for vendors"""
    whatsapp_links = []
    vendor_phones = set()
    
    # Collect vendor phone numbers from session cart
    for product_id, item in cart.cart.items():
        try:
            product = Product.objects.get(id=product_id)
            if hasattr(product, 'business') and product.business and product.business.phone:
                vendor_phones.add(product.business.phone)
        except Product.DoesNotExist:
            continue
    
    return whatsapp_links


@login_required
def pochi_payment_instructions(request, order_id):
    """View for Pochi Biashara payment instructions (original)"""
    try:
        order = get_object_or_404(Order, id=order_id, customer=request.user)
        
        # Get vendor's business phone from first order item
        business_phone = None
        business_name = "Vendor"
        
        first_item = order.order_items.first()
        if first_item and hasattr(first_item.product, 'business') and first_item.product.business:
            business = first_item.product.business
            # Try to get phone from business, fallback to owner's profile
            if business.phone:
                business_phone = business.phone
            elif hasattr(business.owner, 'profile') and business.owner.profile.phone_number:
                business_phone = business.owner.profile.phone_number
        
        # Validate vendor phone exists
        if not business_phone:
            messages.error(request, "Vendor phone number not available. Please contact support.")
            return redirect('products:product_list')
        
        # Clear cart if needed
        if request.session.get('cart_cleared_for_order') == order_id:
            cart = Cart(request)
            cart.clear()
            del request.session['cart_cleared_for_order']
        
        context = {
            'order': order,
            'business_phone': business_phone,
            'business_name': business_name,
            'amount': order.total,
            'account_reference': f'ORDER{order.id}'
        }
        return render(request, 'payments/pochi_instructions.html', context)
    
    except Order.DoesNotExist:
        messages.error(request, "Order not found")
        return redirect('products:product_list')
    

# -----------------------------
# Payment status check
# -----------------------------
def payment_status(request, checkout_request_id=None):
    """
    Check payment status - works with both URL parameter and GET parameter
    """
    # Get checkout_request_id from URL parameter or GET parameter
    if checkout_request_id is None:
        checkout_request_id = request.GET.get('checkout_request_id')
    
    if not checkout_request_id:
        return JsonResponse({
            'success': False,
            'error': 'No checkout request ID provided'
        }, status=400)
    
    try:
        # Try to get from database first
        try:
            payment = MpesaPayment.objects.get(checkout_request_id=checkout_request_id)
            
            response_data = {
                'success': True,
                'status': payment.status,
                'mpesa_receipt': payment.mpesa_receipt_number,
                'amount': str(payment.amount),
            }
            
            if payment.order:
                response_data['order_id'] = payment.order.id
                response_data['customer_name'] = payment.order.customer_name
                response_data['vendor'] = payment.order.items.first().vendor.username if payment.order.items.exists() else None
            
            if payment.status == 'COMPLETED' and payment.order:
                response_data['order_paid'] = True
                response_data['redirect_url'] = f"/payments/success/{payment.order.id}/"
            
            return JsonResponse(response_data)
            
        except MpesaPayment.DoesNotExist:
            # Fall back to querying M-Pesa API
            status_result = query_status(checkout_request_id)
            
            if status_result.get('ResultCode') == '0':
                return JsonResponse({
                    'success': True,
                    'status': 'COMPLETED',
                    'receipt': status_result.get('ReceiptNumber'),
                    'message': 'Payment completed successfully'
                })
            elif status_result.get('ResultCode') == '1037':
                return JsonResponse({
                    'success': False,
                    'status': 'PENDING',
                    'message': 'Waiting for user to enter PIN'
                })
            else:
                return JsonResponse({
                    'success': False,
                    'status': 'FAILED',
                    'message': status_result.get('ResultDesc', 'Payment failed')
                })
            
    except Exception as e:
        logger.error(f"Error checking payment status: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'Failed to check payment status'
        }, status=500)


@login_required
def payment_success(request, order_id):
    """Payment success page"""
    order = get_object_or_404(Order, id=order_id)
    payment = MpesaPayment.objects.filter(order=order).first()
    
    # Check if there are more payments pending
    session_key = request.session.session_key
    pending_orders = Order.objects.filter(
        session_key=session_key,
        paid=False,
        payment_method__in=['mpesa_pending', 'pending']
    ).exclude(id=order_id)
    
    context = {
        'order': order,
        'payment': payment,
        'pending_orders': pending_orders,
        'has_more_payments': pending_orders.exists()
    }
    
    return render(request, 'payments/success.html', context)


# -----------------------------
# Vendor Pochi payment confirmation
# -----------------------------
@login_required
def vendor_pochi_payments(request):
    """Show pending Pochi payments for vendor to confirm"""
    try:
        business = Business.objects.get(owner=request.user)
    except Business.DoesNotExist:
        messages.error(request, "You don't have a registered business")
        return redirect('dashboard:dashboard_home')
    
    # Get orders that contain vendor's products and are using Pochi
    pending_payments = Order.objects.filter(
        items__product__business=business,
        payment_method='pochi_biashara',
        paid=False,
        transaction_code__isnull=False
    ).distinct()
    
    context = {
        'pending_payments': pending_payments,
        'business': business,
    }
    return render(request, 'dashboard/pochi_payments.html', context)


@login_required
def confirm_vendor_payment(request, order_id):
    """Vendor confirms they received the Pochi payment"""
    if request.method == 'POST':
        try:
            business = Business.objects.get(owner=request.user)
        except Business.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': "You don't have a registered business"
            })
        
        order = get_object_or_404(Order, id=order_id)
        
        # Verify this vendor has products in this order
        if not order.items.filter(product__business=business).exists():
            return JsonResponse({
                'success': False,
                'error': 'You do not have permission to confirm this payment'
            })
        
        # Handle both JSON and form data
        if request.content_type == 'application/json':
            data = json.loads(request.body)
            action = data.get('action')
        else:
            action = request.POST.get('action')
        
        if action == 'confirm':
            order.paid = True
            order.payment_confirmed_by = request.user
            order.payment_confirmed_at = timezone.now()
            order.status = 'processing'
            order.save()
            
            if request.content_type == 'application/json':
                return JsonResponse({
                    'success': True,
                    'message': f'Payment for Order #{order.id} confirmed!'
                })
            else:
                messages.success(request, f'Payment for Order #{order.id} confirmed!')
            
        elif action == 'reject':
            reason = request.POST.get('rejection_reason', '')
            order.payment_notes = f'Payment rejected: {reason}'
            order.save()
            
            if request.content_type == 'application/json':
                return JsonResponse({
                    'success': True,
                    'message': f'Payment for Order #{order.id} rejected'
                })
            else:
                messages.warning(request, f'Payment for Order #{order.id} rejected')
        
        return redirect('dashboard:vendor_pochi_payments')
    
    return redirect('dashboard:vendor_pochi_payments')


# -----------------------------
# M-Pesa callback views
# -----------------------------
@csrf_exempt
@require_POST
def mpesa_callback(request):
    """
    M-Pesa STK Push Callback URL
    This is where M-Pesa sends payment confirmation
    """
    try:
        # Get callback data
        callback_data = json.loads(request.body)
        logger.info(f"M-Pesa Callback Received: {json.dumps(callback_data, indent=2)}")
        
        # Extract callback data
        body = callback_data.get('Body', {})
        stk_callback = body.get('stkCallback', {})
        
        checkout_request_id = stk_callback.get('CheckoutRequestID')
        result_code = stk_callback.get('ResultCode')
        result_desc = stk_callback.get('ResultDesc')
        
        if not checkout_request_id:
            logger.error("No checkout_request_id in callback")
            return JsonResponse({"ResultCode": 1, "ResultDesc": "Invalid callback data"})
        
        # Find the payment record
        try:
            payment = MpesaPayment.objects.get(checkout_request_id=checkout_request_id)
        except MpesaPayment.DoesNotExist:
            logger.error(f"Payment not found for checkout ID: {checkout_request_id}")
            return JsonResponse({"ResultCode": 1, "ResultDesc": "Payment not found"})
        
        # Update payment with callback data
        payment.result_code = result_code
        payment.result_description = result_desc
        
        if result_code == 0:
            # Payment successful
            payment.status = 'COMPLETED'
            
            # Get metadata
            callback_metadata = stk_callback.get('CallbackMetadata', {}).get('Item', [])
            for item in callback_metadata:
                if item.get('Name') == 'MpesaReceiptNumber':
                    payment.mpesa_receipt_number = item.get('Value', '')
                elif item.get('Name') == 'TransactionDate':
                    payment.transaction_date = item.get('Value', '')
                elif item.get('Name') == 'PhoneNumber':
                    payment.phone_number = item.get('Value', '')
            
            # Update order if exists
            if payment.order:
                order = payment.order
                order.paid = True
                order.payment_reference = payment.mpesa_receipt_number
                order.status = 'processing'
                order.save()
                logger.info(f"Order #{order.id} marked as paid")
                
                # Clear cart using session
                if order.session_key:
                    from django.contrib.sessions.models import Session
                    try:
                        session = Session.objects.get(session_key=order.session_key)
                        session_data = session.get_decoded()
                        
                        if 'cart' in session_data:
                            del session_data['cart']
                            session.session_data = Session.objects.encode(session_data)
                            session.save()
                            logger.info(f"✅ Cart cleared for order #{order.id}")
                    except Session.DoesNotExist:
                        logger.warning(f"Session {order.session_key} not found")
            
            logger.info(f"Payment completed: {checkout_request_id}")
        else:
            # Payment failed
            payment.status = 'FAILED'
            logger.info(f"Payment failed: {checkout_request_id} - {result_desc}")
        
        payment.save()
        
        return JsonResponse({"ResultCode": 0, "ResultDesc": "Success"})
        
    except json.JSONDecodeError:
        logger.error("Invalid JSON in callback")
        return JsonResponse({"ResultCode": 1, "ResultDesc": "Invalid JSON"})
    except Exception as e:
        logger.exception(f"Error processing callback: {str(e)}")
        return JsonResponse({"ResultCode": 1, "ResultDesc": "Internal server error"})


@csrf_exempt
@require_POST
def mpesa_timeout(request):
    """M-Pesa timeout callback"""
    try:
        callback_data = json.loads(request.body)
        logger.info(f"M-Pesa Timeout: {callback_data}")
        
        checkout_request_id = callback_data.get('CheckoutRequestID')
        if checkout_request_id:
            try:
                payment = MpesaPayment.objects.get(checkout_request_id=checkout_request_id)
                payment.status = 'FAILED'
                payment.result_description = 'Transaction timed out'
                payment.save()
                logger.info(f"Payment timed out: {checkout_request_id}")
            except MpesaPayment.DoesNotExist:
                logger.warning(f"Payment not found for timeout: {checkout_request_id}")
        
        return JsonResponse({"ResultCode": 0, "ResultDesc": "Success"})
    except Exception as e:
        logger.exception(f"Error in timeout callback: {str(e)}")
        return JsonResponse({"ResultCode": 1, "ResultDesc": "Error"})

@login_required
def confirm_pochi_payment(request, order_id):
    """Customer confirms they've paid a vendor via Pochi"""
    if request.method == 'POST':
        try:
            order = get_object_or_404(Order, id=order_id, customer=request.user)
            
            # Mark this vendor's order as paid
            order.paid = True
            order.transaction_code = request.POST.get('transaction_code', 'MANUAL')
            order.save()
            
            return JsonResponse({
                'success': True,
                'message': f'Payment for Order #{order.id} confirmed'
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            })
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'})