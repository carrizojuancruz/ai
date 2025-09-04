import json
import uuid
 
import requests
import streamlit as st
from sseclient import SSEClient
 
st.set_page_config(page_title="Supervisor Test UI", layout="wide")
 
if "thread_id" not in st.session_state:
    st.session_state.thread_id = None
if "messages" not in st.session_state:
    st.session_state.messages = []
if "user_id" not in st.session_state:
    st.session_state.user_id = str(uuid.uuid4())
if "base_url" not in st.session_state:
    st.session_state.base_url = "http://localhost:8000"
 
st.title("Supervisor Test UI")
 
with st.sidebar:
    st.header("Configuration")
    st.session_state.base_url = st.text_input("API Base URL", st.session_state.base_url)
    st.session_state.user_id = st.text_input("User ID", st.session_state.user_id)
    if st.button("Generate New User ID"):
        st.session_state.user_id = str(uuid.uuid4())
        st.rerun()
 
def start_conversation():
    """Initialize a new conversation thread with the supervisor."""
    try:
        response = requests.post(
            f"{st.session_state.base_url}/supervisor/initialize",
            json={"user_id": st.session_state.user_id},
        )
        response.raise_for_status()
        data = response.json()
        st.session_state.thread_id = data["thread_id"]
        st.session_state.messages = [{"role": "assistant", "content": data["welcome"]}]
    except requests.exceptions.RequestException as e:
        st.error(f"Failed to start conversation: {e}")
        st.session_state.thread_id = None
 
if st.session_state.thread_id is None:
    if st.button("Start Conversation"):
        start_conversation()
        st.rerun()
else:
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if "sources" in msg and msg["sources"]:
                st.info(f"Sources: {msg['sources']}")
 
    if prompt := st.chat_input("What is up?"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
 
        try:
            response = requests.post(
                f"{st.session_state.base_url}/supervisor/message",
                json={"thread_id": st.session_state.thread_id, "text": prompt},
            )
            response.raise_for_status()
 
            with st.chat_message("assistant"):
                message_placeholder = st.empty()
                full_response = ""
 
                sse_url = f"{st.session_state.base_url}/supervisor/sse/{st.session_state.thread_id}"
                headers = {'Accept': 'text/event-stream'}
                response = requests.get(sse_url, stream=True, headers=headers)
                client = SSEClient(response)
 
                is_first_delta = True
                sources = []
                welcome_message = st.session_state.messages[0]['content']
 
                for event in client.events():
                    if event.event == "token.delta":
                        data = json.loads(event.data)
                        text_delta = data.get("text", "")
                        sources = data.get("sources", [])
                        print(f"Sources: {sources}")
 
                        if is_first_delta and text_delta.strip() == welcome_message.strip():
                            is_first_delta = False
                            continue
 
                        is_first_delta = False
 
                        if text_delta.strip().startswith("CONTEXT_PROFILE:") or \
                           text_delta.strip().startswith("Relevant context for tailoring this turn:"):
                            continue
 
                        if len(text_delta) >= len(full_response) and text_delta.startswith(full_response):
                            full_response = text_delta
                        elif len(text_delta) < len(full_response) and full_response.endswith(text_delta):
                            continue
                        else:
                            full_response += text_delta
 
                        message_placeholder.markdown(full_response + "▌")
                    elif event.event == "tool.start" or event.event == "tool.end":
                        data = json.loads(event.data)
                        tool_name = data.get("tool")
                    elif event.event == "step.update":
                        data = json.loads(event.data)
                        if data.get("status") == "presented":
                            break
 
                message_placeholder.markdown(full_response)
 
            message_with_sources = {"role": "assistant", "content": full_response}
            if len(sources) > 0:
                message_with_sources["sources"] = sources
 
            st.session_state.messages.append(message_with_sources)
 
        except requests.exceptions.RequestException as e:
            st.error(f"Failed to send message: {e}")
        except Exception as e:
            st.error(f"An unexpected error occurred: {e}")
 
        st.rerun()