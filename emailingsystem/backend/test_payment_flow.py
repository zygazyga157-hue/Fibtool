"""
Test Payment and Delivery Flow
================================
This script tests the complete payment → delivery → email flow.

Usage:
    python test_payment_flow.py
"""
import asyncio
import httpx
from datetime import datetime

BASE_URL = "http://localhost:8000/api/v1"

# Test user credentials (use existing admin or create new user)
TEST_EMAIL = "test@example.com"
TEST_PASSWORD = "testpass123"


async def main():
    """Run complete payment flow test."""
    print("=" * 60)
    print("Testing Complete Payment & Delivery Flow")
    print("=" * 60)
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Step 1: Login
        print("\n[1] Logging in...")
        login_response = await client.post(
            f"{BASE_URL}/auth/login",
            data={"username": TEST_EMAIL, "password": TEST_PASSWORD}
        )
        
        if login_response.status_code != 200:
            print(f"   ❌ Login failed: {login_response.text}")
            print("   💡 Tip: Use admin@fibtool.com / admin123 or create a new user")
            return
        
        token = login_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        print(f"   ✅ Logged in successfully")
        
        # Step 2: Get available plans
        print("\n[2] Fetching available plans...")
        plans_response = await client.get(f"{BASE_URL}/plans", headers=headers)
        plans = plans_response.json()
        
        if not plans:
            print("   ❌ No plans available")
            return
        
        # Use first plan (One-Time Report)
        plan = plans[0]
        print(f"   ✅ Selected plan: {plan['name']} - ${plan['price']/100:.2f}")
        
        # Step 3: Create checkout
        print("\n[3] Creating checkout session...")
        checkout_response = await client.post(
            f"{BASE_URL}/payments/checkout",
            json={
                "plan_id": plan["id"],
                "return_url": "http://localhost:3000/dashboard"
            },
            headers=headers
        )
        
        if checkout_response.status_code != 200:
            print(f"   ❌ Checkout failed: {checkout_response.text}")
            return
        
        checkout_data = checkout_response.json()
        payment_id = checkout_data["payment_id"]
        payment_url = checkout_data["payment_url"]
        
        print(f"   ✅ Checkout created")
        print(f"      Payment ID: {payment_id}")
        print(f"      Payment URL: {payment_url}")
        
        # Step 4: Simulate PayNow webhook (mark payment as paid)
        print("\n[4] Simulating PayNow payment completion...")
        webhook_response = await client.get(
            f"{BASE_URL}/webhooks/paynow/test",
            params={
                "reference": payment_id,
                "paynow_status": "paid"
            }
        )
        
        if webhook_response.status_code != 200:
            print(f"   ❌ Webhook simulation failed: {webhook_response.text}")
            return
        
        webhook_data = webhook_response.json()
        print(f"   ✅ Payment marked as PAID")
        print(f"      Status: {webhook_data['status']}")
        
        # Wait for delivery processing
        print("\n[5] Waiting for delivery processing...")
        await asyncio.sleep(3)
        
        # Step 5: Check dashboard
        print("\n[6] Checking dashboard for updates...")
        dashboard_response = await client.get(
            f"{BASE_URL}/dashboard",
            headers=headers
        )
        
        if dashboard_response.status_code != 200:
            print(f"   ❌ Dashboard fetch failed: {dashboard_response.text}")
            return
        
        dashboard = dashboard_response.json()
        
        print(f"\n   ✅ Dashboard updated:")
        print(f"      Active Subscriptions: {len([s for s in dashboard.get('subscriptions', []) if s['status'] == 'active'])}")
        print(f"      Total Payments: {len(dashboard.get('payments', []))}")
        print(f"      Total Deliveries: {len(dashboard.get('deliveries', []))}")
        
        # Show latest delivery
        if dashboard.get('deliveries'):
            latest_delivery = dashboard['deliveries'][-1]
            print(f"\n   📦 Latest Delivery:")
            print(f"      Symbol: {latest_delivery.get('symbol', 'N/A')}")
            print(f"      Status: {latest_delivery['status']}")
            print(f"      Created: {latest_delivery['created_at']}")
            if latest_delivery.get('file_path'):
                print(f"      File: {latest_delivery['file_path']}")
        
        # Show latest payment
        if dashboard.get('payments'):
            latest_payment = dashboard['payments'][-1]
            print(f"\n   💳 Latest Payment:")
            print(f"      Amount: ${latest_payment['amount']/100:.2f} {latest_payment['currency']}")
            print(f"      Status: {latest_payment['status']}")
            print(f"      Provider Ref: {latest_payment.get('provider_reference', 'N/A')}")
        
        print("\n" + "=" * 60)
        print("✅ Payment Flow Test Complete!")
        print("=" * 60)
        print("\n💡 Next steps:")
        print("   1. Check your email for delivery confirmation")
        print("   2. Check outputs/ directory for generated plots")
        print("   3. Review backend logs for processing details")


if __name__ == "__main__":
    asyncio.run(main())
