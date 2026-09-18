// Razorpay Checkout Integration & Verification Handler
function initRazorpayPayment(config) {
  const payBtn = document.getElementById('payNowBtn');
  if (!payBtn) return;

  payBtn.addEventListener('click', function(e) {
    e.preventDefault();
    payBtn.disabled = true;
    payBtn.innerHTML = '<span class="spinner"></span> Initializing Payment Gateway...';

    // If real Razorpay key is configured and Razorpay script is loaded
    if (typeof Razorpay !== 'undefined' && config.keyId && !config.keyId.startsWith('rzp_test_placeholder')) {
      const options = {
        key: config.keyId,
        amount: config.amountInPaise,
        currency: config.currency,
        name: 'Tradex Academy',
        description: `${config.planName || 'Plan'} (₹${config.price})`,
        image: 'https://images.unsplash.com/photo-1611974789855-9c2a0a7236a3?auto=format&fit=crop&w=128&q=80',
        order_id: config.orderId,
        handler: function(response) {
          payBtn.innerHTML = '<span class="spinner"></span> Verifying Payment Signature...';
          response.plan_type = config.planType || 'combo';
          verifyPaymentOnBackend(response);
        },
        prefill: {
          name: config.userName,
          email: config.userEmail,
          contact: config.userPhone
        },
        theme: {
          color: config.planType === 'gold_strategy' ? '#eab308' : '#10b981'
        },
        modal: {
          ondismiss: function() {
            payBtn.disabled = false;
            payBtn.innerHTML = `Pay ₹${config.price} & Activate Plan`;
          }
        }
      };

      try {
        const rzp = new Razorpay(options);
        rzp.on('payment.failed', function(response) {
          alert('Payment Failed: ' + response.error.description);
          window.location.href = '/subscriptions/failed/';
        });
        rzp.open();
      } catch (err) {
        console.warn('Direct Razorpay open failed, using simulation mode', err);
        triggerSimulatedPayment(config, payBtn);
      }
    } else {
      // Test Mode Simulation for local development
      triggerSimulatedPayment(config, payBtn);
    }
  });
}

function triggerSimulatedPayment(config, payBtn) {
  payBtn.innerHTML = 'Processing payment simulation...';
  
  // Simulate network round-trip of payment
  setTimeout(() => {
    const mockPaymentId = 'pay_sim_' + Math.random().toString(36).substring(2, 12);
    const payload = {
      razorpay_order_id: config.orderId,
      razorpay_payment_id: mockPaymentId,
      razorpay_signature: 'simulated_test_signature',
      plan_type: config.planType || 'combo'
    };
    verifyPaymentOnBackend(payload);
  }, 1200);
}


function verifyPaymentOnBackend(paymentData) {
  fetch('/subscriptions/verify-payment/', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': getCookie('csrftoken')
    },
    body: JSON.stringify(paymentData)
  })
  .then(res => res.json())
  .then(data => {
    if (data.status === 'success' && data.redirect_url) {
      window.location.href = data.redirect_url;
    } else {
      alert('Verification Error: ' + (data.message || 'Payment could not be verified.'));
      window.location.href = '/subscriptions/failed/';
    }
  })
  .catch(err => {
    console.error('Payment verification error:', err);
    window.location.href = '/subscriptions/failed/';
  });
}

function getCookie(name) {
  let cookieValue = null;
  if (document.cookie && document.cookie !== '') {
    const cookies = document.cookie.split(';');
    for (let i = 0; i < cookies.length; i++) {
      const cookie = cookies[i].trim();
      if (cookie.substring(0, name.length + 1) === (name + '=')) {
        cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
        break;
      }
    }
  }
  return cookieValue;
}
