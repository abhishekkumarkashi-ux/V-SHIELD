"""
Twilio router compatibility alias.
Exposes router and stream handler from app.routers.twilio.
"""

from app.routers.twilio import (
    CallSessionState,
    broadcast_telemetry,
    call_states,
    get_call_state,
    handle_twilio_stream_session,
    register_dashboard_subscriber,
    router,
    unregister_dashboard_subscriber,
)

__all__ = [
    "router",
    "handle_twilio_stream_session",
    "call_states",
    "CallSessionState",
    "get_call_state",
    "broadcast_telemetry",
    "register_dashboard_subscriber",
    "unregister_dashboard_subscriber",
]
