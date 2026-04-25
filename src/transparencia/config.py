from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    azure_openai_endpoint: str
    azure_openai_api_key: str
    azure_openai_gpt4o_deployment: str = "gpt-4o"
    azure_openai_embedding_deployment: str = "text-embedding-3-small"

    azure_di_endpoint: str = ""
    azure_di_key: str = ""

    database_url: str

    api_key: str = ""

    socrata_app_token: str = ""
    socrata_domain: str = "www.datos.gov.co"


settings = Settings()
