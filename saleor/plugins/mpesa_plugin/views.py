import json
import logging
from django.http import JsonResponse, HttpRequest
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

logger = logging.getLogger(__name__)


@csrf_exempt
@require_http_methods(["POST"])
def mpesa_callback(request: HttpRequest) -> JsonResponse:
    """
    M-Pesa callback endpoint
    
    This endpoint receives payment confirmations from M-Pesa after
    an STK push is completed (successful or failed).
    
    M-Pesa expects a 200 OK response to acknowledge receipt of the callback.
    
    The callback data structure:
    {
        "Body": {
            "stkCallback": {
                "MerchantRequestID": "...",
                "CheckoutRequestID": "...",
                "ResultCode": 0,
                "ResultDesc": "The service request is processed successfully.",
                "CallbackMetadata": {
                    "Item": [
                        {"Name": "Amount", "Value": 1.00},
                        {"Name": "MpesaReceiptNumber", "Value": "..."},
                        {"Name": "TransactionDate", "Value": 20230101120000},
                        {"Name": "PhoneNumber", "Value": 254712345678}
                    ]
                }
            }
        }
    }
    """
    try:
        callback_data = json.loads(request.body.decode('utf-8'))
        
        logger.info(f'M-Pesa callback received: {json.dumps(callback_data, indent=2)}')
        
        body = callback_data.get('Body', {})
        stk_callback = body.get('stkCallback', {})
        
        checkout_request_id = stk_callback.get('CheckoutRequestID')
        merchant_request_id = stk_callback.get('MerchantRequestID')
        result_code = stk_callback.get('ResultCode')
        result_desc = stk_callback.get('ResultDesc')
        
        if result_code == 0:
            callback_metadata = stk_callback.get('CallbackMetadata', {})
            items = callback_metadata.get('Item', [])
            
            metadata = {}
            for item in items:
                name = item.get('Name')
                value = item.get('Value')
                if name:
                    metadata[name] = value
            
            logger.info(
                f'Payment successful - CheckoutRequestID: {checkout_request_id}, '
                f'Receipt: {metadata.get("MpesaReceiptNumber")}, '
                f'Amount: {metadata.get("Amount")}'
            )
            
        else:
            logger.warning(
                f'Payment failed - CheckoutRequestID: {checkout_request_id}, '
                f'ResultCode: {result_code}, ResultDesc: {result_desc}'
            )
        
        return JsonResponse({
            'ResultCode': 0,
            'ResultDesc': 'Callback received successfully'
        }, status=200)
        
    except json.JSONDecodeError as e:
        logger.error(f'Invalid JSON in callback: {e}')
        return JsonResponse({
            'ResultCode': 1,
            'ResultDesc': 'Invalid JSON'
        }, status=400)
        
    except Exception as e:
        logger.exception(f'Error processing M-Pesa callback: {e}')
        return JsonResponse({
            'ResultCode': 1,
            'ResultDesc': 'Internal server error'
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def mpesa_timeout(request: HttpRequest) -> JsonResponse:
    """
    M-Pesa timeout callback endpoint
    
    This endpoint is called when a transaction times out
    (customer doesn't respond to STK push within time limit).
    """
    try:
        timeout_data = json.loads(request.body.decode('utf-8'))
        
        logger.warning(f'M-Pesa timeout received: {json.dumps(timeout_data, indent=2)}')
        
        return JsonResponse({
            'ResultCode': 0,
            'ResultDesc': 'Timeout received successfully'
        }, status=200)
        
    except Exception as e:
        logger.exception(f'Error processing M-Pesa timeout: {e}')
        return JsonResponse({
            'ResultCode': 1,
            'ResultDesc': 'Internal server error'
        }, status=500)


@require_http_methods(["GET"])
def mpesa_status(request: HttpRequest) -> JsonResponse:
    """
    Health check endpoint for M-Pesa plugin
    
    Returns basic status information about the plugin.
    """
    return JsonResponse({
        'status': 'active',
        'plugin': 'M-Pesa Payment Gateway',
        'version': '1.0.0',
        'endpoints': {
            'callback': '/api/plugins/mpesa/callback/',
            'timeout': '/api/plugins/mpesa/timeout/',
            'status': '/api/plugins/mpesa/status/'
        }
    }, status=200)
