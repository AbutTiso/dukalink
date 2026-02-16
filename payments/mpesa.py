import requests
import base64
import json
from datetime import datetime
from django.conf import settings
from requests.auth import HTTPBasicAuth
import logging

logger = logging.getLogger(__name__)

class MpesaClient:
    """M-Pesa API Client"""
    
    def __init__(self):
        self.consumer_key = settings.MPESA_CONSUMER_KEY
        self.consumer_secret = settings.MPESA_CONSUMER_SECRET
        self.passkey = settings.MPESA_PASSKEY
        self.shortcode = settings.MPESA_BUSINESS_SHORTCODE
        self.lnm_shortcode = settings.MPESA_LNM_SHORTCODE
        self.base_url = settings.MPESA_BASE_URL
        self.transaction_type = settings.MPESA_TRANSACTION_TYPE
        
        # Validate credentials exist
        if not all([self.consumer_key, self.consumer_secret, self.passkey]):
            logger.error("M-Pesa credentials not configured in .env file")
    
    def get_access_token(self):
        """Get M-Pesa access token"""
        if not self.consumer_key or not self.consumer_secret:
            logger.error("M-Pesa consumer key or secret not configured")
            return None
        
        api_url = f"{self.base_url}/oauth/v1/generate?grant_type=client_credentials"
        
        try:
            response = requests.get(
                api_url,
                auth=HTTPBasicAuth(self.consumer_key, self.consumer_secret),
                timeout=30
            )
            
            if response.status_code == 200:
                token = response.json().get('access_token')
                logger.info("Successfully obtained M-Pesa access token")
                return token
            else:
                logger.error(f"Failed to get access token: {response.status_code} - {response.text}")
                return None
                
        except requests.exceptions.ConnectionError:
            logger.error("Connection error to M-Pesa API")
            return None
        except requests.exceptions.Timeout:
            logger.error("Timeout connecting to M-Pesa API")
            return None
        except Exception as e:
            logger.error(f"Error getting access token: {str(e)}")
            return None
    
    def generate_password(self):
        """Generate M-Pesa STK push password"""
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        data_to_encode = self.shortcode + self.passkey + timestamp
        encoded_string = base64.b64encode(data_to_encode.encode())
        return encoded_string.decode('utf-8'), timestamp
    
    def stk_push(self, phone_number, amount, account_reference=None, transaction_desc=None):
        """Initiate STK Push"""
        # Clean phone number - remove +254, 0, etc.
        phone_number = self.format_phone_number(phone_number)
        
        if not phone_number:
            return {"error": "Invalid phone number", "success": False}
        
        access_token = self.get_access_token()
        
        if not access_token:
            return {"error": "Failed to get access token", "success": False}
        
        password, timestamp = self.generate_password()
        
        api_url = f"{self.base_url}/mpesa/stkpush/v1/processrequest"
        
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        
        # Default values
        account_reference = account_reference or "OrderPayment"
        transaction_desc = transaction_desc or "Payment for goods"
        
        # Truncate to API limits
        account_reference = account_reference[:12]
        transaction_desc = transaction_desc[:13]
        
        payload = {
            "BusinessShortCode": self.shortcode,
            "Password": password,
            "Timestamp": timestamp,
            "TransactionType": self.transaction_type,
            "Amount": int(amount),
            "PartyA": int(phone_number),
            "PartyB": int(self.lnm_shortcode),
            "PhoneNumber": int(phone_number),
            "CallBackURL": settings.MPESA_CALLBACK_URL,
            "AccountReference": account_reference,
            "TransactionDesc": transaction_desc
        }
        
        try:
            logger.info(f"Initiating STK push for {phone_number} amount {amount}")
            response = requests.post(api_url, json=payload, headers=headers, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                result['success'] = True
                logger.info(f"STK push initiated successfully: {result.get('CheckoutRequestID')}")
                return result
            else:
                logger.error(f"STK push failed: {response.status_code} - {response.text[:200]}")
                return {
                    "error": "Failed to initiate payment",
                    "status_code": response.status_code,
                    "success": False
                }
                
        except requests.exceptions.ConnectionError:
            logger.error("Connection error to M-Pesa API")
            return {"error": "Connection error", "success": False}
        except requests.exceptions.Timeout:
            logger.error("Timeout connecting to M-Pesa API")
            return {"error": "Request timeout", "success": False}
        except Exception as e:
            logger.error(f"Error in STK push: {str(e)}")
            return {"error": str(e), "success": False}
    
    def query_status(self, checkout_request_id):
        """Query STK push status"""
        access_token = self.get_access_token()
        
        if not access_token:
            return {"error": "Failed to get access token", "success": False}
        
        password, timestamp = self.generate_password()
        
        api_url = f"{self.base_url}/mpesa/stkpushquery/v1/query"
        
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "BusinessShortCode": self.shortcode,
            "Password": password,
            "Timestamp": timestamp,
            "CheckoutRequestID": checkout_request_id
        }
        
        try:
            logger.info(f"Querying status for {checkout_request_id}")
            response = requests.post(api_url, json=payload, headers=headers, timeout=30)
            
            logger.info(f"Query response status: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                result['success'] = True
                logger.info(f"Query successful: {result}")
                return result
            else:
                logger.error(f"Query failed: {response.status_code} - {response.text[:200]}")
                
                # Handle specific error codes
                if response.status_code == 403:
                    return {
                        "error": "Authentication failed. Check your credentials.",
                        "status_code": response.status_code,
                        "success": False
                    }
                elif response.status_code == 429:
                    return {
                        "error": "Too many requests. Please wait a moment.",
                        "status_code": response.status_code,
                        "success": False
                    }
                else:
                    return {
                        "error": f"Failed to query status. Status code: {response.status_code}",
                        "status_code": response.status_code,
                        "success": False
                    }
                    
        except requests.exceptions.ConnectionError:
            logger.error("Connection error to M-Pesa API")
            return {"error": "Connection error", "success": False}
        except requests.exceptions.Timeout:
            logger.error("Timeout connecting to M-Pesa API")
            return {"error": "Request timeout", "success": False}
        except Exception as e:
            logger.error(f"Error querying status: {str(e)}")
            return {"error": str(e), "success": False}
    
    def verify_callback(self, callback_data):
        """
        Verify and process M-Pesa callback data
        Returns: Dictionary with payment details
        """
        try:
            body = callback_data.get('Body', {})
            stk_callback = body.get('stkCallback', {})
            
            checkout_request_id = stk_callback.get('CheckoutRequestID')
            result_code = stk_callback.get('ResultCode')
            result_desc = stk_callback.get('ResultDesc')
            
            # Check if payment was successful (ResultCode 0 means success)
            if result_code == 0:
                metadata = stk_callback.get('CallbackMetadata', {}).get('Item', [])
                
                receipt_number = ''
                amount = 0
                phone = ''
                transaction_date = ''
                
                for item in metadata:
                    name = item.get('Name')
                    value = item.get('Value')
                    
                    if name == 'MpesaReceiptNumber':
                        receipt_number = value
                    elif name == 'Amount':
                        amount = value
                    elif name == 'PhoneNumber':
                        phone = value
                    elif name == 'TransactionDate':
                        transaction_date = value
                
                return {
                    'success': True,
                    'checkout_request_id': checkout_request_id,
                    'result_desc': result_desc,
                    'mpesa_receipt': receipt_number,
                    'result_code': result_code,
                    'amount': amount,
                    'phone': phone,
                    'transaction_date': transaction_date
                }
            else:
                return {
                    'success': False,
                    'checkout_request_id': checkout_request_id,
                    'result_desc': result_desc,
                    'result_code': result_code
                }
        except Exception as e:
            logger.error(f"Error verifying callback: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    @staticmethod
    def format_phone_number(phone):
        """Format phone number to international format"""
        # Convert to string
        phone = str(phone).strip()
        
        # Remove any non-digit characters
        phone = ''.join(filter(str.isdigit, phone))
        
        # If it starts with 0, replace with 254
        if phone.startswith('0'):
            phone = '254' + phone[1:]
        # If it starts with 7, add 254
        elif phone.startswith('7'):
            phone = '254' + phone
        # If it starts with 254, keep as is
        elif phone.startswith('254'):
            pass
        # If it's less than 10 digits, assume it's a local number
        elif len(phone) == 9:
            phone = '254' + phone
        else:
            logger.warning(f"Unexpected phone number format: {phone}")
        
        # Ensure we have exactly 12 digits (254 + 9 digits)
        if len(phone) == 12:
            return phone
        else:
            logger.error(f"Invalid phone number format: {phone}")
            return None

# Create a singleton instance
mpesa_client = MpesaClient()

# Convenience functions
def stk_push(phone_number, amount, account_reference=None, transaction_desc=None):
    """Convenience function for STK push"""
    return mpesa_client.stk_push(phone_number, amount, account_reference, transaction_desc)

def query_status(checkout_request_id):
    """Convenience function for querying status"""
    return mpesa_client.query_status(checkout_request_id)

def format_phone_number(phone):
    """Convenience function for formatting phone numbers"""
    return MpesaClient.format_phone_number(phone)