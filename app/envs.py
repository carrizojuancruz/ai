import os

ENV_VARS = {
    "environment": os.getenv("ENVIRONMENT", "DEV"),
}
