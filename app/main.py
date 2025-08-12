from fastapi import FastAPI
from .envs import ENV_VARS

app = FastAPI()

@app.get("/")
def read_root():
    return {"message": "Hello, World!"}
