"""Book a session / นัดหมาย — trial (15 min, free, once per email) and paid (30 min)."""
from __future__ import annotations

import html
from datetime import datetime, timedelta

import streamlit as st

from booking import (
    BANGKOK,
    BOOKING_HORIZON_DAYS,
    BookingService,
    PAID_DURATION,
    TRIAL_DURATION,
    TrialAlreadyUsedError,
    generate_slots_for_date,
    validate_booking_form,
)
from caldav_client import is_caldav_configured
from database import db
from models import SlotUnavailableError
from payments import (
    PaymentNotVerifiedError,
    PaymentsNotEnabledError,
    is_payments_enabled,
    is_price_placeholder,
    price_label_en,
    price_label_th,
)


def _format_slot(slot_start, duration) -> str:
    end = slot_start + duration
    return f"{slot_start.strftime('%H:%M')}–{end.strftime('%H:%M')}"


def _handle_checkout_return(service: BookingService) -> None:
    """Verify Stripe payment server-side when the customer returns from Checkout."""
    params = st.query_params
    checkout = params.get("booking_checkout")
    if not checkout:
        return
    booking_id = params.get("booking_id")
    session_id = params.get("session_id")
    if checkout == "cancel":
        service.cancel_pending_hold(booking_id)
        st.session_state.booking_notice = (
            "Payment was canceled. The time hold was released. "
            "/ ยกเลิกการชำระเงินแล้ว เราได้คืนช่วงเวลานี้แล้ว"
        )
        st.query_params.clear()
        st.rerun()
    if checkout == "success":
        if not session_id or not booking_id:
            st.session_state.booking_notice = (
                "Payment return was missing details. We have not confirmed a paid session. "
                "/ ข้อมูลการชำระเงินไม่ครบ ระบบยังไม่ยืนยันนัดแบบชำระเงิน"
            )
            st.query_params.clear()
            st.rerun()
        try:
            result = service.confirm_paid_from_checkout(session_id, booking_id)
        except (PaymentNotVerifiedError, SlotUnavailableError, PaymentsNotEnabledError) as exc:
            st.session_state.booking_notice = str(exc)
            st.query_params.clear()
            st.rerun()
        else:
            st.session_state.booking_confirmation = result
            st.query_params.clear()
            st.rerun()


def show_booking_page():
    """Customer page to book a Coach trial or paid session (19:00–21:00, Asia/Bangkok)."""
    st.markdown(
        """
        <style>
        @media (max-width: 768px) {
            h1 { font-size: 1.5rem !important; }
            h2 { font-size: 1.25rem !important; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    with st.expander("📱 Quick Navigation", expanded=False):
        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("🏠 Home", key="booking_nav_home", use_container_width=True):
                st.session_state.navigation = "Home"
                st.rerun()
        with col2:
            if st.button("💡 Coach", key="booking_nav_coach", use_container_width=True):
                st.session_state.navigation = "AIHive Coach"
                st.rerun()
        with col3:
            if st.button("💬 Coaching", key="booking_nav_coaching", use_container_width=True):
                st.session_state.navigation = "Start Coaching"
                st.rerun()

    st.title("📅 Book a session / นัดหมาย")
    st.caption("AIHive Coach · 19:00–21:00 (เวลาไทย, ICT / Asia/Bangkok)")

    st.markdown(
        """
        <div class='card'>
        <p>Reserve a live coaching session with Rungnapa.
        Choose a free 15-minute trial (once per email) or a paid 30-minute session.
        คุณสามารถจองทดลองใช้ฟรี 15 นาที (อีเมลละครั้ง) หรือนัด 30 นาทีแบบชำระเงิน ได้ทุกวัน ช่วง 19:00–21:00</p>
        <p style='margin-bottom:0;color:#94a3b8;font-size:0.95rem;'>
        Other customers only see free or busy times — never your name, email, or topic.
        ลูกค้าคนอื่นเห็นได้เฉพาะช่วงว่างหรือไม่ว่าง ไม่เห็นชื่อ อีเมล หรือหัวข้อของคุณ
        </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if is_caldav_configured():
        st.info(
            "Confirmed bookings are added to the coach's calendar. "
            "ระบบจะบันทึกนัดลงปฏิทินของโค้ชเมื่อการจองได้รับการยืนยัน"
        )
    else:
        st.warning(
            "You can book a time now. It will be saved here, and **calendar sync is pending** "
            "until the coach's calendar is connected. We will not claim it was added to the calendar yet. "
            "/ คุณจองเวลาได้เลย ระบบจะบันทึกนัดไว้ก่อน การซิงค์ปฏิทินยังค้างอยู่ "
            "จนกว่าจะเชื่อมปฏิทินของโค้ช จะยังไม่ยืนยันว่าขึ้นในปฏิทินแล้ว"
        )

    service = BookingService(db)
    _handle_checkout_return(service)

    notice = st.session_state.get("booking_notice")
    if notice:
        st.warning(notice)

    checkout_pending = st.session_state.get("booking_checkout_pending")
    if checkout_pending is not None and checkout_pending.checkout_url:
        st.info(checkout_pending.message_en + " / " + checkout_pending.message_th)
        st.markdown(
            f'<meta http-equiv="refresh" content="0;url={html.escape(checkout_pending.checkout_url, quote=True)}">',
            unsafe_allow_html=True,
        )
        st.link_button(
            "Continue to Stripe Checkout (test mode) / ไปชำระเงินที่ Stripe",
            checkout_pending.checkout_url,
            type="primary",
        )
        st.caption("The session is not booked until payment is verified on return.")
        return

    today = datetime.now(BANGKOK).date()
    max_day = today + timedelta(days=BOOKING_HORIZON_DAYS)

    kind_label = st.radio(
        "Session type / ประเภทนัด",
        options=["trial", "paid"],
        format_func=lambda k: (
            "🎁 Free 15-minute trial / ทดลองใช้ฟรี 15 นาที (ครั้งเดียวต่ออีเมล)"
            if k == "trial"
            else "💳 Paid 30-minute session / นัด 30 นาที (ชำระเงิน)"
        ),
        key="booking_kind",
        horizontal=False,
    )
    duration = TRIAL_DURATION if kind_label == "trial" else PAID_DURATION

    if kind_label == "paid":
        if is_price_placeholder():
            st.info(
                f"Price: **{price_label_en()}** / **{price_label_th()}**. "
                "This is a labeled placeholder until the founder sets AIHIVE_SESSION_PRICE_THB."
            )
        else:
            st.info(f"Price: **{price_label_en()}** / **{price_label_th()}**")
        if not is_payments_enabled():
            st.error(
                "Payments are not yet enabled. A paid session cannot be confirmed. "
                "/ ยังไม่เปิดรับชำระเงิน ระบบจะไม่ยืนยันนัดแบบชำระเงิน"
            )

    name = st.text_input("Name / ชื่อ", max_chars=200, key="booking_name")
    email = st.text_input("Email / อีเมล", max_chars=254, key="booking_email")
    topic = st.text_input(
        "Topic (optional) / หัวข้อ (ไม่บังคับ)",
        max_chars=500,
        key="booking_topic",
    )
    chosen_date = st.date_input(
        "Date / วันที่",
        value=today,
        min_value=today,
        max_value=max_day,
        key="booking_date",
    )

    slots, calendar_warning = service.available_slots(chosen_date, kind=kind_label)
    if calendar_warning:
        st.warning(calendar_warning)

    if not slots:
        remaining_today = generate_slots_for_date(chosen_date, kind=kind_label)
        if not remaining_today:
            st.info(
                "No remaining times on this date. Please pick another day. "
                "/ ไม่มีช่วงเวลาเหลือในวันนี้ กรุณาเลือกวันอื่น"
            )
        else:
            st.info("No free slots on this date / ไม่มีช่วงว่างวันนี้")
        selected = None
    else:
        selected = st.radio(
            "Available times / ช่วงเวลาที่ว่าง (เวลาไทย, ICT)",
            options=slots,
            format_func=lambda s, d=duration: _format_slot(s, d),
            key=f"booking_slot_{kind_label}",
        )

    if kind_label == "trial":
        submit_label = "Book free trial / จองทดลองใช้"
        disabled = selected is None
    else:
        submit_label = "Pay and hold this time / ชำระเงินและกันเวลาไว้"
        disabled = selected is None or not is_payments_enabled()

    if st.button(submit_label, type="primary", disabled=disabled, key="booking_submit"):
        form_errors = validate_booking_form(name, email, topic)
        if form_errors:
            for err in form_errors:
                st.error(err)
        elif kind_label == "trial":
            try:
                result = service.book_trial(
                    name=name,
                    email=email,
                    topic=topic,
                    slot_start=selected,
                )
            except TrialAlreadyUsedError as exc:
                st.error(str(exc))
            except SlotUnavailableError as exc:
                st.error(str(exc))
            except ValueError as exc:
                st.error(str(exc))
            else:
                st.session_state.booking_confirmation = result
                st.session_state.booking_notice = None
                st.rerun()
        else:
            if not is_payments_enabled():
                st.error("Payments are not yet enabled / ยังไม่เปิดรับชำระเงิน")
            else:
                try:
                    result = service.start_paid_checkout(
                        name=name,
                        email=email,
                        topic=topic,
                        slot_start=selected,
                    )
                except PaymentsNotEnabledError as exc:
                    st.error(str(exc))
                except SlotUnavailableError as exc:
                    st.error(str(exc))
                except ValueError as exc:
                    st.error(str(exc))
                else:
                    st.session_state.booking_checkout_pending = result
                    st.session_state.booking_notice = None
                    st.rerun()

    result = st.session_state.get("booking_confirmation")
    if result is not None:
        booking = result.booking
        local = booking.slot_start.astimezone(BANGKOK)
        end = booking.slot_end.astimezone(BANGKOK)
        kind_name = (
            "Free 15-minute trial / ทดลองใช้ฟรี 15 นาที"
            if result.kind == "trial"
            else "Paid 30-minute session / นัด 30 นาที (ชำระแล้ว)"
        )
        st.success(result.message_en + " / " + result.message_th)
        safe_name = html.escape(booking.customer_name)
        safe_email = html.escape(booking.customer_email)
        safe_topic = html.escape(booking.topic or "—")
        st.markdown(
            f"""
            <div class='card'>
            <h3>Confirmation / ยืนยันการนัดหมาย</h3>
            <p><strong>Type / ประเภท:</strong> {kind_name}</p>
            <p><strong>Date / วันที่:</strong> {local.strftime('%A %d %B %Y')}</p>
            <p><strong>Time / เวลา:</strong> {local.strftime('%H:%M')}–{end.strftime('%H:%M')} (เวลาไทย, ICT)</p>
            <p><strong>Name / ชื่อ:</strong> {safe_name}</p>
            <p><strong>Email / อีเมล:</strong> {safe_email}</p>
            <p><strong>Topic / หัวข้อ:</strong> {safe_topic}</p>
            <p style='margin-bottom:0;color:#94a3b8;'>
            Status: {'Added to the coach calendar' if result.calendar_synced else 'Saved locally · calendar sync pending / บันทึกแล้ว · การซิงค์ปฏิทินยังค้างอยู่'}
            </p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button("Book another time / จองเวลาอื่น", key="booking_another"):
            st.session_state.booking_confirmation = None
            st.session_state.booking_notice = None
            st.rerun()
