"""
Debug webhook test - see exact error
"""
import requests
import json

BASE_URL = "http://localhost:8000"
API_BASE = f"{BASE_URL}/api/v1"

# First create a test payment
print("Step 1: Register and login")
requests.post(f"{API_BASE}/auth/register", json={
    "email": "webhook_test@example.com",
    "password": "test123",
    "name": "Webhook Test"
})

login_response = requests.post(f"{API_BASE}/auth/login", json={
    "email": "webhook_test@example.com",
    "password": "test123"
})
token = login_response.json()["access_token"]

print("Step 2: Get a plan")
plans = requests.get(f"{API_BASE}/plans").json()
plan_id = plans[0]["id"]

print("Step 3: Create checkout")
checkout_response = requests.post(
    f"{API_BASE}/checkout",
    json={"plan_id": plan_id, "return_url": "http://localhost:3000"},
    headers={"Authorization": f"Bearer {token}"}
)
payment_id = checkout_response.json()["payment_id"]
print(f"Payment ID: {payment_id}")

print("\nStep 4: Send webhook")
webhook_data = {
    "reference": payment_id,
    "paynowreference": f"PAYNOW-{payment_id[:8]}",
    "status": "paid"
}
print(f"Webhook data: {webhook_data}")

webhook_response = requests.post(
    f"{API_BASE}/webhooks/paynow",
    data=webhook_data
)

print(f"\nWebhook Status Code: {webhook_response.status_code}")
print(f"Webhook Response: {webhook_response.text}")

try:
    print(f"Webhook JSON: {json.dumps(webhook_response.json(), indent=2)}")
except:
    pass

# Check payment status after webhook
payment_status = requests.get(
    f"{API_BASE}/payment/{payment_id}",
    headers={"Authorization": f"Bearer {token}"}
)
print(f"\nPayment Status After Webhook:")
print(json.dumps(payment_status.json(), indent=2))
