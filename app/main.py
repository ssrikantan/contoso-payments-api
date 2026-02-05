"""
Contoso Payments API
====================
Payment processing service for the Contoso e-commerce platform.
Handles payment authorization, capture, and refunds.
"""
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from enum import Enum
import uuid
import hashlib

app = FastAPI(
    title="Contoso Payments API",
    description="Payment processing service for Contoso e-commerce",
    version="1.0.0",
)

# =============================================================================
# MODELS
# =============================================================================

class PaymentStatus(str, Enum):
    PENDING = "pending"
    AUTHORIZED = "authorized"
    CAPTURED = "captured"
    DECLINED = "declined"
    FAILED = "failed"
    REFUNDED = "refunded"
    PARTIALLY_REFUNDED = "partially_refunded"
    VOIDED = "voided"

class PaymentMethod(str, Enum):
    CREDIT_CARD = "credit_card"
    DEBIT_CARD = "debit_card"
    BANK_TRANSFER = "bank_transfer"
    DIGITAL_WALLET = "digital_wallet"

class CardDetails(BaseModel):
    """Card details - NOTE: In production, use tokenized references only!"""
    card_token: str = Field(..., description="Tokenized card reference (never store raw card numbers)")
    last_four: str = Field(..., min_length=4, max_length=4)
    brand: str  # visa, mastercard, amex
    exp_month: int = Field(..., ge=1, le=12)
    exp_year: int = Field(..., ge=2024)

class Payment(BaseModel):
    id: str = Field(default_factory=lambda: f"PAY-{uuid.uuid4().hex[:12].upper()}")
    order_id: str
    customer_id: str
    amount: float = Field(..., gt=0)
    currency: str = "USD"
    status: PaymentStatus = PaymentStatus.PENDING
    payment_method: PaymentMethod
    card_last_four: Optional[str] = None
    card_brand: Optional[str] = None
    authorization_code: Optional[str] = None
    decline_reason: Optional[str] = None
    refunded_amount: float = 0.0
    idempotency_key: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    captured_at: Optional[datetime] = None
    refunded_at: Optional[datetime] = None

class PaymentCreate(BaseModel):
    order_id: str
    customer_id: str
    amount: float = Field(..., gt=0)
    currency: str = "USD"
    payment_method: PaymentMethod
    card_details: Optional[CardDetails] = None
    idempotency_key: Optional[str] = None

class RefundRequest(BaseModel):
    amount: Optional[float] = Field(default=None, gt=0, description="Partial refund amount. Omit for full refund.")
    reason: str = "customer_request"

# =============================================================================
# IN-MEMORY DATABASE (for demo purposes)
# =============================================================================

payments_db: dict[str, Payment] = {}
idempotency_cache: dict[str, str] = {}  # idempotency_key -> payment_id

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def generate_auth_code() -> str:
    """Generate mock authorization code."""
    return hashlib.sha256(uuid.uuid4().bytes).hexdigest()[:8].upper()

def simulate_payment_gateway(amount: float, card_token: str) -> tuple[bool, Optional[str], Optional[str]]:
    """
    Simulate payment gateway response.
    In production, this would call Stripe/Adyen/etc.
    
    Returns: (success, auth_code, decline_reason)
    """
    print(f"Simulating payment gateway call for ${amount}")
    
    # Simulate various outcomes for demo
    if "DECLINE" in card_token.upper():
        return False, None, "Card declined by issuer"
    if "INSUFFICIENT" in card_token.upper():
        return False, None, "Insufficient funds"
    if amount > 10000:
        return False, None, "Amount exceeds limit"
    
    return True, generate_auth_code(), None

# =============================================================================
# ENDPOINTS
# =============================================================================

@app.get("/")
def root():
    """Root endpoint returning service info."""
    return {
        "service": "contoso-payments-api",
        "message": "Welcome to Contoso Payments API",
        "version": "1.0.0",
        "note": "HIGH-IMPACT SERVICE - SRE approval required for changes"
    }


@app.get("/payments/{payment_id}", response_model=Payment)
def get_payment(payment_id: str):
    """Get payment details by ID."""
    if payment_id not in payments_db:
        raise HTTPException(status_code=404, detail="Payment not found")
    return payments_db[payment_id]


@app.get("/payments")
def list_payments(
    order_id: Optional[str] = None,
    customer_id: Optional[str] = None,
    status: Optional[PaymentStatus] = None,
    limit: int = 50,
):
    """List payments with optional filtering."""
    print(f"Listing payments, order_id={order_id}, customer_id={customer_id}")
    
    payments = list(payments_db.values())
    
    if order_id:
        payments = [p for p in payments if p.order_id == order_id]
    if customer_id:
        payments = [p for p in payments if p.customer_id == customer_id]
    if status:
        payments = [p for p in payments if p.status == status]
    
    return payments[:limit]


@app.post("/payments/authorize", response_model=Payment, status_code=201)
def authorize_payment(payment_data: PaymentCreate):
    """
    Authorize a payment (place hold on funds).
    
    This is a high-impact endpoint - all authorization attempts are logged
    for compliance and fraud detection.
    """

    print(f"Authorizing payment for order {payment_data.order_id}, amount=${payment_data.amount}")
    
    # Idempotency check
    if payment_data.idempotency_key and payment_data.idempotency_key in idempotency_cache:
        existing_id = idempotency_cache[payment_data.idempotency_key]
        print(f"Idempotency hit: returning existing payment {existing_id}")
        return payments_db[existing_id]
    
    # Validate card details for card payments
    if payment_data.payment_method in [PaymentMethod.CREDIT_CARD, PaymentMethod.DEBIT_CARD]:
        if not payment_data.card_details:
            raise HTTPException(status_code=400, detail="Card details required for card payments")
    
    # Simulate gateway call
    card_token = payment_data.card_details.card_token if payment_data.card_details else "WALLET"
    success, auth_code, decline_reason = simulate_payment_gateway(payment_data.amount, card_token)
    
    # Create payment record
    payment = Payment(
        order_id=payment_data.order_id,
        customer_id=payment_data.customer_id,
        amount=payment_data.amount,
        currency=payment_data.currency,
        payment_method=payment_data.payment_method,
        card_last_four=payment_data.card_details.last_four if payment_data.card_details else None,
        card_brand=payment_data.card_details.brand if payment_data.card_details else None,
        status=PaymentStatus.AUTHORIZED if success else PaymentStatus.DECLINED,
        authorization_code=auth_code,
        decline_reason=decline_reason,
        idempotency_key=payment_data.idempotency_key,
    )
    
    payments_db[payment.id] = payment
    
    if payment_data.idempotency_key:
        idempotency_cache[payment_data.idempotency_key] = payment.id
    
    if success:
        print(f"Payment {payment.id} authorized successfully, auth_code={auth_code}")
    else:
        print(f"Payment {payment.id} declined: {decline_reason}")
    
    if not success:
        raise HTTPException(status_code=402, detail=f"Payment declined: {decline_reason}")
    
    return payment


@app.post("/payments/{payment_id}/capture", response_model=Payment)
def capture_payment(payment_id: str):
    """
    Capture an authorized payment (actually charge the card).
    
    Must be called within 7 days of authorization or auth will expire.
    """
    if payment_id not in payments_db:
        raise HTTPException(status_code=404, detail="Payment not found")
    
    payment = payments_db[payment_id]
    
    if payment.status != PaymentStatus.AUTHORIZED:
        raise HTTPException(
            status_code=400, 
            detail=f"Cannot capture payment in {payment.status} status"
        )
    
    # In production: call gateway to capture funds
    payment.status = PaymentStatus.CAPTURED
    payment.captured_at = datetime.utcnow()
    payment.updated_at = datetime.utcnow()
    print(f"Payment {payment_id} captured, amount=${payment.amount}")
    return payment


@app.post("/payments/{payment_id}/void", response_model=Payment)
def void_payment(payment_id: str):
    """
    Void an authorized payment (release the hold without charging).
    
    Can only void authorized payments that haven't been captured.
    """
    if payment_id not in payments_db:
        raise HTTPException(status_code=404, detail="Payment not found")
    
    payment = payments_db[payment_id]
    
    if payment.status != PaymentStatus.AUTHORIZED:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot void payment in {payment.status} status"
        )
    
    payment.status = PaymentStatus.VOIDED
    payment.updated_at = datetime.utcnow()
    print(f"Payment {payment_id} voided")
    return payment


@app.post("/payments/{payment_id}/refund", response_model=Payment)
def refund_payment(payment_id: str, refund: RefundRequest):
    """
    Refund a captured payment (full or partial).
    
    Partial refunds are allowed. Total refunded cannot exceed original amount.
    """
    if payment_id not in payments_db:
        raise HTTPException(status_code=404, detail="Payment not found")
    
    payment = payments_db[payment_id]
    
    if payment.status not in [PaymentStatus.CAPTURED, PaymentStatus.PARTIALLY_REFUNDED]:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot refund payment in {payment.status} status"
        )
    
    refund_amount = refund.amount or (payment.amount - payment.refunded_amount)
    
    if refund_amount > (payment.amount - payment.refunded_amount):
        raise HTTPException(
            status_code=400,
            detail=f"Refund amount exceeds remaining balance"
        )
    
    payment.refunded_amount += refund_amount
    payment.refunded_at = datetime.utcnow()
    payment.updated_at = datetime.utcnow()
    
    if payment.refunded_amount >= payment.amount:
        payment.status = PaymentStatus.REFUNDED
    else:
        payment.status = PaymentStatus.PARTIALLY_REFUNDED
    print(f"Payment {payment_id} refunded ${refund_amount}, reason: {refund.reason}")
    return payment


@app.get("/payments/{payment_id}/receipt")
def get_receipt(payment_id: str):
    """Generate receipt for a captured/refunded payment."""
    if payment_id not in payments_db:
        raise HTTPException(status_code=404, detail="Payment not found")
    
    payment = payments_db[payment_id]
    
    if payment.status not in [PaymentStatus.CAPTURED, PaymentStatus.REFUNDED, PaymentStatus.PARTIALLY_REFUNDED]:
        raise HTTPException(status_code=400, detail="Receipt only available for completed payments")
    
    return {
        "receipt_id": f"RCP-{payment.id}",
        "payment_id": payment.id,
        "order_id": payment.order_id,
        "amount": payment.amount,
        "currency": payment.currency,
        "status": payment.status,
        "payment_method": payment.payment_method,
        "card_last_four": f"****{payment.card_last_four}" if payment.card_last_four else None,
        "authorization_code": payment.authorization_code,
        "captured_at": payment.captured_at.isoformat() if payment.captured_at else None,
        "refunded_amount": payment.refunded_amount if payment.refunded_amount > 0 else None,
    }
