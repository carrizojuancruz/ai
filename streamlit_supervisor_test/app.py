import json
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests
import streamlit as st
from sseclient import SSEClient

st.set_page_config(page_title="Supervisor Test UI", layout="wide")

def load_benchmark_prompts() -> list[str]:
    path = Path(__file__).parent / "benchmark_prompts.json"
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, list) else []

def escape_currency_dollars(text: str) -> str:
    """Escape $ characters that are likely currency amounts, while preserving LaTeX math expressions.

    This function:
    - Escapes $ followed by numbers (currency like $36, $12.50)
    - Leaves $ followed by letters/variables intact (math like $x + y$)
    - Preserves $$ display math expressions
    """
    if not text:
        return text

    # Pattern to match currency: $ followed by digits, optionally with commas/decimals
    # This will match: $36, $12.50, $1,000, $100.99, etc.
    currency_pattern = r'\$([0-9]+(?:,[0-9]{3})*(?:\.[0-9]{1,2})?)'

    # Replace currency $ with \$ to escape in markdown
    def escape_currency_match(match):
        return f"\\${match.group(1)}"

    return re.sub(currency_pattern, escape_currency_match, text)

if "thread_id" not in st.session_state:
    st.session_state.thread_id = None
if "messages" not in st.session_state:
    st.session_state.messages = []
if "user_id" not in st.session_state:
    st.session_state.user_id = "a0911c1c-84bd-4ce7-96d9-649167455a06"
if "base_url" not in st.session_state:
    st.session_state.base_url = "http://localhost:8001"
if "benchmark_results" not in st.session_state:
    st.session_state.benchmark_results = []
if "benchmark_mode" not in st.session_state:
    st.session_state.benchmark_mode = False
if "events" not in st.session_state:
    st.session_state.events = []

st.title("Supervisor Test UI")

# Sidebar for benchmark mode
with st.sidebar:
    st.header("⚡ Benchmark Mode")
    prompt_count = len(load_benchmark_prompts())
    if st.button(f"🚀 Run {prompt_count} Prompts Parallel"):
        st.session_state.benchmark_mode = True
        st.session_state.benchmark_results = []
        st.rerun()

    if st.button("Clear Results"):
        st.session_state.benchmark_results = []
        st.rerun()

    if st.session_state.benchmark_results:
        st.subheader("📊 Results")
        for result in st.session_state.benchmark_results:
            st.metric(
                label=f"Prompt {result['id']}",
                value=f"{result['total_time']:.2f}s",
                delta=f"TTFT: {result['ttft']:.2f}s"
            )

    st.divider()

    with st.expander("📡 Events Log", expanded=False):
        if st.button("🗑️ Clear Events", key="clear_events"):
            st.session_state.events = []
            st.rerun()

        if st.session_state.events:
            st.markdown(f"**Total Events: {len(st.session_state.events)}**")
            for _, event in enumerate(st.session_state.events, 1):
                st.code(json.dumps(event, indent=2, ensure_ascii=False), language="json")
        else:
            st.info("No events yet. Start a conversation to see events.")

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
        st.session_state.events = []
    except requests.exceptions.RequestException as e:
        st.error(f"Failed to start conversation: {e}")
        st.session_state.thread_id = None

def send_prompt_and_measure(prompt_text: str, prompt_id: int, base_url: str, user_id: str) -> dict:
    """Send a prompt and measure timing metrics."""
    start_time = time.time()
    ttft = None

    try:
        # Initialize new thread for this prompt
        init_response = requests.post(
            f"{base_url}/supervisor/initialize",
            json={"user_id": user_id},
        )
        init_response.raise_for_status()
        thread_data = init_response.json()
        thread_id = thread_data["thread_id"]

        # Send message
        msg_response = requests.post(
            f"{base_url}/supervisor/message",
            json={"thread_id": thread_id, "text": prompt_text},
        )
        msg_response.raise_for_status()

        # Listen to SSE stream
        sse_url = f"{base_url}/supervisor/sse/{thread_id}"
        headers = {'Accept': 'text/event-stream'}
        response = requests.get(sse_url, stream=True, headers=headers)
        client = SSEClient(response)

        full_response = ""
        first_token_received = False

        for event in client.events():
            if event.event == "token.delta":
                if not first_token_received:
                    ttft = time.time() - start_time
                    first_token_received = True

                data = json.loads(event.data)
                text_delta = data.get("text", "")
                full_response += text_delta

            elif event.event == "step.update":
                data = json.loads(event.data)
                if data.get("status") == "presented":
                    break

        total_time = time.time() - start_time

        return {
            "id": prompt_id,
            "prompt": prompt_text,
            "response": full_response,
            "ttft": ttft or 0,
            "total_time": total_time,
            "success": True
        }

    except Exception as e:
        total_time = time.time() - start_time
        return {
            "id": prompt_id,
            "prompt": prompt_text,
            "response": f"Error: {str(e)}",
            "ttft": 0,
            "total_time": total_time,
            "success": False
        }

# Automatically start conversation if not already started
if st.session_state.thread_id is None:
    start_conversation()

# Benchmark mode execution
if st.session_state.benchmark_mode:
    st.session_state.benchmark_mode = False

    benchmark_prompts = load_benchmark_prompts()
    total = len(benchmark_prompts)

    if total == 0:
        st.error("No benchmark prompts found.")
    else:
        st.info(f"🚀 Running {total} prompts in parallel...")
        progress_bar = st.progress(0)

    base_url = st.session_state.base_url
    user_id = st.session_state.user_id

    if total > 0:
        with ThreadPoolExecutor(max_workers=min(5, total)) as executor:
            futures = {
                executor.submit(send_prompt_and_measure, prompt, i+1, base_url, user_id): i
                for i, prompt in enumerate(benchmark_prompts)
            }

            for completed, future in enumerate(as_completed(futures), start=1):
                result = future.result()
                st.session_state.benchmark_results.append(result)
                progress_bar.progress(completed / total)

        st.session_state.benchmark_results.sort(key=lambda x: x['id'])
        st.success("✅ Benchmark completed!")
        st.rerun()

# Display benchmark results in tabs
if st.session_state.benchmark_results:
    st.subheader("📊 Benchmark Results")

    tabs = st.tabs([f"Prompt {r['id']}" for r in st.session_state.benchmark_results])

    for idx, tab in enumerate(tabs):
        with tab:
            result = st.session_state.benchmark_results[idx]

            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("⏱️ Total Time", f"{result['total_time']:.2f}s")
            with col2:
                st.metric("⚡ TTFT", f"{result['ttft']:.2f}s")
            with col3:
                status = "✅ Success" if result['success'] else "❌ Failed"
                st.metric("Status", status)

            st.markdown("**Prompt:**")
            st.info(result['prompt'])

            st.markdown("**Response:**")
            st.markdown(escape_currency_dollars(result['response']))

    st.divider()

# Display messages if conversation is active
if st.session_state.thread_id is not None:
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            # Content is already escaped when stored, just display it
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

            # Instantiate SSEClient for streaming events
            sse_url = f"{st.session_state.base_url}/supervisor/sse/{st.session_state.thread_id}"
            headers = {'Accept': 'text/event-stream'}
            sse_response = requests.get(sse_url, stream=True, headers=headers)
            client = SSEClient(sse_response)

            with st.chat_message("assistant"):
                message_placeholder = st.empty()
                full_response = ""
                final_response = ""
                sources = []
                is_first_delta = True
                welcome_message = st.session_state.messages[0]['content']
                suppress_tokens = False

                for event in client.events():
                    if event.event == "message.completed":
                        data = json.loads(event.data)
                        final_response = data.get("content", "")
                        sources = data.get("sources", [])
                        st.session_state.events.append({
                            "type": "message.completed",
                            "timestamp": time.time(),
                            "data": data
                        })
                        escaped_final = escape_currency_dollars(final_response)
                        message_placeholder.markdown(escaped_final)
                        full_response = final_response

                        escaped_response = escape_currency_dollars(full_response)
                        message_with_sources = {"role": "assistant", "content": escaped_response}
                        if len(sources) > 0:
                            message_with_sources["sources"] = sources

                        st.session_state.messages.append(message_with_sources)
                        break
                    else:
                        continue

        except requests.exceptions.RequestException as e:
            st.error(f"Failed to send message: {e}")
        except Exception as e:
            st.error(f"An unexpected error occurred: {e}")

        st.rerun()
