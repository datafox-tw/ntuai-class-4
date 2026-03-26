"""
Google Audio Input Local File Upload
====================================

Cookbook example for `google/gemini/audio_input_local_file_upload.py`.
"""

from pathlib import Path

from agno.agent import Agent
from agno.media import Audio
from agno.models.google import Gemini

# ---------------------------------------------------------------------------
# Create Agent
# ---------------------------------------------------------------------------
import os
from dotenv import load_dotenv

load_dotenv()
google_api_key = os.getenv('GOOGLE_API_KEY')
agent = Agent(
    model=Gemini(api_key=google_api_key, id="gemini-2.5-flash"),
    markdown=True,
)


# Please download a sample audio file to test this Agent and upload using:
audio_path = Path(__file__).parent.joinpath("sample.mp3")

agent.print_response(
    "Tell me about this audio",
    audio=[Audio(filepath=audio_path)],
    stream=True,
)