#  Briefing Coordinator Assistant

##  Overview

This is a command-line assistant that automates client briefing call scheduling through Microsoft Outlook by parsing emails using Azure OpenAI and booking meetings using Microsoft Graph API.

It supports:
- Scheduling internal and external calls
- Meeting querying and deletion
- GPT-powered email parsing
- Confirmation emails to clients and TA
- CLI chat-style interaction

---

##  Features

| Category       | Feature                                                                 |
|----------------|-------------------------------------------------------------------------|
|  Email Intake | Fetch unread emails, extract client info via GPT                        |
|  Scheduling   | Schedule internal + external calls with available time slot detection   |
|  Deletion     | Delete scheduled meetings by client/date/type                           |
|  GPT Agent    | Intent parsing, date recognition (`"tomorrow"`, `"Friday"`, etc.)       |
|  Confirmations| Sends confirmation emails to TA and client                              |
|  Logging      | Logs all meetings in SQLite (`schedule_log`)                            |
| CLI Chat     | Uses `rich` to provide chat-like interaction                            |

---

##  Technologies Used

- LangChain (Agent/Tool system)
- Azure OpenAI (GPT-4)
- Microsoft Graph API
- Rich (CLI interface)
- SQLite (meeting database)

---

##  Folder Structure

```
📁/
├── agent_scheduler_graph.py      # Scheduling logic, GPT extraction, Graph calls
├── email_utils.py                # Email + calendar utility functions
├── db_utils.py                   # SQLite logic
├── langchain_agent.py            # LangChain agent setup with tools and CLI
├── .env                          # API keys and config
└── schedule_log.db               # Database of meetings
```

---

## Setup Instructions

1. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Set your `.env`**
   ```env
   AZURE_API_KEY=...
   AZURE_ENDPOINT=https://<your-resource>.openai.azure.com
   DEPLOYMENT_NAME=gpt-4
   SENDER_EMAIL=devaamshastro@gmail.com
   ```

3. **Run the CLI agent**
   ```bash
   python langchain_agent.py
   ```

---

##  Supported Prompts

- `schedule my meetings`
- `when is my meeting with Hewlet Tech?`
- `delete my internal call with Alpha Nova`
- `reschedule meeting with Viridian`
- `show all meetings tomorrow`
- `tell me a joke`

---

##  System Architecture Diagram (Text)

```
                   +-----------------------+
                   |   Unread Email Inbox  |
                   +-----------------------+
                             |
                             v
          +----------------------------+
          |  GPT via Azure OpenAI      |  ← extract client name, email, subject
          |  (extract_info_with_gpt)   |
          +----------------------------+
                             |
                             v
                   +------------------+
                   | SQLite DB (Log)  |
                   +------------------+
                             |
                             v
  +-------------------+     GPT intent parser     +--------------------+
  | CLI via LangChain | ────────────────────────▶ | Parse intent, date |
  +-------------------+                           +--------------------+
                             |
             ┌──────────────┼──────────────┐
             ▼              ▼              ▼
   [QueryMeetings]   [ScheduleMeetings]   [DeleteMeetings]
                             |
                  ┌──────────┴───────────┐
                  ▼                      ▼
     +-----------------------+     +---------------------+
     | Microsoft Graph API   |     | Calendar Availability|
     | (create/update/delete)|     |  (free slot fetch)   |
     +-----------------------+     +---------------------+
                             |
                             v
              +------------------------------+
              | Send confirmation emails     |
              | via Graph API (TA + Client)  |
              +------------------------------+
```
