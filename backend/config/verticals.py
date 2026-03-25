"""
Business Vertical Configurations
Defines persona, services, hours, SMS/email templates per business type.
Set BUSINESS_TYPE env var to activate: dental | spa | roofing | bakery | generic
"""

from typing import Dict, Any

VERTICALS: Dict[str, Dict[str, Any]] = {

    # ── DENTAL ────────────────────────────────────────────
    "dental": {
        "business_name": "Worthington Family Dental",
        "receptionist_name": "Aria",
        "voice": "Polly.Joanna",
        "tagline": "Your smile is our priority",
        "timezone": "America/New_York",
        "logo_emoji": "🦷",
        "primary_color": "#1a6b8a",
        "business_hours": {
            "monday":    {"open": "08:00", "close": "17:00"},
            "tuesday":   {"open": "08:00", "close": "17:00"},
            "wednesday": {"open": "08:00", "close": "17:00"},
            "thursday":  {"open": "08:00", "close": "17:00"},
            "friday":    {"open": "08:00", "close": "14:00"},
            "saturday":  None,
            "sunday":    None,
        },
        "greeting": (
            "Thank you for calling Worthington Family Dental. "
            "I'm Aria, your virtual assistant. "
            "I can help you schedule, reschedule, or cancel your appointment, "
            "or answer general questions. How can I help you today?"
        ),
        "after_hours_message": (
            "Our office is currently closed. "
            "We're open Monday through Thursday 8 AM to 5 PM, "
            "and Friday 8 AM to 2 PM. "
            "Please leave a message and we'll call you back."
        ),
        "services": [
            {"name": "New Patient Exam",     "duration_min": 60, "calendly_slug": "new-patient-exam"},
            {"name": "Routine Cleaning",      "duration_min": 45, "calendly_slug": "cleaning"},
            {"name": "Emergency Appointment", "duration_min": 30, "calendly_slug": "emergency"},
            {"name": "Consultation",          "duration_min": 30, "calendly_slug": "consultation"},
            {"name": "Teeth Whitening",       "duration_min": 60, "calendly_slug": "whitening"},
            {"name": "X-Ray & Exam",          "duration_min": 45, "calendly_slug": "xray-exam"},
        ],
        "intake_questions": [
            "Are you a new or existing patient?",
            "What is your date of birth?",
            "Do you have dental insurance? If so, which provider?",
            "Are you experiencing any pain or dental emergency?",
        ],
        "transfer_triggers": [
            "billing", "insurance dispute", "dental emergency", "severe pain",
            "broken tooth", "speak to dentist", "speak to doctor", "complaint",
        ],
        "faq": {
            "parking":             "Free parking is available in our lot at 6649 North High Street, Worthington.",
            "insurance":           "We accept Delta Dental, Cigna, Aetna, MetLife, United Healthcare, and Humana.",
            "cancellation_policy": "We ask for 24 hours notice. Late cancellations may incur a $50 fee.",
            "payment":             "We accept cash, all major credit cards, and CareCredit financing.",
            "location":            "6649 North High Street, Worthington, Ohio 43085.",
        },
        "sms_templates": {
            "confirmation":  "Hi {name}! Your appointment at Worthington Family Dental is confirmed for {date} at {time}. 📍 6649 N High St, Worthington OH. Reply CANCEL to cancel or call (614) 555-0191.",
            "reminder_24h":  "Hi {name}, reminder: your {service} appointment is tomorrow at {time} with Worthington Family Dental. Reply CONFIRM to confirm or CANCEL to cancel.",
            "reminder_1h":   "Hi {name}! Your dental appointment is in 1 hour at {time}. See you soon! — Worthington Family Dental",
            "cancellation":  "Hi {name}, your appointment at Worthington Family Dental on {date} has been cancelled. Call (614) 555-0191 to rebook.",
            "reschedule":    "Hi {name}, your appointment has been rescheduled to {date} at {time}. — Worthington Family Dental",
        },
        "email_templates": {
            "confirmation_subject": "Appointment Confirmed — {service} on {date}",
            "reminder_subject":     "Reminder: Your appointment is tomorrow at {time}",
            "cancellation_subject": "Appointment Cancelled — {date}",
        },
    },

    # ── SPA ───────────────────────────────────────────────
    "spa": {
        "business_name": "Serenity Spa & Wellness",
        "receptionist_name": "Luna",
        "voice": "Polly.Salli",
        "tagline": "Restore. Renew. Rejuvenate.",
        "timezone": "America/New_York",
        "logo_emoji": "🌿",
        "primary_color": "#6b4c8a",
        "business_hours": {
            "monday":    None,
            "tuesday":   {"open": "10:00", "close": "20:00"},
            "wednesday": {"open": "10:00", "close": "20:00"},
            "thursday":  {"open": "10:00", "close": "20:00"},
            "friday":    {"open": "10:00", "close": "20:00"},
            "saturday":  {"open": "09:00", "close": "18:00"},
            "sunday":    {"open": "10:00", "close": "17:00"},
        },
        "greeting": (
            "Welcome to Serenity Spa and Wellness. "
            "I'm Luna, your virtual concierge. "
            "I can help you book a treatment, check your reservation, or answer questions. "
            "How may I assist you today?"
        ),
        "after_hours_message": (
            "Our spa is currently closed. "
            "We're open Tuesday through Sunday. "
            "Please leave a message and we'll get back to you."
        ),
        "services": [
            {"name": "Swedish Massage",    "duration_min": 60,  "calendly_slug": "swedish-60"},
            {"name": "Deep Tissue Massage","duration_min": 90,  "calendly_slug": "deep-tissue-90"},
            {"name": "HydraFacial",        "duration_min": 60,  "calendly_slug": "hydrafacial"},
            {"name": "Hot Stone Massage",  "duration_min": 90,  "calendly_slug": "hot-stone"},
            {"name": "Couples Massage",    "duration_min": 60,  "calendly_slug": "couples"},
            {"name": "Prenatal Massage",   "duration_min": 60,  "calendly_slug": "prenatal"},
        ],
        "intake_questions": [
            "Is this your first visit to our spa?",
            "Do you have any medical conditions or areas of concern we should know about?",
            "Do you have a preferred therapist?",
            "Are you celebrating a special occasion?",
        ],
        "transfer_triggers": [
            "complaint", "medical concern", "speak to manager", "gift card issue", "allergy reaction",
        ],
        "faq": {
            "arrival":             "Please arrive 15 minutes early to complete intake forms and enjoy our relaxation lounge.",
            "gratuity":            "Gratuity is not included. Industry standard is 18 to 20 percent.",
            "cancellation_policy": "24-hour notice required. Same-day cancellations are charged 50 percent of the service.",
            "memberships":         "We offer monthly memberships for 20 percent off all services. Ask us for details.",
        },
        "sms_templates": {
            "confirmation": "Hi {name}! ✨ Your {service} at Serenity Spa is confirmed for {date} at {time}. Please arrive 15 min early. Reply CANCEL to cancel.",
            "reminder_24h": "Hi {name}, your relaxing {service} is tomorrow at {time}! Remember to arrive 15 min early. Reply CONFIRM or CANCEL. — Serenity Spa",
            "reminder_1h":  "Hi {name}! Your spa appointment is in 1 hour. See you soon! 🌿",
            "cancellation": "Hi {name}, your appointment at Serenity Spa on {date} has been cancelled. We hope to see you again soon!",
            "reschedule":   "Hi {name}, your appointment has been rescheduled to {date} at {time}. Looking forward to seeing you! — Serenity Spa ✨",
        },
        "email_templates": {
            "confirmation_subject": "{service} Confirmed — {date} at {time}",
            "reminder_subject":     "See you tomorrow at {time} — Serenity Spa",
            "cancellation_subject": "Appointment Cancelled — {date}",
        },
    },

    # ── ROOFING ───────────────────────────────────────────
    "roofing": {
        "business_name": "Summit Roofing & Exteriors",
        "receptionist_name": "Max",
        "voice": "Polly.Matthew",
        "tagline": "Protecting homes across Central Ohio",
        "timezone": "America/New_York",
        "logo_emoji": "🏠",
        "primary_color": "#1a3a5c",
        "business_hours": {
            "monday":    {"open": "07:00", "close": "18:00"},
            "tuesday":   {"open": "07:00", "close": "18:00"},
            "wednesday": {"open": "07:00", "close": "18:00"},
            "thursday":  {"open": "07:00", "close": "18:00"},
            "friday":    {"open": "07:00", "close": "17:00"},
            "saturday":  {"open": "08:00", "close": "14:00"},
            "sunday":    None,
        },
        "greeting": (
            "Thank you for calling Summit Roofing and Exteriors. "
            "I'm Max, your virtual assistant. "
            "I can schedule a free inspection, connect you with our team, or answer questions. "
            "What can I help you with today?"
        ),
        "after_hours_message": (
            "Our office is currently closed. "
            "We're open Monday through Saturday. "
            "For active leaks or emergencies please press 1 to leave an urgent message."
        ),
        "services": [
            {"name": "Free Roof Inspection",   "duration_min": 60, "calendly_slug": "inspection"},
            {"name": "Storm Damage Assessment", "duration_min": 90, "calendly_slug": "storm-assessment"},
            {"name": "Estimate Consultation",   "duration_min": 45, "calendly_slug": "estimate"},
            {"name": "Gutter Inspection",       "duration_min": 30, "calendly_slug": "gutter-inspection"},
            {"name": "Project Follow-up",       "duration_min": 30, "calendly_slug": "followup"},
        ],
        "intake_questions": [
            "What is the address of the property?",
            "Is this for a residential or commercial property?",
            "Are you experiencing an active leak or storm damage?",
            "How old is your current roof approximately?",
            "Are you working with your insurance company?",
        ],
        "transfer_triggers": [
            "active leak", "emergency", "insurance claim", "existing project issue",
            "billing dispute", "speak to manager",
        ],
        "faq": {
            "service_area": "We serve all of Central Ohio including Columbus, Worthington, Dublin, Westerville, and surrounding areas.",
            "insurance":    "We work directly with all major insurance companies and can assist with your claim.",
            "warranty":     "We offer a 10-year workmanship warranty on all roof installations.",
            "financing":    "We offer 0 percent financing for 18 months through our financing partners.",
        },
        "sms_templates": {
            "confirmation": "Hi {name}! Your free roof inspection with Summit Roofing is confirmed for {date} at {time}. Our inspector will call 30 min before arrival. Reply CANCEL to cancel.",
            "reminder_24h": "Hi {name}, reminder: Summit Roofing inspection is tomorrow at {time}. Please ensure roof access is available. Reply CONFIRM or CANCEL.",
            "reminder_1h":  "Hi {name}, your Summit Roofing inspector is on the way and will arrive in approximately 1 hour.",
            "cancellation": "Hi {name}, your inspection on {date} has been cancelled. Call us anytime to reschedule. — Summit Roofing",
            "reschedule":   "Hi {name}, your inspection has been rescheduled to {date} at {time}. — Summit Roofing & Exteriors",
        },
        "email_templates": {
            "confirmation_subject": "Inspection Confirmed — {date} at {time}",
            "reminder_subject":     "Reminder: Roof Inspection Tomorrow at {time}",
            "cancellation_subject": "Inspection Cancelled — {date}",
        },
    },

    # ── BAKERY ────────────────────────────────────────────
    "bakery": {
        "business_name": "Sweet Provisions Bakery",
        "receptionist_name": "Rosie",
        "voice": "Polly.Kendra",
        "tagline": "Baked fresh daily with love",
        "timezone": "America/New_York",
        "logo_emoji": "🧁",
        "primary_color": "#8b4513",
        "business_hours": {
            "monday":    None,
            "tuesday":   {"open": "07:00", "close": "18:00"},
            "wednesday": {"open": "07:00", "close": "18:00"},
            "thursday":  {"open": "07:00", "close": "18:00"},
            "friday":    {"open": "07:00", "close": "19:00"},
            "saturday":  {"open": "07:00", "close": "17:00"},
            "sunday":    {"open": "08:00", "close": "14:00"},
        },
        "greeting": (
            "Hello and welcome to Sweet Provisions Bakery! "
            "I'm Rosie, your bakery assistant. "
            "I can help you place a custom order, check on an existing order, or schedule a tasting. "
            "What can I do for you today?"
        ),
        "after_hours_message": (
            "We're currently closed. "
            "We're open Tuesday through Sunday. "
            "Leave us a message and we'll get back to you!"
        ),
        "services": [
            {"name": "Custom Cake Consultation", "duration_min": 30,  "calendly_slug": "cake-consult"},
            {"name": "Wedding Cake Tasting",      "duration_min": 60,  "calendly_slug": "wedding-tasting"},
            {"name": "Catering Order Pickup",     "duration_min": 15,  "calendly_slug": "order-pickup"},
            {"name": "Decorating Class",          "duration_min": 120, "calendly_slug": "decorating-class"},
        ],
        "intake_questions": [
            "What is the occasion?",
            "How many servings do you need?",
            "Do you have any dietary restrictions — gluten-free, vegan, or nut-free?",
            "What is the date you need the order by?",
        ],
        "transfer_triggers": [
            "complaint", "wrong order", "allergy issue", "speak to baker",
        ],
        "faq": {
            "lead_time": "Custom cakes require at least 72 hours notice. Wedding cakes require 4 weeks.",
            "pickup":    "Orders are available for pickup during business hours. We do not currently offer delivery.",
            "deposit":   "A 50 percent deposit is required for all custom orders.",
            "allergies": "Our kitchen handles tree nuts, peanuts, wheat, dairy, and eggs. We cannot guarantee allergen-free products.",
        },
        "sms_templates": {
            "confirmation": "Hi {name}! 🎂 Your {service} at Sweet Provisions is scheduled for {date} at {time}. Reply CANCEL to cancel.",
            "reminder_24h": "Hi {name}, reminder: your {service} is tomorrow at {time} at Sweet Provisions. Reply CONFIRM or CANCEL. 🧁",
            "reminder_1h":  "Hi {name}! Your appointment at Sweet Provisions is in 1 hour. See you soon! 🎂",
            "cancellation": "Hi {name}, your appointment on {date} has been cancelled. We hope to bake something special for you soon!",
            "reschedule":   "Hi {name}, your appointment has been rescheduled to {date} at {time}. — Sweet Provisions 🎂",
        },
        "email_templates": {
            "confirmation_subject": "{service} Confirmed — {date}",
            "reminder_subject":     "Reminder: Your appointment is tomorrow at {time}",
            "cancellation_subject": "Appointment Cancelled — {date}",
        },
    },

    # ── GENERIC SMB ───────────────────────────────────────
    "generic": {
        "business_name": "My Business",
        "receptionist_name": "Alex",
        "voice": "Polly.Joanna",
        "tagline": "Here to help",
        "timezone": "America/New_York",
        "logo_emoji": "📅",
        "primary_color": "#2c3e50",
        "business_hours": {
            "monday":    {"open": "09:00", "close": "17:00"},
            "tuesday":   {"open": "09:00", "close": "17:00"},
            "wednesday": {"open": "09:00", "close": "17:00"},
            "thursday":  {"open": "09:00", "close": "17:00"},
            "friday":    {"open": "09:00", "close": "17:00"},
            "saturday":  None,
            "sunday":    None,
        },
        "greeting": (
            "Thank you for calling. "
            "I'm Alex, your virtual assistant. "
            "I can help you schedule an appointment or answer questions. "
            "How can I help you today?"
        ),
        "after_hours_message": (
            "We're currently closed. "
            "Please call back during business hours or leave a message."
        ),
        "services": [
            {"name": "Consultation", "duration_min": 30, "calendly_slug": "consultation"},
            {"name": "Appointment",  "duration_min": 60, "calendly_slug": "appointment"},
            {"name": "Follow-up",    "duration_min": 30, "calendly_slug": "followup"},
        ],
        "intake_questions": [
            "Is this your first time working with us?",
            "What is the nature of your visit?",
        ],
        "transfer_triggers": [
            "emergency", "billing", "speak to human", "speak to manager", "complaint",
        ],
        "faq": {},
        "sms_templates": {
            "confirmation": "Hi {name}! Your appointment at {business_name} is confirmed for {date} at {time}. Reply CANCEL to cancel.",
            "reminder_24h": "Hi {name}, reminder: your appointment is tomorrow at {time}. Reply CONFIRM or CANCEL. — {business_name}",
            "reminder_1h":  "Hi {name}! Your appointment is in 1 hour. See you soon! — {business_name}",
            "cancellation": "Hi {name}, your appointment on {date} has been cancelled. Call us to rebook. — {business_name}",
            "reschedule":   "Hi {name}, your appointment has been rescheduled to {date} at {time}. — {business_name}",
        },
        "email_templates": {
            "confirmation_subject": "Appointment Confirmed — {date} at {time}",
            "reminder_subject":     "Reminder: Your appointment is tomorrow at {time}",
            "cancellation_subject": "Appointment Cancelled — {date}",
        },
    },
}


def get_vertical(vertical_key: str) -> Dict[str, Any]:
    """Return vertical config, falling back to generic."""
    return VERTICALS.get(vertical_key, VERTICALS["generic"])
