"""
ParcelPilot Agent

This agent uses OpenRouter through the OpenAI-compatible SDK.

Workflow:
1. User sends a message.
2. The LLM can call available tools.
3. Non-action tools execute immediately.
4. If the model calls propose_action, the agent pauses.
5. The Streamlit UI asks the user to Confirm or Cancel.
6. After confirmation/cancellation, the agent resumes.
"""

import json
import os

from data_loader import StructuredData
from tools import (
    TOOL_DEFINITIONS,
    run_search_documents,
    run_structured_data_lookup,
    run_propose_action,
)


# ============================================================
# OPENROUTER MODEL
# ============================================================

MODEL = os.getenv(
    "OPENROUTER_MODEL",
    "openrouter/free",
)


# ============================================================
# SYSTEM PROMPT
# ============================================================

SYSTEM_PROMPT = """
You are ParcelPilot's customer support assistant, talking to an
authenticated customer.

You can only see and act on THIS customer's own data.

The tools are already scoped to the authenticated account, so never
claim to look at another customer's information.

SOURCE AUTHORITY

Use sources in this order when they conflict:

1. The customer's own signed contract/agreement, if one exists and
   covers the topic.

2. Current policy or current SOP documents.

3. Current product documentation.

4. Never use a document marked "deprecated" as current guidance.
   If you find one, explicitly state that a newer version supersedes it
   and use the current version instead.

5. Historical ticket "historical_resolution" text is past context only.
   It may be wrong. Never repeat it as current policy without verifying
   it against current documents.

HOW TO ANSWER

- Use search_documents for questions about policy, SOP rules,
  contract terms, or known product issues.

- Use structured_data_lookup for questions about the customer's own
  account, orders, or tickets.

- Timing and delay calculations are already provided by the structured
  data tool when applicable.

- Multi-step questions are normal.

- If you cannot answer confidently because sources conflict, important
  facts are missing, manager approval is required, or the situation is
  outside what you can determine, say so clearly and recommend
  escalation instead of guessing.

- Never promise a service credit or fee waiver without first checking
  the relevant facts using the available tools.

ACTIONS

- Use propose_action to stage an escalation or follow-up task.

- propose_action does NOT execute anything immediately.

- The customer must explicitly confirm the action in the UI.

- Before proposing an action, gather the necessary information using
  the other tools.

- Call propose_action only once you have the necessary information.

- Do not claim that an action has been completed unless the user has
  confirmed it.

Keep answers concise, direct, and mention which source you relied on,
for example:

"Per your Enterprise Agreement..."

or

"According to the current Cancellation & Service Credit SOP..."
"""


# ============================================================
# CONVERT TOOL DEFINITIONS TO OPENAI / OPENROUTER FORMAT
# ============================================================

def get_openrouter_tools():
    """
    Convert the existing internal tool definitions into the
    OpenAI/OpenRouter function-calling format.

    Your tools.py does not need to be changed.
    """

    openrouter_tools = []

    for tool in TOOL_DEFINITIONS:

        openrouter_tools.append(
            {
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool["description"],
                    "parameters": tool["input_schema"],
                },
            }
        )

    return openrouter_tools


OPENROUTER_TOOLS = get_openrouter_tools()


# ============================================================
# EXECUTE NON-ACTION TOOLS
# ============================================================

def _execute_tool(
    name: str,
    args: dict,
    account_id: str,
    data: StructuredData,
) -> dict:
    """
    Execute regular tools.

    Account access is enforced inside the tool layer.
    """

    if name == "search_documents":

        return run_search_documents(
            args,
            account_id,
        )

    if name == "structured_data_lookup":

        return run_structured_data_lookup(
            args,
            account_id,
            data,
        )

    return {
        "error": f"Unknown tool: {name}"
    }


# ============================================================
# SAFE TOOL ARGUMENT PARSING
# ============================================================

def _parse_arguments(arguments):
    """
    Parse tool arguments returned by OpenRouter.

    OpenAI/OpenRouter tool calls usually return arguments as a JSON
    string.
    """

    if isinstance(arguments, dict):
        return arguments

    if not arguments:
        return {}

    try:

        return json.loads(arguments)

    except json.JSONDecodeError:

        return {
            "error": "Invalid JSON arguments returned by model."
        }


# ============================================================
# EXTRACT ASSISTANT TEXT
# ============================================================

def _extract_text(message) -> str:
    """
    Extract normal assistant text safely.
    """

    content = message.content

    if not content:
        return ""

    return content


# ============================================================
# CREATE ASSISTANT MESSAGE FOR CONVERSATION HISTORY
# ============================================================

def _build_assistant_message(message) -> dict:
    """
    Convert the OpenAI SDK response message into a plain dictionary
    that can be stored in the conversation history.

    This preserves tool calls for the next API request.
    """

    assistant_message = {
        "role": "assistant",
        "content": message.content,
    }

    if message.tool_calls:

        assistant_message["tool_calls"] = []

        for tool_call in message.tool_calls:

            assistant_message["tool_calls"].append(
                {
                    "id": tool_call.id,
                    "type": "function",
                    "function": {
                        "name": tool_call.function.name,
                        "arguments": tool_call.function.arguments,
                    },
                }
            )

    return assistant_message


# ============================================================
# MAIN AGENT LOOP
# ============================================================

def _agent_loop(
    client,
    messages,
    account_id,
    data,
):
    """
    Run the agent until:

    1. The model produces a final answer, OR
    2. The model proposes an action requiring user confirmation.
    """

    trace = []

    while True:

        # ----------------------------------------------------
        # CALL OPENROUTER
        # ----------------------------------------------------

        response = client.chat.completions.create(

            model=MODEL,

            messages=[
                {
                    "role": "system",
                    "content": SYSTEM_PROMPT,
                },
                *messages,
            ],

            tools=OPENROUTER_TOOLS,

            tool_choice="auto",

            max_tokens=1500,
        )


        # ----------------------------------------------------
        # GET ASSISTANT MESSAGE
        # ----------------------------------------------------

        assistant_message = response.choices[0].message


        # Store assistant response in plain dictionary format
        messages.append(
            _build_assistant_message(
                assistant_message
            )
        )


        # ----------------------------------------------------
        # CHECK FOR TOOL CALLS
        # ----------------------------------------------------

        tool_calls = assistant_message.tool_calls


        # ----------------------------------------------------
        # NO TOOL CALL = FINAL RESPONSE
        # ----------------------------------------------------

        if not tool_calls:

            final_text = _extract_text(
                assistant_message
            )

            return {
                "messages": messages,
                "pending_action": None,
                "final_text": final_text,
                "trace": trace,
            }


        # ----------------------------------------------------
        # CHECK WHETHER AN ACTION WAS PROPOSED
        # ----------------------------------------------------

        action_call = None

        for tool_call in tool_calls:

            if tool_call.function.name == "propose_action":

                action_call = tool_call

                break


        # ----------------------------------------------------
        # EXECUTE TOOL CALLS
        # ----------------------------------------------------

        results_by_id = {}

        for tool_call in tool_calls:

            tool_name = tool_call.function.name

            args = _parse_arguments(
                tool_call.function.arguments
            )


            # ----------------------------------------------
            # PROPOSE ACTION
            # ----------------------------------------------

            if tool_name == "propose_action":

                result = run_propose_action(
                    args
                )


            # ----------------------------------------------
            # NORMAL TOOLS
            # ----------------------------------------------

            else:

                result = _execute_tool(
                    tool_name,
                    args,
                    account_id,
                    data,
                )


            # Save tool trace for Streamlit UI
            trace.append(
                {
                    "tool": tool_name,
                    "input": args,
                    "result": result,
                }
            )


            results_by_id[tool_call.id] = result


        # ----------------------------------------------------
        # ACTION FOUND → PAUSE FOR USER CONFIRMATION
        # ----------------------------------------------------

        if action_call is not None:

            action_args = _parse_arguments(
                action_call.function.arguments
            )

            preface_text = _extract_text(
                assistant_message
            )


            return {
                "messages": messages,

                "pending_action": {

                    "action_tool_call_id":
                        action_call.id,

                    "proposal":
                        action_args,

                    "tool_calls": [
                        {
                            "id": tool_call.id,
                            "name":
                                tool_call.function.name,
                        }
                        for tool_call in tool_calls
                    ],

                    "results_by_id":
                        results_by_id,
                },

                "final_text":
                    preface_text,

                "trace":
                    trace,
            }


        # ----------------------------------------------------
        # SEND TOOL RESULTS BACK TO MODEL
        # ----------------------------------------------------

        for tool_call in tool_calls:

            result = results_by_id[
                tool_call.id
            ]

            messages.append(
                {
                    "role": "tool",

                    "tool_call_id":
                        tool_call.id,

                    "content":
                        json.dumps(
                            result,
                            default=str,
                        ),
                }
            )


        # Loop again so the model can use the tool results.


# ============================================================
# START A NEW USER TURN
# ============================================================

def start_turn(
    client,
    messages: list,
    account_id: str,
    data: StructuredData,
):
    """
    Start processing a new user message.

    The messages list must already contain the latest user message.
    """

    return _agent_loop(
        client,
        messages,
        account_id,
        data,
    )


# ============================================================
# RESUME AFTER HUMAN CONFIRMATION
# ============================================================

def resume_after_action(
    client,
    messages,
    pending_action,
    execution_result,
    account_id,
    data,
):
    """
    Resume the agent after the user either confirms or cancels
    the proposed action.

    execution_result contains either:

    - execute_action(...) output after confirmation

    OR

    - a declined/cancelled result.
    """

    results_by_id = dict(
        pending_action["results_by_id"]
    )


    # Replace the staged proposal result with the actual result
    results_by_id[
        pending_action["action_tool_call_id"]
    ] = execution_result


    # Send all tool results back to the model
    for tool_call in pending_action["tool_calls"]:

        tool_call_id = tool_call["id"]

        result = results_by_id[
            tool_call_id
        ]

        messages.append(
            {
                "role": "tool",

                "tool_call_id":
                    tool_call_id,

                "content":
                    json.dumps(
                        result,
                        default=str,
                    ),
            }
        )


    # Continue the agent loop
    return _agent_loop(
        client,
        messages,
        account_id,
        data,
    )