import os
import json
import re
from datetime import timedelta
from dotenv import load_dotenv
import email_utils
from db_utils import init_db, log_meeting
from openai import AzureOpenAI
from datetime import timedelta
import dateparser
from email_utils import (
    get_graph_token,
    get_emails_from_sender,
    get_available_time_slots,
    create_calendar_event,
    update_calendar_event,
    check_existing_event,
    mark_email_as_read
)
from db_utils import log_meeting
from email_utils import check_existing_external_event
from db_utils import query_meetings, query_meetings_advanced
from email_utils import send_email_graph
load_dotenv()
init_db()


client = AzureOpenAI(
    api_key=os.getenv("AZURE_API_KEY"),
    api_version="2024-02-01",
    azure_endpoint=os.getenv("AZURE_ENDPOINT")
)



def extract_client_name(user_input: str) -> str | None:
    prompt = f"""
You are a helpful assistant. Extract the client name if the user is asking to schedule a meeting.

Input: "{user_input}"

If the input contains a company/client name, respond only with the name, like:
"Viridian Corp"

If no company is mentioned, respond with: "none"
"""

    response = client.chat.completions.create(
        model=os.getenv("DEPLOYMENT_NAME"),
        messages=[
            {"role": "system", "content": "Extract the client name or return 'none'."},
            {"role": "user", "content": prompt}
        ],
        temperature=0
    )

    result = response.choices[0].message.content.strip()
    return result if result.lower() != "none" else None

def extract_info_with_gpt(email_body: str, debug: bool = True) -> dict:
    """Extract client_name, client_address, and subject_name from scheduling emails using GPT with fallbacks."""
    import re, json, os
    from openai import AzureOpenAI

    client = AzureOpenAI(
        api_key=os.getenv("AZURE_API_KEY"),
        api_version="2024-02-01",
        azure_endpoint=os.getenv("AZURE_ENDPOINT")
    )

    # 🧹 Clean email body
    email_body = re.sub(r"<mailto:[^>]+>", "", email_body)
    email_body = re.sub(r"\s{2,}", " ", email_body).strip()

    
        

    prompt = f"""
You are an assistant that extracts scheduling information from emails.

Return ONLY a JSON object with:
{{
  "client_name": "string or null",
  "client_address": "email or null",
  "subject_name": "short readable title or null"
}}

If unsure, return null for missing fields. Do not add any explanation.

--- Example ---
Email:
Kindly schedule a strategy meeting for Hewlet Tech next week.
Their email is: hewlettech@outlook.com

Response:
{{
  "client_name": "Hewlet Tech",
  "client_address": "hewlettech@outlook.com",
  "subject_name": "Strategy Meeting"
}}

Now extract info from this email:
\"\"\"{email_body}\"\"\"
"""

    try:
        response = client.chat.completions.create(
            model=os.getenv("DEPLOYMENT_NAME"),
            messages=[
                {"role": "system", "content": "You extract client details from scheduling emails."},
                {"role": "user", "content": prompt}
            ],
            temperature=0
        )

        content = response.choices[0].message.content.strip()
        if content.startswith("```"):
            content = re.sub(r"```(?:json)?", "", content).replace("```", "").strip()

        if not content:
            raise ValueError("Empty GPT response")

        parsed = json.loads(content)

        # 🧠 Fallback for client_name
        client_name = parsed.get("client_name")
        if not client_name:
            match = re.search(
                r"(?:Client(?: name)?\s*[:=]\s*|schedule(?: a)?(?: strategy)?(?: meeting)? for\s*)([A-Z][\w\s&.]+)",
                email_body, re.IGNORECASE)
            if match:
                client_name = match.group(1).strip()

        # 📧 Fallback for email
        client_address = parsed.get("client_address")
        if not client_address:
            match = re.search(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", email_body)
            if match:
                client_address = match.group(0).strip()

        # 🏷️ Fallback subject
        subject_name = parsed.get("subject_name") or "Client Briefing Call"
        if debug:
          print("📨 Final extracted info:", {
                 "client_name": client_name,
                  "client_address": client_address,
                   "subject_name": subject_name
            })
        return {
            "client_name": client_name,
            "client_address": client_address,
            "subject_name": subject_name
        }

    except Exception as e:
        print("❌ Error parsing email with GPT:", e)
        return {
            "client_name": None,
            "client_address": None,
            "subject_name": None
        }


    
def classify_intent(user_input: str) -> str:
    """Use GPT to determine if input is about scheduling."""
    prompt = f"""
You are a helpful assistant. Classify the following input as either:

- "scheduling" → if the user is talking about scheduling meetings, coordinating calls, or briefing sessions
- "general" → if the user is asking anything else

Input: "{user_input}"
Respond ONLY with: scheduling or general
"""

    response = client.chat.completions.create(
        model=os.getenv("DEPLOYMENT_NAME"),
        messages=[
            {"role": "system", "content": "Classify user input as 'scheduling' or 'general'."},
            {"role": "user", "content": prompt}
        ],
        temperature=0
    )

    return response.choices[0].message.content.strip().lower()


def run_scheduler_flow(force_client: str = None):
    token = get_graph_token()
    sender_email = os.getenv("SENDER_EMAIL")
    user_email = "ta-innovation@tainnovationoutlook.onmicrosoft.com"

    if force_client:
        extracted = {
            "client_name": force_client,
            "client_address": "client@example.com",
            "subject_name": f"Briefing Session with {force_client}"
        }
        parsed_emails = [extracted]
    else:
        raw_emails = get_emails_from_sender(token, sender_email)

        if not raw_emails:
            print("📭 No scheduling emails found.")
            return

        parsed_emails = []
        for mail in raw_emails:
            
            extracted = extract_info_with_gpt(mail["body"])

            if not extracted or not extracted.get("client_name"):
                print("❌ Could not extract client name. Skipping.")
                continue

            mark_email_as_read(token, mail["id"])
            print("📩 Marked email as read.")
            parsed_emails.append(extracted)

    if not parsed_emails:
        print("📭 No valid scheduling emails found after parsing.")
        return

    for extracted in parsed_emails:
        client_name = extracted["client_name"]
        subject = f"Internal Strategy Briefing for {client_name}"

        print(f"\n📄 Parsed Client Request:")
        print(f"Subject Title: {extracted['subject_name']}")
        print(f"Client Name : {client_name}")
        print(f"Client Email: {extracted['client_address']}")

        # 🔍 Check for existing event
        event_id = check_existing_event(token, user_email, client_name)

        if event_id:
            print(f"⏭️  Skipping {client_name} — event already exists.")
            continue

        # ✅ Internal Call Flow
        slots = get_available_time_slots(token, user_email)
        if not slots:
            print("❌ No available internal slots.")
            continue

        print("\nAvailable internal call slots (IST):")
        for i, slot_utc in enumerate(slots):
            slot_ist = slot_utc + timedelta(hours=5, minutes=30)
            print(f"{i + 1}. {slot_ist.strftime('%Y-%m-%d %H:%M')} IST")

        try:
            choice = int(input("\nChoose a slot number for internal call: ")) - 1
            selected_slot = slots[choice]
            slot_ist = selected_slot + timedelta(hours=5, minutes=30)

            # ✅ Create Internal Event
            create_calendar_event(token, user_email, subject, selected_slot)

            # ✅ Log internal to DB
            log_meeting(
                client_name=client_name,
                subject=subject,
                meeting_time_ist=slot_ist.strftime("%Y-%m-%d %H:%M"),
                meeting_time_utc=selected_slot.strftime("%Y-%m-%d %H:%M"),
                call_type="internal"
            )

            print(f"✅ Internal call scheduled at {slot_ist.strftime('%Y-%m-%d %H:%M')} IST")
            from email_utils import send_email_graph
            send_email_graph(
                token,
                user_email,
                f"Confirmed: {subject}",
                f"Dear TA,\n\nThe internal call with {client_name} has been scheduled on {slot_ist.strftime('%Y-%m-%d %H:%M')} IST.\n\nSubject: {subject}"
            )
            # 📞 Schedule External Call
            schedule_external_call(token, user_email, client_name, extracted.get("client_address"))

        except (IndexError, ValueError):
            print("❌ Invalid selection. Skipping this client.")


def resolve_natural_date(text: str) -> str | None:
    parsed_date = dateparser.parse(text, settings={"PREFER_DATES_FROM": "future"})
    if parsed_date:
        return parsed_date.strftime("%Y-%m-%d")
    return None

def parse_user_intent(user_input: str) -> dict:
    prompt = f"""
You are a smart assistant that helps with scheduling internal and external calls, as well as answering casual questions.

Your job is to extract the following:
- intent: "schedule", "query", "delete", or "chat"
- client_name: mentioned company or client, or null
- call_type: "internal", "external", or "any"
- date_text: natural language like "tomorrow", "Friday", or "next week" (or null)

Respond ONLY with JSON.

--- Examples ---

Input:
"when is my meeting with Blue Energy"

Response:
{{ "intent": "query", "client_name": "Blue Energy", "call_type": "any", "date_text": null }}

Input:
"schedule external call with AceVentura Corp"

Response:
{{ "intent": "schedule", "client_name": "AceVentura Corp", "call_type": "external", "date_text": null }}

Input:
"delete my internal meeting with Alpha Nova"

Response:
{{ "intent": "delete", "client_name": "Alpha Nova", "call_type": "internal", "date_text": null }}

Input:
"tell me a joke"

Response:
{{ "intent": "chat", "client_name": null, "call_type": "any", "date_text": null }}

Input:
"hi"

Response:
{{ "intent": "chat", "client_name": null, "call_type": "any", "date_text": null }}

--- Now extract from below ---

Input:
\"\"\"{user_input}\"\"\"
"""

    try:
        response = client.chat.completions.create(
            model=os.getenv("DEPLOYMENT_NAME"),
            messages=[
                {"role": "system", "content": "Extract user scheduling intent in structured JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0
        )

        raw = response.choices[0].message.content.strip()
        if raw.startswith("```"):
            raw = re.sub(r"```(?:json)?", "", raw).replace("```", "").strip()
        parsed = json.loads(raw)

        resolved_date = resolve_natural_date(parsed.get("date_text") or "")
        parsed["date"] = resolved_date
        return parsed

    except Exception as e:
        print("❌ Failed to parse intent JSON:", e)
        print("🔍 Raw response from LLM:\n", response.choices[0].message.content if 'response' in locals() else "No response")
        return {
            "intent": "chat",
            "client_name": None,
            "call_type": "any",
            "date": None
        }

def reschedule_meeting(client_name: str, call_type: str = "any") -> str:
    token = get_graph_token()
    user_email = "ta-innovation@tainnovationoutlook.onmicrosoft.com"

    # Use internal or external identifier
    check_func = check_existing_event if call_type == "internal" else check_existing_external_event
    event_id = check_func(token, user_email, client_name)

    if not event_id:
        return f"❌ No {call_type} meeting found for {client_name}."

    slots = get_available_time_slots(token, user_email)
    if not slots:
        return "❌ No available slots to reschedule."

    print("\n🕒 Available slots for rescheduling (IST):")
    for i, slot_utc in enumerate(slots):
        slot_ist = slot_utc + timedelta(hours=5, minutes=30)
        print(f"{i + 1}. {slot_ist.strftime('%Y-%m-%d %H:%M')} IST")

    try:
        choice = int(input("\nChoose a new slot number: ")) - 1
        selected_slot = slots[choice]
        slot_ist = selected_slot + timedelta(hours=5, minutes=30)

        if update_calendar_event(token, user_email, event_id, selected_slot):
            return f"✅ Rescheduled to {slot_ist.strftime('%Y-%m-%d %H:%M')} IST"
        else:
            return "❌ Failed to update calendar event."

    except (IndexError, ValueError):
        return "❌ Invalid selection."



def schedule_external_call(token, user_email, client_name, client_address=None):
    print("\n📞 Now scheduling the external client call...\n")

    if check_existing_external_event(token, user_email, client_name):
        print(f"⚠️ An external call already exists for {client_name}. Skipping duplicate.")
        return

    slots = get_available_time_slots(token, user_email)

    if not slots:
        print("❌ No available slots for external call.")
        return

    print("Available external call slots (IST):")
    for i, slot_utc in enumerate(slots):
        slot_ist = slot_utc + timedelta(hours=5, minutes=30)
        print(f"{i + 1}. {slot_ist.strftime('%Y-%m-%d %H:%M')} IST")

    try:
        choice = int(input("\nChoose a slot number for the external call: ")) - 1
        selected_slot = slots[choice]
        slot_ist = selected_slot + timedelta(hours=5, minutes=30)

        subject = f"External Briefing Call – {client_name}"
        create_calendar_event(token, user_email, subject, selected_slot)

        
        log_meeting(
            client_name=client_name,
            subject=subject,
            meeting_time_ist=slot_ist.strftime("%Y-%m-%d %H:%M"),
            meeting_time_utc=selected_slot.strftime("%Y-%m-%d %H:%M"),
            call_type="external"
        )


        print(f"✅ External call scheduled at {slot_ist.strftime('%Y-%m-%d %H:%M')} IST")
        # 📨 Confirmation to TA
        send_email_graph(
            token,
            user_email,
            f"Confirmed: {subject}",
            f"Dear TA,\n\nThe external call with {client_name} has been scheduled on {slot_ist.strftime('%Y-%m-%d %H:%M')} IST.\n\nSubject: {subject}"
        )

         # 📨 Confirmation to Client (if available)
        
        if client_address:
          send_email_graph(
              token,
              client_address,
              "Your Briefing Call is Confirmed",
              f"Dear {client_name},\n\nYour briefing call with TA Innovation is scheduled for {slot_ist.strftime('%Y-%m-%d %H:%M')} IST.\n\nLooking forward to speaking with you.\n\nBest,\nTA Innovation"
        ) 

    except (IndexError, ValueError):
        print("❌ Invalid selection for external call. Skipping.")

def is_query_intent(user_input: str) -> bool:
    prompt = f"""
Classify this input as either:
- "query" if the user wants to view scheduled meetings or logs
- "other" otherwise

Input: "{user_input}"

Respond with just: query or other
"""
    response = client.chat.completions.create(
        model=os.getenv("DEPLOYMENT_NAME"),
        messages=[
            {"role": "system", "content": "Classify user input intent."},
            {"role": "user", "content": prompt}
        ],
        temperature=0
    )
    return response.choices[0].message.content.strip().lower() == "query"


def main():
    print("🤖 Briefing Assistant is ready. Type 'exit' to quit.\n")
    while True:
        user_input = input("You: ").strip()
        if user_input.lower() in {"exit", "quit"}:
            print("👋 Goodbye!")
            break

        parsed = parse_user_intent(user_input)
        intent = parsed.get("intent")

        if intent == "query":
            results = query_meetings_advanced(
                client=parsed.get("client_name"),
                call_type=parsed.get("call_type"),
                date=parsed.get("date")
            )
            if not results:
                print("📭 No matching meetings found.")
            else:
                for r in results:
                    print(f"📌 {r[1]} ({r[4]})")
                    print(f"    🧑 {r[0]}")
                    print(f"    🕒 {r[2]} IST\n")

        elif intent == "schedule":
            run_scheduler_flow(force_client=parsed.get("client_name"))

        else:
            # General assistant fallback
            response = client.chat.completions.create(
                model=os.getenv("DEPLOYMENT_NAME"),
                messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": user_input}
                ],
                temperature=0.7
            )
            print("\n🤖", response.choices[0].message.content.strip())

if __name__ == "__main__":
    main()
