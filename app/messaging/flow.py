"""Declarative definition of the scripted guest-onboarding flow.

Each GuestFlowState maps to one FlowStep: the question asked, and the set
of recognized answers (FlowOption) branching to the next state. Adding a
step means adding a FLOW entry and a GuestFlowState value — not touching
branching code in app/messaging/inbound.py, which just walks this
structure generically (matches a reply -> records data -> moves to
next_state or ends).

Matching is substring-based ("in", not exact match) on free text — a real
WhatsApp Business Profile would send these as templates with Quick Reply
buttons instead (structured button-tap responses, no text matching, no
"מוכן"-contains-"כן" ambiguity), but that requires an approved Business
Profile + Meta template review, which the Twilio Sandbox we're testing
against doesn't support at all.
TODO(next phase, once on a real WhatsApp Business Profile): send these
steps as approved templates with Quick Reply buttons via Twilio's Content
API (ContentSid), and parse inbound button-payload fields instead of Body
text — replaces this substring-matching approach entirely.
"""

from dataclasses import dataclass, field

from app.models.guest_session import GuestFlowState, TripType

HELP_QUESTION = "תרצה שאעזור לך לתכנן את החופשה והביקור? (כן/לא)"
TRIP_TYPE_QUESTION = "האם זו חופשה או נסיעה עסקית?"
DECLINE_ACK = "בסדר, אני כאן אם תרצה לשאול משהו בהמשך."
TRIP_TYPE_ACK = "מעולה, אשמח לעזור! במה אוכל לסייע?"


@dataclass(frozen=True)
class FlowOption:
    """One recognized answer to a FlowStep's question."""

    matches: tuple[str, ...]
    next_state: GuestFlowState | None  # None = flow ends here
    ack: str | None = None  # sent in addition to/instead of the next question
    record: dict[str, object] = field(default_factory=dict)  # GuestSession attrs to set


@dataclass(frozen=True)
class FlowStep:
    question: str
    options: tuple[FlowOption, ...]
    unrecognized_reply: str


FLOW: dict[GuestFlowState, FlowStep] = {
    GuestFlowState.awaiting_help_confirmation: FlowStep(
        question=HELP_QUESTION,
        options=(
            FlowOption(matches=("כן",), next_state=GuestFlowState.awaiting_trip_type),
            FlowOption(matches=("לא",), next_state=None, ack=DECLINE_ACK),
        ),
        unrecognized_reply="לא הבנתי, אפשר לענות כן או לא?",
    ),
    GuestFlowState.awaiting_trip_type: FlowStep(
        question=TRIP_TYPE_QUESTION,
        options=(
            FlowOption(
                matches=("עסק",),
                next_state=None,
                ack=TRIP_TYPE_ACK,
                record={"trip_type": TripType.business},
            ),
            FlowOption(
                matches=("חופש", "נסיע", "טיול"),
                next_state=None,
                ack=TRIP_TYPE_ACK,
                record={"trip_type": TripType.vacation},
            ),
        ),
        unrecognized_reply="אפשר לענות: חופשה או נסיעה עסקית?",
    ),
}
