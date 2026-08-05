"""Reusable Gemini adapter for JSON-structured agent outputs."""
from __future__ import annotations
import json, os
from collections.abc import Mapping
from typing import Protocol
class StructuredGenerator(Protocol):
    def generate(self, prompt: str, schema: Mapping[str, object]) -> Mapping[str, object]: ...
class GeminiStructuredGenerator:
    def __init__(self, api_key: str | None=None, model_name: str | None=None) -> None:
        self._api_key=api_key or os.getenv("GEMINI_API_KEY")
        self._model_name=model_name or os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    def generate(self, prompt: str, schema: Mapping[str, object]) -> Mapping[str, object]:
        if not self._api_key: raise RuntimeError("GEMINI_API_KEY is required to run an AI agent.")
        try: from google import genai
        except ImportError as error: raise RuntimeError("Install dependencies before running Gemini-powered agents.") from error
        client=genai.Client(api_key=self._api_key)
        try:
            response=client.models.generate_content(model=self._model_name,contents=prompt,config={"response_mime_type":"application/json","response_json_schema":dict(schema),"temperature":0.3})
        finally: client.close()
        result=getattr(response,"parsed",None) or json.loads(response.text)
        if not isinstance(result,Mapping): raise RuntimeError("Gemini returned JSON that is not an object.")
        return result