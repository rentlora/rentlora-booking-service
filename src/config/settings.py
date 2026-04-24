from pydantic_settings import BaseSettings

from typing import Optional

class Settings(BaseSettings):
    MONGO_USER: Optional[str] = None
    MONGO_PASSWORD: Optional[str] = None
    MONGO_HOST: str = "localhost"
    MONGO_PORT: str = "27017"
    PORT: int = 8003

    @property
    def MONGO_URI(self) -> str:
        if self.MONGO_USER and self.MONGO_PASSWORD:
            return f"mongodb://{self.MONGO_USER}:{self.MONGO_PASSWORD}@{self.MONGO_HOST}:{self.MONGO_PORT}"
        return f"mongodb://{self.MONGO_HOST}:{self.MONGO_PORT}"

    
    class Config:
        env_file = ".env"

settings = Settings()
