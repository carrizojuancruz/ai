# Supervisor Test UI

This Streamlit application provides a simple user interface to interact with and test the supervisor agent.

## How to Run

1.  **Navigate to this directory:**
    ```bash
    cd streamlit_supervisor_test
    ```

2.  **Install dependencies:**
    It's recommended to use a virtual environment.
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows use `venv\Scripts\activate`
    pip install -r requirements.txt
    ```

3.  **Run the application:**
    Make sure the main FastAPI application is running.
    ```bash
    streamlit run app.py
    ```

The application will be available at `http://localhost:8501` by default.

## Features

-   Start a new conversation with the supervisor.
-   Send messages and view the agent's responses in real-time.
-   See notifications for tool usage (`tool.start` and `tool.end`).
-   Configure the API base URL and `user_id` from the sidebar.
