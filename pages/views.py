from django.shortcuts import render, redirect
from django.views.generic import TemplateView
from django.contrib import messages
from django.core.mail import send_mail, BadHeaderError
from django.conf import settings
import logging

from .models import ContactMessage

logger = logging.getLogger(__name__)

def faqs(request):
    """FAQs page"""
    faq_categories = [
        {
            'title': 'For Customers',
            'icon': 'fa-shopping-cart',
            'faqs': [
                {
                    'question': 'How do I place an order?',
                    'answer': 'Browse products from various vendors, add items to cart, and checkout. You can pay via M-Pesa or other available payment methods.'
                },
                {
                    'question': 'How can I track my order?',
                    'answer': 'Log in to your account and visit "My Orders" section. You can see real-time status updates of all your orders.'
                },
                {
                    'question': 'What payment methods are accepted?',
                    'answer': 'We accept M-Pesa, credit/debit cards, and bank transfers. M-Pesa is our recommended payment method for fastest processing.'
                },
                {
                    'question': 'Can I cancel my order?',
                    'answer': 'Yes, you can cancel pending orders from your orders page. Once an order is processing, please contact the vendor directly.'
                },
                {
                    'question': 'How do I contact a vendor?',
                    'answer': 'Each vendor has a WhatsApp contact button on their shop page. You can message them directly for inquiries.'
                },
            ]
        },
        {
            'title': 'For Vendors',
            'icon': 'fa-store',
            'faqs': [
                {
                    'question': 'How do I register my business?',
                    'answer': 'Click on "Sell on DukaLink" and complete the business registration form. You will need to provide KRA PIN, business registration certificate, and ID documents.'
                },
                {
                    'question': 'How long does verification take?',
                    'answer': 'Document verification typically takes 1-2 business days. You will receive an email notification once verified.'
                },
                {
                    'question': 'How do I receive payments?',
                    'answer': 'Set up your M-Pesa Paybill or Till number in your dashboard. Payments are processed instantly and settled within 24 hours.'
                },
                {
                    'question': 'What documents do I need?',
                    'answer': 'You need: Business Registration Certificate, KRA PIN Certificate, National ID/Passport, and Single Business Permit from your county.'
                },
                {
                    'question': 'How do I manage my products?',
                    'answer': 'Use your vendor dashboard to add, edit, or remove products. You can also track inventory and sales analytics.'
                },
            ]
        },
        {
            'title': 'Payments & Shipping',
            'icon': 'fa-truck',
            'faqs': [
                {
                    'question': 'How does M-Pesa payment work?',
                    'answer': 'When you checkout, you will receive an STK push on your phone. Enter your PIN to complete payment instantly.'
                },
                {
                    'question': 'What are the delivery options?',
                    'answer': 'Delivery options vary by vendor. Most vendors offer same-day delivery within Nairobi and 1-3 days for upcountry.'
                },
                {
                    'question': 'Is my payment secure?',
                    'answer': 'Yes, all payments are processed securely through M-Pesa\'s official API. We do not store your payment credentials.'
                },
                {
                    'question': 'What is your refund policy?',
                    'answer': 'Refunds are handled by vendors. Contact the vendor directly within 7 days of receiving your order.'
                },
            ]
        },
        {
            'title': 'Account & Security',
            'icon': 'fa-shield-alt',
            'faqs': [
                {
                    'question': 'How do I reset my password?',
                    'answer': 'Click on "Forgot Password" on the login page. Enter your email address to receive password reset instructions.'
                },
                {
                    'question': 'How do I delete my account?',
                    'answer': 'Contact our support team at support@dukalink.com to request account deletion.'
                },
                {
                    'question': 'Is my personal information safe?',
                    'answer': 'We use industry-standard encryption to protect your data. We never share your information with third parties without consent.'
                },
            ]
        },
    ]
    
    return render(request, 'pages/faqs.html', {'faq_categories': faq_categories})


def privacy_policy(request):
    """Privacy Policy page"""
    return render(request, 'pages/privacy_policy.html')


def terms_of_service(request):
    """Terms of Service page"""
    return render(request, 'pages/terms_of_service.html')


def contact_us(request):
    """Contact Us page with email notification"""
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        email = request.POST.get('email', '').strip()
        subject = request.POST.get('subject', '').strip()
        message = request.POST.get('message', '').strip()
        
        # Validate required fields
        if not all([name, email, subject, message]):
            messages.error(request, 'Please fill in all fields.')
            return render(request, 'pages/contact_us.html')
        
        try:
            # Send email to site admin
            send_mail(
                f'Contact Form: {subject}',
                f'From: {name} <{email}>\n\nMessage:\n{message}',
                settings.DEFAULT_FROM_EMAIL,
                [settings.CONTACT_EMAIL],
                fail_silently=False,
            )
            
            # Optional: Save to database
            ContactMessage.objects.create(
                name=name,
                email=email,
                subject=subject,
                message=message
            )
            
            # Optional: Send auto-reply to customer
            send_mail(
                'Thank you for contacting DukaLink',
                f'Dear {name},\n\nThank you for reaching out to us. We have received your message and will respond within 24 hours.\n\nYour message: {message}\n\nBest regards,\nDukaLink Team',
                settings.DEFAULT_FROM_EMAIL,
                [email],
                fail_silently=False,
            )
            
            messages.success(request, 'Thank you for contacting us! We will respond within 24 hours.')
            
        except BadHeaderError:
            messages.error(request, 'Invalid header found in email.')
        except Exception as e:
            logger.error(f'Contact form email error: {e}')
            messages.error(request, 'Sorry, there was an error sending your message. Please try again later.')
        
        return redirect('pages:contact_us')
    
    return render(request, 'pages/contact_us.html')


def about_us(request):
    """About Us page"""
    return render(request, 'pages/about_us.html')