"""
API Testing Script - Test all endpoints
Run this after starting the server with: uvicorn app.main:app --reload
"""
import requests
import json

BASE_URL = "http://localhost:8000"
API_BASE = f"{BASE_URL}/api/v1"

# Store token for authenticated requests
token = None
user_id = None
payment_id = None
plan_id = None


def print_response(name, response):
    """Pretty print response."""
    print(f"\n{'='*60}")
    print(f"TEST: {name}")
    print(f"{'='*60}")
    print(f"Status: {response.status_code}")
    try:
        print(f"Response: {json.dumps(response.json(), indent=2)}")
    except:
        print(f"Response: {response.text}")
    print()


def test_health():
    """Test health endpoint."""
    response = requests.get(f"{BASE_URL}/health")
    print_response("Health Check", response)
    return response.status_code == 200


def test_root():
    """Test root endpoint."""
    response = requests.get(BASE_URL)
    print_response("Root Endpoint", response)
    return response.status_code == 200


def test_register():
    """Test user registration."""
    global user_id
    data = {
        "email": "testuser@example.com",
        "password": "testpass123",
        "name": "Test User"
    }
    response = requests.post(f"{API_BASE}/auth/register", json=data)
    print_response("Register User", response)
    if response.status_code == 201:
        user_id = response.json().get("user_id")
        return True
    return False


def test_login():
    """Test user login."""
    global token
    data = {
        "email": "testuser@example.com",
        "password": "testpass123"
    }
    response = requests.post(f"{API_BASE}/auth/login", json=data)
    print_response("Login User", response)
    if response.status_code == 200:
        token = response.json().get("access_token")
        return True
    return False


def test_get_me():
    """Test get current user."""
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(f"{API_BASE}/auth/me", headers=headers)
    print_response("Get Current User", response)
    return response.status_code == 200


def test_get_plans():
    """Test get plans."""
    global plan_id
    response = requests.get(f"{API_BASE}/plans")
    print_response("Get Plans", response)
    if response.status_code == 200:
        plans = response.json()
        if plans:
            plan_id = plans[0]["id"]
        return True
    return False


def test_checkout():
    """Test checkout."""
    global payment_id
    headers = {"Authorization": f"Bearer {token}"}
    data = {
        "plan_id": plan_id,
        "return_url": "http://localhost:3000/dashboard"
    }
    response = requests.post(f"{API_BASE}/checkout", json=data, headers=headers)
    print_response("Checkout", response)
    if response.status_code == 200:
        payment_id = response.json().get("payment_id")
        return True
    return False


def test_get_payment_status():
    """Test get payment status."""
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(f"{API_BASE}/payment/{payment_id}", headers=headers)
    print_response("Get Payment Status", response)
    return response.status_code == 200


def test_dashboard():
    """Test dashboard."""
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(f"{API_BASE}/dashboard", headers=headers)
    print_response("Get Dashboard", response)
    return response.status_code == 200


def test_webhook():
    """Test PayNow webhook."""
    data = {
        "reference": payment_id,
        "paynowreference": "PAYNOW-TEST-12345",
        "status": "paid"
    }
    response = requests.post(f"{API_BASE}/webhooks/paynow", data=data)
    print_response("PayNow Webhook", response)
    return response.status_code == 200


def test_dashboard_after_payment():
    """Test dashboard after payment."""
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(f"{API_BASE}/dashboard", headers=headers)
    print_response("Dashboard After Payment", response)
    return response.status_code == 200


def test_unauthorized_access():
    """Test unauthorized access."""
    response = requests.get(f"{API_BASE}/dashboard")
    print_response("Unauthorized Access (should fail)", response)
    return response.status_code == 401


def test_invalid_login():
    """Test invalid login."""
    data = {
        "email": "wrong@example.com",
        "password": "wrongpass"
    }
    response = requests.post(f"{API_BASE}/auth/login", json=data)
    print_response("Invalid Login (should fail)", response)
    return response.status_code == 401


def test_duplicate_registration():
    """Test duplicate registration."""
    data = {
        "email": "testuser@example.com",
        "password": "testpass123",
        "name": "Test User"
    }
    response = requests.post(f"{API_BASE}/auth/register", json=data)
    print_response("Duplicate Registration (should fail)", response)
    return response.status_code == 400


def run_all_tests():
    """Run all tests in sequence."""
    print("\n" + "="*60)
    print("STARTING API ENDPOINT TESTS")
    print("="*60)
    
    tests = [
        ("Health Check", test_health),
        ("Root Endpoint", test_root),
        ("Register User", test_register),
        ("Login User", test_login),
        ("Get Current User", test_get_me),
        ("Get Plans", test_get_plans),
        ("Checkout", test_checkout),
        ("Get Payment Status", test_get_payment_status),
        ("Get Dashboard", test_dashboard),
        ("PayNow Webhook", test_webhook),
        ("Dashboard After Payment", test_dashboard_after_payment),
        ("Unauthorized Access", test_unauthorized_access),
        ("Invalid Login", test_invalid_login),
        ("Duplicate Registration", test_duplicate_registration),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
            if result:
                print(f"✅ {name} - PASSED")
            else:
                print(f"❌ {name} - FAILED")
        except Exception as e:
            print(f"❌ {name} - ERROR: {str(e)}")
            results.append((name, False))
    
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    passed = sum(1 for _, result in results if result)
    total = len(results)
    print(f"Passed: {passed}/{total}")
    print(f"Success Rate: {(passed/total)*100:.1f}%")
    print()
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {name}")


if __name__ == "__main__":
    print("Make sure the server is running at http://localhost:8000")
    input("Press Enter to start testing...")
    run_all_tests()
