"""Stripe Checkout helpers for paid Coach and Tutor sessions.

Test mode only unless AIHIVE_PAYMENTS_LIVE=true. The secret key is read
from the environment when needed and is never stored on Config, logged,
or included in exceptions.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Optional


DEFAULT_PLACEHOLDER_PRICE_THB = 1500
HOLD_MINUTES = 15
# Stripe charges THB in satang (two decimal places).
THB_ZERO_DECIMAL = False


class PaymentsNotEnabledError(Exception):
    """Paid booking cannot start because Stripe is not configured (or live keys are blocked)."""


class LiveStripeKeyRefused(Exception):
    """A live Stripe secret key was provided but live payments are not approved."""


class PaymentNotVerifiedError(Exception):
    """Checkout returned but payment was not verified server-side."""


def get_stripe_secret_key() -> Optional[str]:
    value = os.getenv("STRIPE_SECRET_KEY")
    if value is None:
        return None
    value = value.strip()
    return value or None


def payments_live_allowed() -> bool:
    return os.getenv("AIHIVE_PAYMENTS_LIVE", "").strip().lower() == "true"


def redact_payment_secrets(text: str) -> str:
    if text is None:
        return ""
    out = str(text)
    key = get_stripe_secret_key()
    if key:
        out = out.replace(key, "***")
    out = re.sub(r"sk_(?:test|live)_[A-Za-z0-9]+", "sk_***", out)
    return out


def _classify_key(key: Optional[str]) -> str:
    if not key:
        return "missing"
    if key.startswith("sk_test_"):
        return "test"
    if key.startswith("sk_live_"):
        return "live"
    return "invalid"


def is_payments_enabled() -> bool:
    """True only when a usable key is present. Live keys stay disabled without approval."""
    kind = _classify_key(get_stripe_secret_key())
    if kind == "test":
        return True
    if kind == "live" and payments_live_allowed():
        return True
    return False


def require_usable_stripe_key() -> str:
    key = get_stripe_secret_key()
    kind = _classify_key(key)
    if kind == "missing" or kind == "invalid":
        raise PaymentsNotEnabledError(
            "Payments are not yet enabled / ยังไม่เปิดรับชำระเงิน"
        )
    if kind == "live" and not payments_live_allowed():
        raise LiveStripeKeyRefused(
            "Live Stripe keys are disabled unless AIHIVE_PAYMENTS_LIVE=true"
        )
    return key  # type: ignore[return-value]


def is_price_placeholder() -> bool:
    return not (os.getenv("AIHIVE_SESSION_PRICE_THB") or "").strip()


def get_session_price_thb() -> int:
    raw = (os.getenv("AIHIVE_SESSION_PRICE_THB") or "").strip()
    if not raw:
        return DEFAULT_PLACEHOLDER_PRICE_THB
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError("AIHIVE_SESSION_PRICE_THB must be a whole number of baht") from exc
    if value < 10:
        raise ValueError("AIHIVE_SESSION_PRICE_THB is too small for a Stripe charge")
    return value


def amount_to_stripe_units(baht: int) -> int:
    """Convert baht to Stripe unit_amount (satang)."""
    return int(baht) * 100


def get_public_return_url() -> Optional[str]:
    for key in ("AIHIVE_PUBLIC_URL", "RENDER_EXTERNAL_URL"):
        value = (os.getenv(key) or "").strip().rstrip("/")
        if value:
            return value
    env = (os.getenv("APP_ENV") or "development").lower()
    if env in {"development", "dev", "test", "local"}:
        port = (os.getenv("AIHIVE_LOCAL_PORT") or os.getenv("PORT") or "8501").strip()
        return f"http://localhost:{port}"
    return None


def price_label_en() -> str:
    amount = get_session_price_thb()
    if is_price_placeholder():
        return (
            f"THB {amount:,} (placeholder — price not yet decided)"
        )
    return f"THB {amount:,}"


def price_label_th() -> str:
    amount = get_session_price_thb()
    if is_price_placeholder():
        return f"THB {amount:,} (ราคาตัวอย่าง ยังไม่ได้กำหนดจริง)"
    return f"THB {amount:,}"


@dataclass
class CheckoutSessionInfo:
    id: str
    url: Optional[str]
    payment_status: str
    status: str
    metadata: dict
    amount_total: Optional[int] = None
    currency: Optional[str] = None
    payment_intent: Optional[str] = None


class StripeCheckoutClient:
    """Thin wrapper so tests can inject a fake client."""

    def create_session(
        self,
        *,
        booking_id: str,
        customer_email: str,
        customer_name: str,
        success_url: str,
        cancel_url: str,
        price_thb: int,
        placeholder: bool,
        service_type: str = "coach",
    ) -> CheckoutSessionInfo:
        key = require_usable_stripe_key()
        label = "Tutor" if (service_type or "coach").strip().lower() == "tutor" else "Coach"
        product_name = f"AIHive {label} session (30 minutes)"
        description = f"Live {label.lower()} session with Rungnapa Mukdasanit"
        if placeholder:
            description = (
                "Placeholder price — not yet decided. "
                f"AIHive {label} 30-minute session."
            )
        try:
            import stripe

            session = stripe.checkout.Session.create(
                api_key=key,
                mode="payment",
                success_url=success_url,
                cancel_url=cancel_url,
                customer_email=customer_email,
                client_reference_id=booking_id,
                metadata={
                    "booking_id": booking_id,
                    "session_kind": "paid",
                    "service_type": "tutor" if (service_type or "coach").strip().lower() == "tutor" else "coach",
                },
                expires_at=None,  # Stripe minimum is 30 minutes; we enforce a 15-min hold ourselves
                line_items=[
                    {
                        "quantity": 1,
                        "price_data": {
                            "currency": "thb",
                            "unit_amount": amount_to_stripe_units(price_thb),
                            "product_data": {
                                "name": product_name,
                                "description": description,
                            },
                        },
                    }
                ],
            )
        except (PaymentsNotEnabledError, LiveStripeKeyRefused):
            raise
        except Exception as exc:
            raise PaymentsNotEnabledError(
                f"Could not start Checkout ({type(exc).__name__})"
            ) from None
        return _info_from_stripe(session)

    def retrieve_session(self, session_id: str) -> CheckoutSessionInfo:
        key = require_usable_stripe_key()
        if not session_id or not str(session_id).startswith("cs_"):
            raise PaymentNotVerifiedError("Missing or invalid Checkout Session id")
        try:
            import stripe

            session = stripe.checkout.Session.retrieve(session_id, api_key=key)
        except PaymentNotVerifiedError:
            raise
        except Exception as exc:
            raise PaymentNotVerifiedError(
                f"Could not verify payment ({type(exc).__name__})"
            ) from None
        return _info_from_stripe(session)


def _info_from_stripe(session) -> CheckoutSessionInfo:
    metadata = dict(getattr(session, "metadata", None) or {})
    url = getattr(session, "url", None)
    payment_intent = getattr(session, "payment_intent", None)
    if payment_intent is not None and not isinstance(payment_intent, str):
        payment_intent = getattr(payment_intent, "id", str(payment_intent))
    return CheckoutSessionInfo(
        id=str(session.id),
        url=url,
        payment_status=str(getattr(session, "payment_status", "") or ""),
        status=str(getattr(session, "status", "") or ""),
        metadata=metadata,
        amount_total=getattr(session, "amount_total", None),
        currency=getattr(session, "currency", None),
        payment_intent=str(payment_intent) if payment_intent else None,
    )


def payment_is_verified(info: CheckoutSessionInfo, booking_id: str, expected_thb: int) -> bool:
    """Server-side check only. Query-string flags are never enough."""
    if info.payment_status != "paid":
        return False
    if info.status and info.status != "complete":
        return False
    meta_id = (info.metadata or {}).get("booking_id")
    if meta_id and meta_id != booking_id:
        return False
    if info.amount_total is not None and info.amount_total != amount_to_stripe_units(expected_thb):
        return False
    if info.currency and str(info.currency).lower() != "thb":
        return False
    return True
