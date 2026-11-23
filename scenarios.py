"""Three worked examples of how OTHER agents in the enterprise would use this caller. All organizations, people and
details are fictional. Each shows the shape: a short purpose, an organization, optional per-call steps, and the facts the
voice agent may state. `sensitive_phrases` are the details that must never be spoken to a wrong person or left on a voicemail."""
from __future__ import annotations

from .request import CallRequest

SCENARIOS = ("doctor", "course", "vacation")


def build(name: str, contact_id: str, first_name: str = "there", requested_by: str = "") -> CallRequest:
    if name == "doctor":
        return CallRequest(
            contact_id=contact_id, requested_by=requested_by or "scheduling-agent",
            purpose="confirm an upcoming doctor's appointment",
            organization="Example Family Clinic",
            script=("Ask whether the appointment time still works. If the person cannot make it, say a team member will "
                    "call to reschedule. Do not give medical advice and do not discuss the reason for the visit."),
            facts=(f"The contact's first name is {first_name}. Appointment with Dr. Rivera on Tuesday at 2:30 PM at "
                   "Example Family Clinic, 14 Elm Street. Please arrive 10 minutes early and bring a photo ID."),
            sensitive_phrases=("Dr. Rivera", "2:30", "Elm Street", "photo ID", "appointment"))
    if name == "course":
        return CallRequest(
            contact_id=contact_id, requested_by=requested_by or "admissions-agent",
            purpose="tell the person about a short AI training course",
            organization="Example Training Institute",
            script=("Say it is a 6-week evening course. Ask if they would like a team member to send details. "
                    "Do not quote prices or promise jobs, salaries or any career outcome."),
            facts=(f"The contact's first name is {first_name}. The Applied AI Basics course runs 6 weeks, two evenings "
                   "a week, online. The next class starts on the first Monday of next month. Registration is free to start."),
            sensitive_phrases=("Applied AI Basics", "6 weeks", "first Monday", "registration"))
    if name == "vacation":
        return CallRequest(
            contact_id=contact_id, requested_by=requested_by or "travel-offers-agent",
            purpose="share vacation destination offers",
            organization="Example Travel Co",
            script=("Mention the three destinations once and ask which sounds most interesting. Do not state prices, "
                    "dates or availability; say a team member will follow up with those."),
            facts=(f"The contact's first name is {first_name}. Current featured destinations are Lisbon, Banff and Kyoto. "
                   "Offers are for travel in the spring season."),
            sensitive_phrases=("Lisbon", "Banff", "Kyoto"))
    raise ValueError(f"unknown scenario {name!r}; choose one of {', '.join(SCENARIOS)}")
