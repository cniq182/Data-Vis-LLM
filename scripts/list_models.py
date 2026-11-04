"""Check the CampusAI connection and list the models we can use."""
import tomllib
from pathlib import Path

from openai import OpenAI

# Read the key and URL from the secrets file (never hard-coded in the code).
secrets = tomllib.loads(Path(".streamlit/secrets.toml").read_text(encoding="utf-8"))

# Point the OpenAI library at DTU's server instead of OpenAI's.
client = OpenAI(
    api_key=secrets["CAMPUSAI_API_KEY"],
    base_url=secrets["CAMPUSAI_BASE_URL"],
)

# GET /v1/models: ask the server which models are available.
for model in client.models.list():
    print(model.id)