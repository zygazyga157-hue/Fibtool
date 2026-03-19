"""
PayNow payment service integration for Zimbabwe.
Official docs: https://developers.paynow.co.zw/
"""
import httpx
import hashlib
from typing import Tuple, Dict, Optional
from urllib.parse import urlencode

from app.core.config import get_settings

settings = get_settings()


class PayNowClient:
    """PayNow API Client for Zimbabwe payments."""
    
    def __init__(self):
        self.integration_id = settings.PAYNOW_INTEGRATION_ID
        self.integration_key = settings.PAYNOW_INTEGRATION_KEY
        self.return_url = settings.PAYNOW_RETURN_URL
        self.result_url = settings.PAYNOW_RESULT_URL
        self.base_url = "https://www.paynow.co.zw"
        
    def _generate_hash(self, data: Dict[str, str]) -> str:
        """
        Generate PayNow hash for request validation.
        
        Args:
            data: Dictionary of parameters to hash
            
        Returns:
            SHA512 hash string
        """
        # Create values string (all values concatenated)
        values_string = "".join([str(v) for v in data.values()])
        
        # Append integration key
        hash_string = values_string + self.integration_key
        
        # Generate SHA512 hash
        return hashlib.sha512(hash_string.encode()).hexdigest().upper()
    
    async def create_transaction(
        self,
        payment_id: str,
        amount: float,
        email: str,
        description: str,
        additional_info: Optional[str] = None
    ) -> Tuple[bool, str, Optional[str]]:
        """
        Create a PayNow transaction and get payment URL.
        
        Args:
            payment_id: Unique payment identifier
            amount: Payment amount in USD
            email: Customer email
            description: Payment description
            additional_info: Optional additional information
            
        Returns:
            Tuple of (success, message, payment_url)
        """
        try:
            # Prepare payment data
            data = {
                "id": self.integration_id,
                "reference": payment_id,
                "amount": str(amount),
                "additionalinfo": additional_info or description,
                "returnurl": self.return_url,
                "resulturl": self.result_url,
                "authemail": email,
                "status": "Message"
            }
            
            # Generate hash
            data["hash"] = self._generate_hash(data)
            
            print(f"[PayNow] Creating transaction for ${amount} - Reference: {payment_id}")
            
            # Send request to PayNow
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.base_url}/interface/initiatetransaction",
                    data=data,
                    headers={"Content-Type": "application/x-www-form-urlencoded"}
                )
                
                # Parse response
                response_data = self._parse_response(response.text)
                
                status = response_data.get("status", "").lower()
                
                if status == "ok":
                    # Transaction created successfully
                    poll_url = response_data.get("pollurl", "")
                    browser_url = response_data.get("browserurl", "")
                    
                    print(f"[PayNow] Transaction created successfully")
                    print(f"[PayNow] Browser URL: {browser_url}")
                    print(f"[PayNow] Poll URL: {poll_url}")
                    
                    return True, "Transaction created", browser_url
                else:
                    # Transaction creation failed
                    error = response_data.get("error", "Unknown error")
                    print(f"[PayNow] Transaction failed: {error}")
                    return False, f"PayNow error: {error}", None
                    
        except Exception as e:
            print(f"[PayNow] Exception creating transaction: {str(e)}")
            return False, f"Connection error: {str(e)}", None
    
    def _parse_response(self, response_text: str) -> Dict[str, str]:
        """
        Parse PayNow response string into dictionary.
        
        Args:
            response_text: Response text from PayNow (key=value format)
            
        Returns:
            Dictionary of response parameters
        """
        result = {}
        for line in response_text.strip().split("\n"):
            if "=" in line:
                key, value = line.split("=", 1)
                result[key.lower()] = value
        return result
    
    async def check_transaction_status(self, poll_url: str) -> Dict[str, str]:
        """
        Check status of a PayNow transaction.
        
        Args:
            poll_url: Poll URL returned from initiate transaction
            
        Returns:
            Dictionary with transaction status
        """
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(poll_url)
                return self._parse_response(response.text)
        except Exception as e:
            print(f"[PayNow] Error checking status: {str(e)}")
            return {"status": "error", "error": str(e)}
    
    def verify_webhook_hash(self, data: Dict[str, str]) -> bool:
        """
        Verify hash from PayNow webhook.
        
        Args:
            data: Dictionary of webhook parameters
            
        Returns:
            True if hash is valid
        """
        try:
            received_hash = data.get("hash", "")
            
            # Create data dict without hash for verification
            verify_data = {k: v for k, v in data.items() if k.lower() != "hash"}
            
            # Generate expected hash
            expected_hash = self._generate_hash(verify_data)
            
            is_valid = received_hash.upper() == expected_hash.upper()
            
            if not is_valid:
                print(f"[PayNow] Hash verification failed")
                print(f"[PayNow] Expected: {expected_hash}")
                print(f"[PayNow] Received: {received_hash}")
            
            return is_valid
            
        except Exception as e:
            print(f"[PayNow] Error verifying hash: {str(e)}")
            return False


# Global PayNow client instance
paynow_client = PayNowClient()


async def create_paynow_transaction(
    payment_id: str,
    amount: int,
    email: str,
    description: str
) -> Tuple[str, str]:
    """
    Create a PayNow transaction and return payment URL and reference.
    
    Args:
        payment_id: Unique payment ID
        amount: Amount in cents (will be converted to dollars)
        email: Customer email
        description: Payment description
    
    Returns:
        Tuple of (payment_url, paynow_reference)
    """
    # Convert cents to dollars
    amount_usd = amount / 100.0
    
    # Create transaction
    success, message, payment_url = await paynow_client.create_transaction(
        payment_id=payment_id,
        amount=amount_usd,
        email=email,
        description=description,
        additional_info=f"Fibtool - {description}"
    )
    
    if success and payment_url:
        return payment_url, payment_id
    else:
        # If PayNow fails, return demo URL
        print(f"[PayNow] Using fallback demo URL: {message}")
        demo_url = f"https://paynow.example.com/payment/{payment_id}"
        return demo_url, payment_id


def verify_webhook_signature(data: Dict[str, str]) -> bool:
    """
    Verify webhook signature from PayNow.
    
    Args:
        data: Dictionary of webhook parameters
        
    Returns:
        True if signature is valid
    """
    return paynow_client.verify_webhook_hash(data)


async def create_paynow_inline_data(
    payment_id: str,
    amount: int,
    email: str,
    description: str
) -> Dict[str, str]:
    """
    Create PayNow transaction data for inline/modal payment (no redirect).
    Returns form data that frontend can POST to PayNow.
    
    Args:
        payment_id: Unique payment ID
        amount: Amount in cents (will be converted to dollars)
        email: Customer email
        description: Payment description
    
    Returns:
        Dictionary containing form fields and action URL
    """
    # Convert cents to dollars
    amount_usd = amount / 100.0
    
    # Prepare payment data (same as create_transaction but return raw data)
    data = {
        "id": paynow_client.integration_id,
        "reference": payment_id,
        "amount": str(amount_usd),
        "additionalinfo": f"Fibtool - {description}",
        "returnurl": paynow_client.return_url,
        "resulturl": paynow_client.result_url,
        "authemail": email,
        "status": "Message"
    }
    
    # Generate hash
    data["hash"] = paynow_client._generate_hash(data)
    
    print(f"[PayNow] Creating inline transaction for ${amount_usd} - Reference: {payment_id}")
    
    try:
        # Send request to PayNow to get browser URL
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{paynow_client.base_url}/interface/initiatetransaction",
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            
            # Parse response
            response_data = paynow_client._parse_response(response.text)
            
            status = response_data.get("status", "").lower()
            
            if status == "ok":
                # Return form data with browser URL
                return {
                    "action_url": response_data.get("browserurl", ""),
                    "poll_url": response_data.get("pollurl", ""),
                    "reference": payment_id,
                    "amount": amount_usd,
                    "email": email,
                    "description": description
                }
            else:
                # Return demo data if PayNow fails
                print(f"[PayNow] Using fallback demo data: {response_data.get('error', 'Unknown error')}")
                return {
                    "action_url": f"https://demo.paynow.co.zw/payment/{payment_id}",
                    "poll_url": "",
                    "reference": payment_id,
                    "amount": amount_usd,
                    "email": email,
                    "description": description,
                    "demo_mode": True
                }
    except Exception as e:
        print(f"[PayNow] Error creating inline transaction: {e}")
        # Return demo data
        return {
            "action_url": f"https://demo.paynow.co.zw/payment/{payment_id}",
            "poll_url": "",
            "reference": payment_id,
            "amount": amount_usd,
            "email": email,
            "description": description,
            "demo_mode": True
        }


