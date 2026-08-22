import os

import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI

from data_loader import load_structured_data
from tools import execute_action
import agent
import insights


# ============================================================
# LOAD ENVIRONMENT VARIABLES
# ============================================================

load_dotenv()


# ============================================================
# STREAMLIT CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="ParcelPilot Support",
    page_icon="📦",
    layout="wide",
)


# ============================================================
# DATA + OPENROUTER CLIENT
# ============================================================

@st.cache_resource
def get_data():
    return load_structured_data()


@st.cache_resource
def get_client():
    """
    Create an OpenRouter client using the OpenAI-compatible SDK.
    """

    api_key = os.getenv("OPENROUTER_API_KEY")

    if not api_key:
        st.error(
            "OPENROUTER_API_KEY is not set. "
            "Please add it to your .env file."
        )
        st.stop()

    return OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
    )


data = get_data()
client = get_client()


# ============================================================
# SESSION STATE
# ============================================================

if "account_id" not in st.session_state:
    st.session_state.account_id = None

if "messages" not in st.session_state:
    st.session_state.messages = []

if "chat_log" not in st.session_state:
    st.session_state.chat_log = []

if "pending_action" not in st.session_state:
    st.session_state.pending_action = None

if "staff_authed" not in st.session_state:
    st.session_state.staff_authed = False


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.title("📦 ParcelPilot")

    view = st.radio(
        "View",
        [
            "Customer Support Chat",
            "Internal Insights (staff only)",
        ],
    )

    st.divider()

    if view == "Customer Support Chat":

        st.subheader("Mock customer login")

        account_options = {
            f"{row.account_name} ({row.account_id}, {row.plan})":
            row.account_id
            for row in data.accounts.itertuples()
        }

        choice = st.selectbox(
            "Logged in as",
            list(account_options.keys()),
        )

        selected_account = account_options[choice]

        # Reset conversation when switching accounts
        if selected_account != st.session_state.account_id:

            st.session_state.account_id = selected_account
            st.session_state.messages = []
            st.session_state.chat_log = []
            st.session_state.pending_action = None

        st.caption(
            f"Data & actions are scoped to "
            f"**{selected_account}** only."
        )

        if st.button("Reset conversation"):

            st.session_state.messages = []
            st.session_state.chat_log = []
            st.session_state.pending_action = None

            st.rerun()


# ============================================================
# CUSTOMER SUPPORT CHAT
# ============================================================

def render_chat():

    account_id = st.session_state.account_id

    st.header("Customer Support Chat")

    st.caption(f"Account: {account_id}")


    # --------------------------------------------------------
    # DISPLAY CHAT HISTORY
    # --------------------------------------------------------

    for entry in st.session_state.chat_log:

        with st.chat_message(entry["role"]):

            st.markdown(entry["text"])

            if entry.get("trace"):

                with st.expander(
                    "🔧 Tools used",
                    expanded=False,
                ):

                    for step in entry["trace"]:

                        st.markdown(
                            f"**{step['tool']}**"
                        )

                        st.json(step["input"])

                        st.json(step["result"])


    # --------------------------------------------------------
    # PENDING ACTION CONFIRMATION
    # --------------------------------------------------------

    if st.session_state.pending_action:

        proposal = (
            st.session_state
            .pending_action["proposal"]
        )

        with st.chat_message("assistant"):

            st.warning(
                "⚠️ Action awaiting your confirmation"
            )

            st.json(proposal)

            col1, col2 = st.columns(2)

            confirmed = col1.button(
                "✅ Confirm",
                key="confirm_action",
            )

            cancelled = col2.button(
                "❌ Cancel",
                key="cancel_action",
            )


            if confirmed or cancelled:

                # --------------------------------------------
                # CONFIRM ACTION
                # --------------------------------------------

                if confirmed:

                    result = execute_action(proposal)

                    st.session_state.chat_log.append(
                        {
                            "role": "assistant",
                            "text": (
                                "✅ Action executed: "
                                f"`{result['action_id']}` "
                                f"({result['action_type']}, "
                                f"{result.get('severity') or ''})."
                            ),
                            "trace": [],
                        }
                    )


                # --------------------------------------------
                # CANCEL ACTION
                # --------------------------------------------

                else:

                    result = {
                        "status": "declined_by_user"
                    }

                    st.session_state.chat_log.append(
                        {
                            "role": "assistant",
                            "text": (
                                "❌ Action cancelled — "
                                "nothing was created."
                            ),
                            "trace": [],
                        }
                    )


                # --------------------------------------------
                # RESUME AGENT
                # --------------------------------------------

                out = agent.resume_after_action(

                    client,

                    st.session_state.messages,

                    st.session_state.pending_action,

                    result,

                    account_id,

                    data,

                )


                # Update conversation messages
                st.session_state.messages = (
                    out["messages"]
                )


                # Update pending action
                st.session_state.pending_action = (
                    out["pending_action"]
                )


                # Add final agent response
                if out["final_text"]:

                    st.session_state.chat_log.append(
                        {
                            "role": "assistant",
                            "text": out["final_text"],
                            "trace": out["trace"],
                        }
                    )


                st.rerun()


        # Do not show chat input while action confirmation
        # is pending
        return


    # --------------------------------------------------------
    # USER INPUT
    # --------------------------------------------------------

    user_input = st.chat_input(
        "Ask about your orders, policies, or a service credit..."
    )


    if user_input:

        # --------------------------------------------
        # ADD USER MESSAGE TO UI
        # --------------------------------------------

        st.session_state.chat_log.append(
            {
                "role": "user",
                "text": user_input,
                "trace": [],
            }
        )


        # --------------------------------------------
        # ADD USER MESSAGE TO LLM HISTORY
        # --------------------------------------------

        st.session_state.messages.append(
            {
                "role": "user",
                "content": user_input,
            }
        )


        # --------------------------------------------
        # RUN AGENT
        # --------------------------------------------

        with st.spinner("Working on it..."):

            out = agent.start_turn(

                client,

                st.session_state.messages,

                account_id,

                data,

            )


        # --------------------------------------------
        # UPDATE CONVERSATION HISTORY
        # --------------------------------------------

        st.session_state.messages = (
            out["messages"]
        )


        # --------------------------------------------
        # STORE PENDING ACTION
        # --------------------------------------------

        st.session_state.pending_action = (
            out["pending_action"]
        )


        # --------------------------------------------
        # ADD AGENT RESPONSE TO CHAT
        # --------------------------------------------

        if out["final_text"]:

            st.session_state.chat_log.append(
                {
                    "role": "assistant",
                    "text": out["final_text"],
                    "trace": out["trace"],
                }
            )


        st.rerun()


# ============================================================
# INTERNAL INSIGHTS
# ============================================================

def render_internal():

    st.header(
        "Internal Insights (Proactive Issue Detection)"
    )


    # --------------------------------------------------------
    # STAFF AUTHENTICATION
    # --------------------------------------------------------

    if not st.session_state.staff_authed:

        st.info(
            "Staff-only view. "
            "Enter the internal access code to continue."
        )

        code = st.text_input(
            "Access code",
            type="password",
        )

        if st.button("Enter"):

            if code == "internal123":

                st.session_state.staff_authed = True

                st.rerun()

            else:

                st.error(
                    "Incorrect code."
                )

        return


    # --------------------------------------------------------
    # BUILD TICKET INSIGHTS
    # --------------------------------------------------------

    ticket_df = insights.build_ticket_insights(data)

    st.caption(
        f"Snapshot time: {data.snapshot_time}"
    )


    # --------------------------------------------------------
    # OPEN TICKETS — SLA STATUS
    # --------------------------------------------------------

    st.subheader(
        "Open tickets — SLA status"
    )


    if ticket_df.empty:

        st.write(
            "No open tickets."
        )

    else:

        def highlight(row):

            color = {
                "BREACHED": "#ffcccc",
                "NEAR BREACH": "#fff3cd",
            }.get(
                row["sla_status"],
                "",
            )

            return [
                f"background-color: {color}"
            ] * len(row)


        st.dataframe(
            ticket_df.style.apply(
                highlight,
                axis=1,
            ),
            use_container_width=True,
        )


    # --------------------------------------------------------
    # KNOWN ISSUE CLUSTERING
    # --------------------------------------------------------

    st.subheader(
        "Known-issue clustering"
    )

    clusters = insights.build_known_issue_clusters(
        ticket_df
    )


    if clusters.empty:

        st.write(
            "No tickets currently match a known issue."
        )

    else:

        st.dataframe(
            clusters,
            use_container_width=True,
        )


    # --------------------------------------------------------
    # HISTORICAL RESOLUTION REVIEW
    # --------------------------------------------------------

    st.subheader(
        "Historical resolutions needing re-verification"
    )

    st.caption(
        "These closed tickets carry a historical_resolution "
        "note. Per the data pack, such notes may be incorrect "
        "and should not be reused as policy without checking "
        "current sources."
    )

    review_df = (
        insights.historical_resolution_review_queue(
            data
        )
    )


    if review_df.empty:

        st.write(
            "None."
        )

    else:

        st.dataframe(
            review_df,
            use_container_width=True,
        )


# ============================================================
# APP ROUTING
# ============================================================

if view == "Customer Support Chat":

    render_chat()

else:

    render_internal()