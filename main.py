import os
from dotenv import load_dotenv
from langchain.agents import initialize_agent, AgentType, Tool
from langchain_community.chat_models import AzureChatOpenAI
import warnings
from langchain_core._api.deprecation import LangChainDeprecationWarning
warnings.filterwarnings("ignore", category=LangChainDeprecationWarning)
warnings.filterwarnings("ignore", message=".*expected to be of the form.*")
from agent_scheduler_graph import (
    run_scheduler_flow,
    query_meetings_advanced,
    parse_user_intent,
    schedule_external_call,
    reschedule_meeting,
)
from db_utils import delete_meeting

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich import box

load_dotenv()


llm = AzureChatOpenAI(
    deployment_name=os.getenv("DEPLOYMENT_NAME"),
    openai_api_key=os.getenv("AZURE_API_KEY"),
    openai_api_version="2024-02-01",
    azure_endpoint=os.getenv("AZURE_ENDPOINT"),
    temperature=0
)


def schedule_meetings_tool(_: str) -> str:
    run_scheduler_flow()
    return "✅ Checked unread emails and scheduled available meetings."


def query_meetings_tool(input_text: str) -> str:
    intent = parse_user_intent(input_text)
    print("🔍 Parsed intent:", intent)
    results = query_meetings_advanced(
        client=intent.get("client_name"),
        call_type=intent.get("call_type"),
        date=intent.get("date")
    )
    if not results:
        return "📭 No meetings found."
    return "\n\n".join([
        f"📌 {row['subject']} ({row['call_type']})\n🧑 {row['client_name']}\n🕒 {row['meeting_time_ist']} IST"
        for row in results
    ])

def delete_meeting_tool(input_text: str) -> str:
    intent = parse_user_intent(input_text)
    client = intent.get("client_name")
    call_type = intent.get("call_type", "any")
    date = intent.get("date")

    if not client and not date:
      return "⚠️ Please specify either a client name or a date to delete meetings."

    
    from email_utils import get_graph_token, delete_calendar_event
    token = get_graph_token()
    user_email = "ta-innovation@tainnovationoutlook.onmicrosoft.com"
    deleted_calendar_count = delete_calendar_event(token, user_email, client, call_type, date)

   
    deleted_db_count = delete_meeting(client, call_type, date)

    if deleted_calendar_count or deleted_db_count:
        return f"🗑️ Deleted {deleted_calendar_count} calendar event(s) and {deleted_db_count} DB record(s)."
    return "⚠️ No events found to delete."


def reschedule_meeting_tool(input_text: str) -> str:
    intent = parse_user_intent(input_text)
    client = intent.get("client_name")
    call_type = intent.get("call_type") or "any"

    if not client:
        return "⚠️ Please specify a client name."

    return reschedule_meeting(client, call_type)


tools = [
    Tool(name="ScheduleMeetings", func=schedule_meetings_tool, description="Schedules internal and external meetings from unread emails."),
    Tool(name="QueryMeetings", func=query_meetings_tool, description="Find meetings by client name, date, or type."),
    Tool(name="DeleteMeetings", func=delete_meeting_tool, description="Delete a meeting from the database and calendar."),
    Tool(name="RescheduleMeeting", func=reschedule_meeting_tool, description="Reschedule a meeting for a given client (internal or external)."),
]


agent = initialize_agent(
    tools,
    llm,
    agent=AgentType.OPENAI_FUNCTIONS,
    #verbose=True
)


console = Console()

if __name__ == "__main__":
    console.print(Panel.fit("🤖 [bold cyan]LangChain Briefing Assistant[/bold cyan]\n[dim]Type 'exit' to quit.[/dim]", box=box.DOUBLE))

    while True:
        user_input = Prompt.ask("[bold yellow]🧑 You[/bold yellow]")
        if user_input.lower().strip() in {"exit", "quit"}:
            console.print("\n👋 [bold]Goodbye![/bold]")
            break

        try:
            response = agent.invoke(user_input)
            message = response["output"] if isinstance(response, dict) and "output" in response else str(response)
            console.print(Panel.fit(message, title="🤖 Agent", style="bold cyan", box=box.ROUNDED))
        except Exception as e:
            console.print(Panel.fit(f"❌ [red]Error:[/red] {str(e)}", box=box.SQUARE))
