import hmac
import hashlib
from django.conf import settings
import razorpay


def get_razorpay_client():
    """Initializes and returns Razorpay client instance."""
    key_id = getattr(settings, 'RAZORPAY_KEY_ID', '')
    key_secret = getattr(settings, 'RAZORPAY_KEY_SECRET', '')
    
    # Return mock or real client
    if key_id and key_secret and not key_id.startswith('rzp_test_placeholder'):
        try:
            return razorpay.Client(auth=(key_id, key_secret))
        except Exception:
            return None
    return None


def create_razorpay_order(amount_in_rupees, currency='INR', receipt=None, notes=None):
    """
    Creates an order on Razorpay.
    Amount in Razorpay must be in paise (₹1 = 100 paise).
    """
    client = get_razorpay_client()
    amount_in_paise = int(amount_in_rupees * 100)
    
    order_data = {
        'amount': amount_in_paise,
        'currency': currency,
        'receipt': receipt or f"order_rcpt_{int(amount_in_rupees)}",
        'payment_capture': 1, # Auto capture
        'notes': notes or {}
    }

    if client:
        try:
            order = client.order.create(data=order_data)
            return {
                'id': order['id'],
                'amount': order['amount'],
                'currency': order['currency'],
                'is_mock': False
            }
        except Exception as e:
            # Fallback to simulated order if network or key issue
            pass
            
    # Dev / Simulation mode fallback
    import uuid
    simulated_order_id = f"order_sim_{uuid.uuid4().hex[:12]}"
    return {
        'id': simulated_order_id,
        'amount': amount_in_paise,
        'currency': currency,
        'is_mock': True
    }


def verify_razorpay_signature(order_id, payment_id, signature):
    """
    Verifies Razorpay payment signature using SHA256 HMAC.
    Returns True if valid or if in simulation dev mode.
    """
    if order_id.startswith('order_sim_') or payment_id.startswith('pay_sim_'):
        return True # Simulated test transaction

    client = get_razorpay_client()
    key_secret = getattr(settings, 'RAZORPAY_KEY_SECRET', '')

    if client:
        try:
            params = {
                'razorpay_order_id': order_id,
                'razorpay_payment_id': payment_id,
                'razorpay_signature': signature
            }
            client.utility.verify_payment_signature(params)
            return True
        except razorpay.errors.SignatureVerificationError:
            return False
        except Exception:
            pass

    # Manual HMAC verification fallback
    if key_secret:
        msg = f"{order_id}|{payment_id}".encode('utf-8')
        generated_sig = hmac.new(key_secret.encode('utf-8'), msg, hashlib.sha256).hexdigest()
        return hmac.compare_digest(generated_sig, signature)

    return False
