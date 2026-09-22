// Manual UPI Flow Handler (Razorpay Popup completely disabled)
function initRazorpayPayment(config) {
  const payBtn = document.getElementById('payNowBtn');
  if (!payBtn) return;

  payBtn.addEventListener('click', function(e) {
    e.preventDefault();
    const planType = config.planType || 'starter';
    window.location.href = `/pay/${planType}/`;
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
