from dataclasses import dataclass

from app.core.config import config


@dataclass
class LangfuseConfig:
    public_key: str
    secret_key: str
    host: str
    project_name: str

    @classmethod
    def from_env_guest(cls) -> "LangfuseConfig":
        return cls(
            public_key=config.LANGFUSE_PUBLIC_KEY or "",
            secret_key=config.LANGFUSE_SECRET_KEY or "",
            host=config.LANGFUSE_HOST,
            project_name="guest"
        )

    @classmethod
    def from_env_supervisor(cls) -> "LangfuseConfig":
        return cls(
            public_key=config.LANGFUSE_PUBLIC_SUPERVISOR_KEY or "",
            secret_key=config.LANGFUSE_SECRET_SUPERVISOR_KEY or "",
            host=config.LANGFUSE_HOST,
            project_name="supervisor"
        )
