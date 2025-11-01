import base64
import logging
from datetime import datetime
from typing import Dict, Any
import httpx

logger = logging.getLogger(__name__)


class MpesaAPIError(Exception):
    """Custom exception for M-Pesa API errors"""
    pass


def get_api_base_url(environment: str) -> str:
    """Get the appropriate M-Pesa API base URL based on environment"""
    if environment.lower() == 'production':
        return 'https://api.safaricom.co.ke'
    return 'https://sandbox.safaricom.co.ke'


async def get_access_token(
    consumer_key: str,
    consumer_secret: str,
    environment: str = 'sandbox'
) -> str:
    """
    Generate OAuth access token for M-Pesa API
    
    Args:
        consumer_key: M-Pesa consumer key
        consumer_secret: M-Pesa consumer secret
        environment: 'sandbox' or 'production'
        
    Returns:
        Access token string
        
    Raises:
        MpesaAPIError: If token generation fails
    """
    base_url = get_api_base_url(environment)
    url = f'{base_url}/oauth/v1/generate?grant_type=client_credentials'
    
    auth_string = f'{consumer_key}:{consumer_secret}'
    auth_bytes = auth_string.encode('ascii')
    auth_base64 = base64.b64encode(auth_bytes).decode('ascii')
    
    headers = {
        'Authorization': f'Basic {auth_base64}',
        'Content-Type': 'application/json',
    }
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            
            data = response.json()
            access_token = data.get('access_token')
            
            if not access_token:
                raise MpesaAPIError('No access token in response')
            
            logger.info('M-Pesa access token generated successfully')
            return access_token
            
    except httpx.HTTPStatusError as e:
        logger.error(f'HTTP error during token generation: {e}')
        raise MpesaAPIError(f'Failed to generate access token: {e}')
    except httpx.RequestError as e:
        logger.error(f'Request error during token generation: {e}')
        raise MpesaAPIError(f'Network error during token generation: {e}')
    except Exception as e:
        logger.error(f'Unexpected error during token generation: {e}')
        raise MpesaAPIError(f'Unexpected error: {e}')


def generate_password(shortcode: str, passkey: str, timestamp: str) -> str:
    """
    Generate the password for STK push request
    
    Password is base64 encoded string of: Shortcode + Passkey + Timestamp
    
    Args:
        shortcode: M-Pesa business shortcode
        passkey: M-Pesa passkey
        timestamp: Timestamp in format YYYYMMDDHHmmss
        
    Returns:
        Base64 encoded password
    """
    password_string = f'{shortcode}{passkey}{timestamp}'
    password_bytes = password_string.encode('ascii')
    return base64.b64encode(password_bytes).decode('ascii')


def get_timestamp() -> str:
    """
    Get current timestamp in M-Pesa format
    
    Returns:
        Timestamp string in format: YYYYMMDDHHmmss
    """
    return datetime.now().strftime('%Y%m%d%H%M%S')


async def initiate_stk_push(
    access_token: str,
    shortcode: str,
    passkey: str,
    amount: float,
    phone_number: str,
    callback_url: str,
    account_reference: str,
    transaction_desc: str,
    environment: str = 'sandbox'
) -> Dict[str, Any]:
    """
    Initiate M-Pesa STK Push (Lipa Na M-Pesa Online)
    
    Args:
        access_token: OAuth access token
        shortcode: Business shortcode
        passkey: Lipa Na M-Pesa Online passkey
        amount: Amount to charge
        phone_number: Customer phone number (254XXXXXXXXX format)
        callback_url: URL to receive payment confirmation
        account_reference: Reference for the transaction
        transaction_desc: Description of the transaction
        environment: 'sandbox' or 'production'
        
    Returns:
        API response dictionary
        
    Raises:
        MpesaAPIError: If STK push fails
    """
    base_url = get_api_base_url(environment)
    url = f'{base_url}/mpesa/stkpush/v1/processrequest'
    
    timestamp = get_timestamp()
    password = generate_password(shortcode, passkey, timestamp)
    
    payload = {
        'BusinessShortCode': shortcode,
        'Password': password,
        'Timestamp': timestamp,
        'TransactionType': 'CustomerPayBillOnline',
        'Amount': int(amount),
        'PartyA': phone_number,
        'PartyB': shortcode,
        'PhoneNumber': phone_number,
        'CallBackURL': callback_url,
        'AccountReference': account_reference,
        'TransactionDesc': transaction_desc,
    }
    
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json',
    }
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            
            data = response.json()
            logger.info(f'STK push initiated: {data}')
            return data
            
    except httpx.HTTPStatusError as e:
        error_data = {}
        try:
            error_data = e.response.json()
        except:
            pass
        logger.error(f'HTTP error during STK push: {e}, Response: {error_data}')
        raise MpesaAPIError(f'STK push failed: {error_data.get("errorMessage", str(e))}')
    except httpx.RequestError as e:
        logger.error(f'Request error during STK push: {e}')
        raise MpesaAPIError(f'Network error during STK push: {e}')
    except Exception as e:
        logger.error(f'Unexpected error during STK push: {e}')
        raise MpesaAPIError(f'Unexpected error: {e}')


async def query_transaction_status(
    access_token: str,
    shortcode: str,
    passkey: str,
    checkout_request_id: str,
    environment: str = 'sandbox'
) -> Dict[str, Any]:
    """
    Query the status of an M-Pesa transaction
    
    Args:
        access_token: OAuth access token
        shortcode: Business shortcode
        passkey: Lipa Na M-Pesa Online passkey
        checkout_request_id: CheckoutRequestID from STK push response
        environment: 'sandbox' or 'production'
        
    Returns:
        API response with transaction status
        
    Raises:
        MpesaAPIError: If query fails
    """
    base_url = get_api_base_url(environment)
    url = f'{base_url}/mpesa/stkpushquery/v1/query'
    
    timestamp = get_timestamp()
    password = generate_password(shortcode, passkey, timestamp)
    
    payload = {
        'BusinessShortCode': shortcode,
        'Password': password,
        'Timestamp': timestamp,
        'CheckoutRequestID': checkout_request_id,
    }
    
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json',
    }
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            
            data = response.json()
            logger.info(f'Transaction status queried: {data}')
            return data
            
    except httpx.HTTPStatusError as e:
        error_data = {}
        try:
            error_data = e.response.json()
        except:
            pass
        logger.error(f'HTTP error during status query: {e}, Response: {error_data}')
        raise MpesaAPIError(f'Status query failed: {error_data.get("errorMessage", str(e))}')
    except httpx.RequestError as e:
        logger.error(f'Request error during status query: {e}')
        raise MpesaAPIError(f'Network error during status query: {e}')
    except Exception as e:
        logger.error(f'Unexpected error during status query: {e}')
        raise MpesaAPIError(f'Unexpected error: {e}')


async def initiate_reversal(
    access_token: str,
    initiator: str,
    security_credential: str,
    transaction_id: str,
    amount: float,
    receiver_party: str,
    remarks: str,
    queue_timeout_url: str,
    result_url: str,
    occasion: str = '',
    environment: str = 'sandbox'
) -> Dict[str, Any]:
    """
    Initiate M-Pesa transaction reversal
    
    Note: This requires additional credentials and approval from Safaricom.
    Most merchants will need to handle refunds manually through M-Pesa support.
    
    Args:
        access_token: OAuth access token
        initiator: Username of the API operator
        security_credential: Encrypted credential
        transaction_id: M-Pesa transaction ID to reverse
        amount: Amount to reverse
        receiver_party: Organization receiving the reversal
        remarks: Comments for the reversal
        queue_timeout_url: Timeout callback URL
        result_url: Result callback URL
        occasion: Optional occasion
        environment: 'sandbox' or 'production'
        
    Returns:
        API response dictionary
        
    Raises:
        MpesaAPIError: If reversal fails
    """
    base_url = get_api_base_url(environment)
    url = f'{base_url}/mpesa/reversal/v1/request'
    
    payload = {
        'Initiator': initiator,
        'SecurityCredential': security_credential,
        'CommandID': 'TransactionReversal',
        'TransactionID': transaction_id,
        'Amount': int(amount),
        'ReceiverParty': receiver_party,
        'RecieverIdentifierType': '11',
        'Remarks': remarks,
        'QueueTimeOutURL': queue_timeout_url,
        'ResultURL': result_url,
        'Occasion': occasion,
    }
    
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json',
    }
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            
            data = response.json()
            logger.info(f'Reversal initiated: {data}')
            return data
            
    except httpx.HTTPStatusError as e:
        error_data = {}
        try:
            error_data = e.response.json()
        except:
            pass
        logger.error(f'HTTP error during reversal: {e}, Response: {error_data}')
        raise MpesaAPIError(f'Reversal failed: {error_data.get("errorMessage", str(e))}')
    except httpx.RequestError as e:
        logger.error(f'Request error during reversal: {e}')
        raise MpesaAPIError(f'Network error during reversal: {e}')
    except Exception as e:
        logger.error(f'Unexpected error during reversal: {e}')
        raise MpesaAPIError(f'Unexpected error: {e}')
