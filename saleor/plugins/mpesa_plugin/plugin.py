import logging
from decimal import Decimal
from typing import Optional, Any, Dict

from django.core.exceptions import ValidationError

from saleor.plugins.base_plugin import BasePlugin, ConfigurationTypeField
from saleor.payment.interface import (
    GatewayResponse,
    PaymentData,
    TransactionKind,
)

from .utils import (
    get_access_token,
    initiate_stk_push,
    query_transaction_status,
    MpesaAPIError,
)

logger = logging.getLogger(__name__)


class MpesaPaymentPlugin(BasePlugin):
    """
    M-Pesa Payment Plugin for Saleor
    
    Integrates with Safaricom's M-Pesa Daraja API to process payments
    via STK Push (Lipa Na M-Pesa Online).
    """
    
    PLUGIN_ID = "mirumee.payments.mpesa"
    PLUGIN_NAME = "M-Pesa Payment Gateway"
    PLUGIN_DESCRIPTION = "Accept M-Pesa payments via STK Push"
    DEFAULT_ACTIVE = False
    CONFIGURATION_PER_CHANNEL = True
    
    DEFAULT_CONFIGURATION = [
        {"name": "consumer_key", "value": None},
        {"name": "consumer_secret", "value": None},
        {"name": "shortcode", "value": None},
        {"name": "passkey", "value": None},
        {"name": "environment", "value": "sandbox"},
        {"name": "callback_url", "value": None},
    ]
    
    CONFIG_STRUCTURE = {
        "consumer_key": {
            "type": ConfigurationTypeField.STRING,
            "help_text": "M-Pesa API Consumer Key from Daraja Portal",
            "label": "Consumer Key",
        },
        "consumer_secret": {
            "type": ConfigurationTypeField.SECRET,
            "help_text": "M-Pesa API Consumer Secret from Daraja Portal",
            "label": "Consumer Secret",
        },
        "shortcode": {
            "type": ConfigurationTypeField.STRING,
            "help_text": "M-Pesa Business Shortcode (Paybill or Till Number)",
            "label": "Business Shortcode",
        },
        "passkey": {
            "type": ConfigurationTypeField.SECRET,
            "help_text": "Lipa Na M-Pesa Online Passkey from Daraja Portal",
            "label": "Passkey",
        },
        "environment": {
            "type": ConfigurationTypeField.STRING,
            "help_text": "API Environment: 'sandbox' or 'production'",
            "label": "Environment",
        },
        "callback_url": {
            "type": ConfigurationTypeField.STRING,
            "help_text": "Public URL for M-Pesa to send payment confirmations",
            "label": "Callback URL",
        },
    }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        configuration = {item["name"]: item["value"] for item in self.configuration}
        
        self.consumer_key = configuration.get("consumer_key") or ""
        self.consumer_secret = configuration.get("consumer_secret") or ""
        self.shortcode = configuration.get("shortcode") or ""
        self.passkey = configuration.get("passkey") or ""
        self.environment = configuration.get("environment") or "sandbox"
        self.callback_url = configuration.get("callback_url") or ""
        
    def _validate_configuration(self) -> bool:
        """Validate that all required credentials are configured"""
        required_fields = [
            self.consumer_key,
            self.consumer_secret,
            self.shortcode,
            self.passkey,
        ]
        return all(required_fields)
    
    async def process_payment(
        self,
        payment_information: PaymentData,
        previous_value: Any = None
    ) -> GatewayResponse:
        """
        Process a payment by initiating M-Pesa STK Push
        
        Args:
            payment_information: Payment details including amount and phone number
            previous_value: Previous payment data (if any)
            
        Returns:
            GatewayResponse with transaction details or error information
        """
        if not self._validate_configuration():
            logger.error("M-Pesa plugin not properly configured")
            return GatewayResponse(
                is_success=False,
                action_required=False,
                kind=TransactionKind.AUTH,
                amount=payment_information.amount,
                currency=payment_information.currency,
                transaction_id="",
                error="Payment gateway not configured",
                raw_response={},
            )
        
        try:
            amount = float(payment_information.amount)
            phone_number = self._extract_phone_number(payment_information)
            
            if not phone_number:
                raise ValidationError("Phone number is required for M-Pesa payment")
            
            account_reference = payment_information.order_id or "SALEOR-ORDER"
            transaction_desc = f"Payment for order {payment_information.order_id}"
            
            logger.info(
                f"Initiating STK push for amount {amount} to {phone_number}"
            )
            
            access_token = await get_access_token(
                self.consumer_key,
                self.consumer_secret,
                self.environment
            )
            
            stk_response = await initiate_stk_push(
                access_token=access_token,
                shortcode=self.shortcode,
                passkey=self.passkey,
                amount=amount,
                phone_number=phone_number,
                callback_url=self.callback_url,
                account_reference=account_reference,
                transaction_desc=transaction_desc,
                environment=self.environment
            )
            
            if stk_response.get('ResponseCode') == '0':
                checkout_request_id = stk_response.get('CheckoutRequestID')
                merchant_request_id = stk_response.get('MerchantRequestID')
                
                logger.info(
                    f"STK push initiated successfully. "
                    f"CheckoutRequestID: {checkout_request_id}"
                )
                
                return GatewayResponse(
                    is_success=True,
                    action_required=True,
                    kind=TransactionKind.AUTH,
                    amount=payment_information.amount,
                    currency=payment_information.currency,
                    transaction_id=checkout_request_id,
                    error=None,
                    raw_response=stk_response,
                    psp_reference=merchant_request_id,
                )
            else:
                error_msg = stk_response.get('errorMessage', 'Unknown error')
                logger.error(f"STK push failed: {error_msg}")
                
                return GatewayResponse(
                    is_success=False,
                    action_required=False,
                    kind=TransactionKind.AUTH,
                    amount=payment_information.amount,
                    currency=payment_information.currency,
                    transaction_id="",
                    error=f"M-Pesa error: {error_msg}",
                    raw_response=stk_response,
                )
                
        except MpesaAPIError as e:
            logger.exception("M-Pesa API error during payment processing")
            return GatewayResponse(
                is_success=False,
                action_required=False,
                kind=TransactionKind.AUTH,
                amount=payment_information.amount,
                currency=payment_information.currency,
                transaction_id="",
                error=f"M-Pesa API error: {str(e)}",
                raw_response={},
            )
            
        except Exception as e:
            logger.exception("Unexpected error during payment processing")
            return GatewayResponse(
                is_success=False,
                action_required=False,
                kind=TransactionKind.AUTH,
                amount=payment_information.amount,
                currency=payment_information.currency,
                transaction_id="",
                error=f"Payment processing error: {str(e)}",
                raw_response={},
            )
    
    async def confirm_payment(
        self,
        payment_information: PaymentData,
        previous_value: Any = None
    ) -> GatewayResponse:
        """
        Confirm payment status by querying M-Pesa transaction status
        
        This method is called to verify if a payment has been completed.
        It can be triggered manually or as part of the callback flow.
        
        Args:
            payment_information: Payment details with transaction token
            previous_value: Previous payment data
            
        Returns:
            GatewayResponse with confirmation status
        """
        if not payment_information.token:
            return GatewayResponse(
                is_success=False,
                action_required=False,
                kind=TransactionKind.CAPTURE,
                amount=payment_information.amount,
                currency=payment_information.currency,
                transaction_id="",
                error="No transaction token to confirm",
                raw_response={},
            )
        
        try:
            access_token = await get_access_token(
                self.consumer_key,
                self.consumer_secret,
                self.environment
            )
            
            status_response = await query_transaction_status(
                access_token=access_token,
                shortcode=self.shortcode,
                passkey=self.passkey,
                checkout_request_id=payment_information.token,
                environment=self.environment
            )
            
            result_code = status_response.get('ResultCode')
            
            if result_code == '0':
                logger.info(
                    f"Payment confirmed for CheckoutRequestID: "
                    f"{payment_information.token}"
                )
                return GatewayResponse(
                    is_success=True,
                    action_required=False,
                    kind=TransactionKind.CAPTURE,
                    amount=payment_information.amount,
                    currency=payment_information.currency,
                    transaction_id=payment_information.token,
                    error=None,
                    raw_response=status_response,
                )
            elif result_code == '1032':
                return GatewayResponse(
                    is_success=False,
                    action_required=False,
                    kind=TransactionKind.CANCEL,
                    amount=payment_information.amount,
                    currency=payment_information.currency,
                    transaction_id=payment_information.token,
                    error="Payment cancelled by user",
                    raw_response=status_response,
                )
            elif result_code == '1':
                return GatewayResponse(
                    is_success=False,
                    action_required=False,
                    kind=TransactionKind.CANCEL,
                    amount=payment_information.amount,
                    currency=payment_information.currency,
                    transaction_id=payment_information.token,
                    error="Insufficient funds",
                    raw_response=status_response,
                )
            elif result_code == '1037':
                return GatewayResponse(
                    is_success=False,
                    action_required=False,
                    kind=TransactionKind.CANCEL,
                    amount=payment_information.amount,
                    currency=payment_information.currency,
                    transaction_id=payment_information.token,
                    error="Transaction timeout",
                    raw_response=status_response,
                )
            else:
                error_msg = status_response.get('ResultDesc', 'Unknown error')
                return GatewayResponse(
                    is_success=False,
                    action_required=False,
                    kind=TransactionKind.CANCEL,
                    amount=payment_information.amount,
                    currency=payment_information.currency,
                    transaction_id=payment_information.token,
                    error=f"Payment failed: {error_msg}",
                    raw_response=status_response,
                )
                
        except MpesaAPIError as e:
            logger.exception("M-Pesa API error during payment confirmation")
            return GatewayResponse(
                is_success=False,
                action_required=False,
                kind=TransactionKind.CAPTURE,
                amount=payment_information.amount,
                currency=payment_information.currency,
                transaction_id=payment_information.token or "",
                error=f"M-Pesa API error: {str(e)}",
                raw_response={},
            )
            
        except Exception as e:
            logger.exception("Unexpected error during payment confirmation")
            return GatewayResponse(
                is_success=False,
                action_required=False,
                kind=TransactionKind.CAPTURE,
                amount=payment_information.amount,
                currency=payment_information.currency,
                transaction_id=payment_information.token or "",
                error=f"Payment confirmation error: {str(e)}",
                raw_response={},
            )
    
    async def refund_payment(
        self,
        payment_information: PaymentData,
        previous_value: Any = None
    ) -> GatewayResponse:
        """
        Refund/reverse an M-Pesa payment
        
        Note: M-Pesa reversal API has strict requirements and limitations.
        Reversals must be done within a specific timeframe and require
        additional approval flows.
        
        Args:
            payment_information: Payment details to refund
            previous_value: Previous payment data
            
        Returns:
            GatewayResponse with refund status
        """
        logger.warning(
            "M-Pesa refund requested but not fully implemented. "
            "Manual reversal may be required."
        )
        
        return GatewayResponse(
            is_success=False,
            action_required=False,
            kind=TransactionKind.REFUND,
            amount=payment_information.amount,
            currency=payment_information.currency,
            transaction_id=payment_information.token or "",
            error="Automatic refunds not supported. Please contact M-Pesa support for manual reversal.",
            raw_response={},
        )
    
    def _extract_phone_number(self, payment_information: PaymentData) -> Optional[str]:
        """
        Extract phone number from payment information
        
        Looks for phone number in billing address or metadata.
        Phone number should be in format: 254XXXXXXXXX (Kenya format)
        """
        if payment_information.billing:
            phone = payment_information.billing.get('phone')
            if phone:
                return self._normalize_phone_number(phone)
        
        if payment_information.graphql_payment_id:
            return None
        
        return None
    
    def _normalize_phone_number(self, phone: str) -> str:
        """
        Normalize phone number to M-Pesa format (254XXXXXXXXX)
        
        Accepts formats like:
        - 254712345678
        - +254712345678
        - 0712345678
        - 712345678
        """
        phone = phone.strip().replace(' ', '').replace('-', '')
        
        if phone.startswith('+254'):
            phone = phone[1:]
        elif phone.startswith('0'):
            phone = '254' + phone[1:]
        elif not phone.startswith('254'):
            phone = '254' + phone
        
        return phone
    
    def process_callback(self, callback_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process M-Pesa callback data
        
        This method is called by the callback view when M-Pesa sends
        a payment confirmation.
        
        Args:
            callback_data: Raw callback data from M-Pesa
            
        Returns:
            Processed callback information including payment status
        """
        try:
            body = callback_data.get('Body', {})
            stk_callback = body.get('stkCallback', {})
            
            result_code = stk_callback.get('ResultCode')
            checkout_request_id = stk_callback.get('CheckoutRequestID')
            merchant_request_id = stk_callback.get('MerchantRequestID')
            result_desc = stk_callback.get('ResultDesc')
            
            callback_metadata = stk_callback.get('CallbackMetadata', {})
            items = callback_metadata.get('Item', [])
            
            metadata = {}
            for item in items:
                key = item.get('Name')
                value = item.get('Value')
                if key:
                    metadata[key] = value
            
            payment_status = {
                'checkout_request_id': checkout_request_id,
                'merchant_request_id': merchant_request_id,
                'result_code': result_code,
                'result_desc': result_desc,
                'amount': metadata.get('Amount'),
                'mpesa_receipt_number': metadata.get('MpesaReceiptNumber'),
                'transaction_date': metadata.get('TransactionDate'),
                'phone_number': metadata.get('PhoneNumber'),
                'success': result_code == 0,
            }
            
            logger.info(
                f"Callback processed for CheckoutRequestID: {checkout_request_id}. "
                f"Result: {result_desc}"
            )
            
            return payment_status
            
        except Exception as e:
            logger.exception("Error processing M-Pesa callback")
            return {
                'success': False,
                'error': str(e)
            }
