"""
Barça Bot Agent — OpenAI Agents SDK configuration.

The agent has two tools:
  • sql_query       → structured match/stats queries
  • User-provided files, images, and URLs are supplied as request context
"""
import os
from openai import AsyncOpenAI
from agents import Agent, set_default_openai_client, ModelSettings
from api.tools.sql_tool import sql_query
from api.config import settings
import agents

agents.set_default_openai_api("chat_completions")
agents.set_tracing_disabled(True)

# Configure a custom OpenAI client with automatic retry + exponential backoff.
# max_retries=6 means the SDK will retry up to 6 times on transient errors
# (including 429 rate-limit responses), with built-in exponential backoff.
_openai_client = AsyncOpenAI(
    api_key=settings.openai_api_key,
    base_url=os.getenv("OPENAI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai/"),
    max_retries=6,
    timeout=120.0,
)
set_default_openai_client(_openai_client)

SYSTEM_PROMPT = """
You are **Ninety**, a football intelligence assistant.
Help users think, write, research, plan, code, and analyze information.

## TOOL USE RULES — FOLLOW THESE STRICTLY

### Use `sql_query` only for football-data questions:
- La Liga standings, table position, points, wins, losses
- Match results, scores, fixtures (past or upcoming)
- Player statistics: goals, assists, appearances, cards
- Squad list, player info from the database

### For all other questions:
- Answer from your general model knowledge when no user-provided context is attached.
- Do not claim that facts came from a Barça knowledge base.
- State briefly when a fact may be outdated or uncertain, especially for current players,
  records, injuries, or recent events.

### NEVER call a tool for:
- Pure conversational follow-ups: "longer", "shorter", "expand", "summarize that", "explain more", "give me more detail", "make it longer"
- Greetings or small talk
- Clarifying what you just said

## Guidelines

- **Be useful and direct.** Match the user's requested level of detail.
- **Be precise with numbers** and distinguish known facts from assumptions.
- **Do not invent facts.** When uncertain, say so and recommend a source or ask the
  user to provide a file or URL for analysis.
- **Prioritize user-provided context** when it is attached.
- **Gracefully handle gaps**: if data isn't available, say so honestly.
- Use markdown formatting where helpful.
"""

barca_agent = Agent(
    name="Ninety",
    model=settings.model,
    instructions=SYSTEM_PROMPT,
    tools=[sql_query],
    model_settings=ModelSettings(
        parallel_tool_calls=False,  # Llama/Groq fails with parallel tool calls
    ),
)

general_agent = Agent(
    name="Ninety",
    model=settings.model,
    instructions=SYSTEM_PROMPT + """

For this response, do not call tools. Answer directly from your general knowledge
or from the user-provided context included in the request.
""",
    model_settings=ModelSettings(parallel_tool_calls=False),
)


async def generate_general_response(messages: list[dict]) -> str:
    response = await _openai_client.chat.completions.create(
        model=settings.model,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are Ninety, a helpful football intelligence assistant. "
                    "Answer directly and naturally. Use user-provided context as evidence. "
                    "For image questions, use the visual description and any filename hint "
                    "as supporting context, but label identity as likely rather than certain "
                    "unless the image contains clear identifying evidence. Do not invent "
                    "facts; acknowledge uncertainty when appropriate."
                ),
            },
            *messages,
        ],
        temperature=0.3,
    )
    return response.choices[0].message.content or ""
