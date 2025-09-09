import os
from dataclasses import dataclass


@dataclass
class LangfuseConfig:
    public_key: str
    secret_key: str
    host: str
    project_name: str

    @classmethod
    def from_env_guest(cls) -> "LangfuseConfig":
        return cls(
            public_key=os.environ["LANGFUSE_PUBLIC_KEY"],
            secret_key=os.environ["LANGFUSE_SECRET_KEY"],
            host=os.environ["LANGFUSE_HOST"],
            project_name="guest"
        )

    @classmethod
    def from_env_supervisor(cls) -> "LangfuseConfig":
        return cls(
            public_key=os.environ["LANGFUSE_PUBLIC_SUPERVISOR_KEY"],
            secret_key=os.environ["LANGFUSE_SECRET_SUPERVISOR_KEY"],
            host=os.environ["LANGFUSE_HOST_SUPERVISOR"],
            project_name="supervisor"
        )
