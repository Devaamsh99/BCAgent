import requests
from msal import ConfidentialClientApplication
from dotenv import load_dotenv
import os
import difflib

load_dotenv()

def get_graph_token():
    app = ConfidentialClientApplication(
        os.getenv("CLIENT_ID"),
        authority=f"https://login.microsoftonline.com/{os.getenv('TENANT_ID')}",
        client_credential=os.getenv("CLIENT_SECRET"),
    )
    token = app.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])

    if "access_token" not in token:
        print("❌ Error acquiring token:")
        print(token)
        raise Exception("Access token missing. Check credentials and permissions.")
    
    return token["access_token"]

def get_emails_from_sender(access_token, sender_email):
    target_user = "ta-innovation@tainnovationoutlook.onmicrosoft.com"
    # ✅ Filter: only unread messages
    url = f"https://graph.microsoft.com/v1.0/users/{target_user}/messages?$top=25&$filter=isRead eq false"

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    print(f"📨 Fetching UNREAD emails from {target_user}'s inbox...")
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        print(f"❌ Failed to retrieve messages: {response.status_code}")
        print(response.json())
        return []

    messages = response.json().get("value", [])
    print(f"✅ Retrieved {len(messages)} messages.")

    filtered = []
    for msg in messages:
        from_email = msg.get("from", {}).get("emailAddress", {}).get("address", "").strip().lower()
        print(f"🔎 Checking FROM: {from_email} — SUBJECT: {msg.get('subject')}")
        
        if from_email == sender_email.strip().lower():
            filtered.append({
                "id": msg.get("id"),
                "subject": msg.get("subject", ""),
                "body": msg.get("body", {}).get("content", "")
            })

    print(f"✅ Found {len(filtered)} matching unread emails from {sender_email}")
    return filtered


from datetime import datetime, timedelta

from datetime import datetime, timedelta
import requests

from datetime import datetime, timedelta
import requests

def send_email_graph(access_token, to, subject, body):
    user_email = "ta-innovation@tainnovationoutlook.onmicrosoft.com"
    url = f"https://graph.microsoft.com/v1.0/users/{user_email}/sendMail"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    email = {
        "message": {
            "subject": subject,
            "body": {
                "contentType": "Text",
                "content": body
            },
            "toRecipients": [{"emailAddress": {"address": to}}]
        }
    }

    response = requests.post(url, headers=headers, json=email)
    if response.status_code in [202, 200]:
        print(f"📧 Sent confirmation to {to}")
    else:
        print(f"❌ Failed to send email to {to}: {response.text}")


def mark_email_as_read(access_token: str, message_id: str):
    user_email = "ta-innovation@tainnovationoutlook.onmicrosoft.com"
    url = f"https://graph.microsoft.com/v1.0/users/{user_email}/messages/{message_id}"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    payload = {"isRead": True}

    response = requests.patch(url, headers=headers, json=payload)
    if response.status_code == 200:
        print(f"📩 Marked message {message_id} as read.")
    else:
        print(f"⚠️ Failed to mark email as read ({response.status_code}): {response.text}")

def get_available_time_slots(access_token, user_email, duration_minutes=30):
    import requests

    def fetch_slots(from_utc, to_utc):
        endpoint = f"https://graph.microsoft.com/v1.0/users/{user_email}/calendar/getSchedule"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }

        body = {
            "schedules": [user_email],
            "startTime": {
                "dateTime": from_utc.isoformat(),
                "timeZone": "UTC"
            },
            "endTime": {
                "dateTime": to_utc.isoformat(),
                "timeZone": "UTC"
            },
            "availabilityViewInterval": 30
        }

        res = requests.post(endpoint, headers=headers, json=body)
        if res.status_code != 200:
            print("❌ Failed to get calendar availability:", res.text)
            return []

        schedule = res.json()["value"][0]
        availability = schedule.get("availabilityView", "")
        return [
            from_utc + timedelta(minutes=i * 30)
            for i, block in enumerate(availability)
            if block == "0"
        ]

    now_utc = datetime.utcnow().replace(minute=0, second=0, microsecond=0)
    end_utc = now_utc + timedelta(days=1)
    all_slots = fetch_slots(now_utc, end_utc)

    ideal_slots = []
    for slot in all_slots:
        slot_ist = slot + timedelta(hours=5, minutes=30)
        if (
            slot_ist.minute in [0, 30]
            and 8 <= slot_ist.hour < 17
            and slot_ist.weekday() < 5
        ):
            ideal_slots.append(slot)
        if len(ideal_slots) == 3:
            break

    if ideal_slots:
        return ideal_slots

    # No ideal slots — offer fallback
    print("\n⚠️ No ideal time slots found (8 AM – 5 PM, Mon–Fri).\nWhat would you like to do?")
    print("1. Relax business hours (7 AM – 6 PM)")
    print("2. Check tomorrow")
    print("3. Skip scheduling for now")

    choice = input("Enter your choice (1/2/3): ").strip()
    
    if choice == "1":
        relaxed_slots = []
        for slot in all_slots:
            slot_ist = slot + timedelta(hours=5, minutes=30)
            if (
                slot_ist.minute in [0, 30]
                and 7 <= slot_ist.hour < 18
                and slot_ist.weekday() < 5
            ):
                relaxed_slots.append(slot)
            if len(relaxed_slots) == 3:
                break
        return relaxed_slots

    elif choice == "2":
        # Try next day
        tomorrow_start = now_utc + timedelta(days=1)
        tomorrow_end = tomorrow_start + timedelta(days=1)
        next_day_slots = fetch_slots(tomorrow_start, tomorrow_end)

        next_day_clean = []
        for slot in next_day_slots:
            slot_ist = slot + timedelta(hours=5, minutes=30)
            if (
                slot_ist.minute in [0, 30]
                and 8 <= slot_ist.hour < 17
                and slot_ist.weekday() < 5
            ):
                next_day_clean.append(slot)
            if len(next_day_clean) == 3:
                break
        return next_day_clean

    else:
        print("⏭️ Skipping internal scheduling for now.")
        return []



    if res.status_code == 200:
        schedule = res.json()["value"][0]
        availability = schedule.get("availabilityView", "")
        for i, block in enumerate(availability):
            if block == "0":  # Free
                slot_start = now + timedelta(minutes=i * 30)
                if slot_start.minute in [0, 30]:  # Only :00 and :30 slots
                    slots.append(slot_start)
                if len(slots) == 3:
                    break
    else:
        print("❌ Failed to get calendar availability:", res.text)

    return slots


def create_calendar_event(access_token, user_email, subject, start_time, duration_minutes=30):
    url = f"https://graph.microsoft.com/v1.0/users/{user_email}/events"

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    end_time = start_time + timedelta(minutes=duration_minutes)

    data = {
        "subject": subject,
        "start": {
            "dateTime": start_time.isoformat(),
            "timeZone": "UTC"
        },
        "end": {
            "dateTime": end_time.isoformat(),
            "timeZone": "UTC"
        },
        "attendees": [
            {
                "emailAddress": {
                    "address": user_email,
                    "name": "TA Innovation"
                },
                "type": "required"
            }
        ]
    }

    res = requests.post(url, headers=headers, json=data)
    if res.status_code in [200, 201]:
        print(f"📅 Internal call scheduled at {start_time.isoformat()}")
    else:
        print("❌ Failed to create event:", res.text)

def check_existing_event(access_token, user_email, client_name) -> str | None:
    import requests
    from datetime import datetime, timedelta

    now = datetime.utcnow()
    end = now + timedelta(days=30)

    url = f"https://graph.microsoft.com/v1.0/users/{user_email}/calendarview?startdatetime={now.isoformat()}&enddatetime={end.isoformat()}"

    headers = {
        "Authorization": f"Bearer {access_token}" }

    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        print("❌ Failed to check existing events:", response.text)
        return None

    events = response.json().get("value", [])
    for event in events:
        if client_name.lower() in event.get("subject", "").lower():
            return event.get("id")  # return the event ID if found

    return None
def update_calendar_event(access_token, user_email, event_id, new_start_time, duration_minutes=30):
    import requests
    from datetime import timedelta

    url = f"https://graph.microsoft.com/v1.0/users/{user_email}/events/{event_id}"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    new_end_time = new_start_time + timedelta(minutes=duration_minutes)

    data = {
        "start": {
            "dateTime": new_start_time.isoformat(),
            "timeZone": "UTC"
        },
        "end": {
            "dateTime": new_end_time.isoformat(),
            "timeZone": "UTC"
        }
    }

    response = requests.patch(url, headers=headers, json=data)
    if response.status_code in [200, 204]:
        return True
    else:
        print("❌ Failed to update event:", response.text)
        return False

def check_existing_external_event(access_token, user_email, client_name) -> bool:
    import requests
    from datetime import datetime, timedelta

    now = datetime.utcnow()
    end = now + timedelta(days=30)

    url = f"https://graph.microsoft.com/v1.0/users/{user_email}/calendarview?startdatetime={now.isoformat()}&enddatetime={end.isoformat()}"

    headers = {
        "Authorization": f"Bearer {access_token}" }

    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        print("❌ Failed to check external events:", response.text)
        return False

    events = response.json().get("value", [])
    for event in events:
        subj = event.get("subject", "").lower()
        if "external" in subj and client_name.lower() in subj:
            return True

    return False

def check_existing_internal_event(access_token, user_email, client_name):
    url = f"https://graph.microsoft.com/v1.0/users/{user_email}/calendar/events"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        return False

    events = response.json().get("value", [])
    for event in events:
        if (
            client_name.lower() in event.get("subject", "").lower() and
            "internal" in event.get("subject", "").lower()
        ):
            return True
    return False

def delete_calendar_event(access_token, user_email, client_name, call_type, date=None):
    url = f"https://graph.microsoft.com/v1.0/users/{user_email}/calendar/events"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        return 0

    events = response.json().get("value", [])
    deleted_count = 0

    for event in events:
        subject = event.get("subject", "").lower()
        start_time = event.get("start", {}).get("dateTime", "")

        # Fuzzy match client name (word overlap)
        if client_name:
            client_words = client_name.lower().split()
            subject_words = subject.split()
            match_score = len(set(client_words) & set(subject_words)) / len(client_words)
            client_match = match_score > 0.5
        else:
            client_match = True  # Allow match if no client name specified

        # Call type logic
        if call_type.lower() == "any":
            type_match = True
        else:
            type_match = call_type.lower() in subject

        # Date logic
        if date:
            try:
                event_date = datetime.fromisoformat(start_time).date()
                target_date = datetime.strptime(date, "%Y-%m-%d").date()
                date_match = event_date == target_date
            except Exception:
                date_match = False
        else:
            date_match = True

        if client_match and type_match and date_match:
            event_id = event.get("id")
            del_url = f"https://graph.microsoft.com/v1.0/users/{user_email}/calendar/events/{event_id}"
            del_res = requests.delete(del_url, headers=headers)
            if del_res.status_code in (204, 202):
                deleted_count += 1

    return deleted_count


