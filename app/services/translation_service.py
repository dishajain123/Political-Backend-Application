"""
Translation Service
===================
Bedrock-backed translation helper with strict output behavior.

Design:
- Uses Bedrock model from settings.gpt_model (env: GPT_MODEL)
- Reads AWS credentials and region only from environment variables
- Returns only translated text (no extra tokens)
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from typing import Optional, Dict, Any

import boto3
from botocore.config import Config as BotoConfig

from app.core.config import settings

logger = logging.getLogger(__name__)


def _resolve_bedrock_model_id(model: str) -> str:
    model = (model or "").strip()
    if model.startswith("bedrock/"):
        return model.split("/", 1)[1]
    return model


def _extract_text_from_response(data: Dict[str, Any]) -> Optional[str]:
    if not isinstance(data, dict):
        return None
    # Bedrock Converse-style
    output = data.get("output")
    if isinstance(output, dict):
        msg = output.get("message")
        text = _extract_text_from_message(msg)
        if text:
            return text
    # Some providers return "message" at top level
    text = _extract_text_from_message(data.get("message"))
    if text:
        return text
    # Fallbacks used by some models
    results = data.get("results")
    if isinstance(results, list) and results:
        first = results[0]
        if isinstance(first, dict):
            if "outputText" in first:
                return str(first["outputText"])
    if "completion" in data:
        return str(data["completion"])
    if "text" in data:
        return str(data["text"])
    return None


def _extract_text_from_message(message: Any) -> Optional[str]:
    if not isinstance(message, dict):
        return None
    content = message.get("content")
    if isinstance(content, list):
        for item in content:
            if isinstance(item, dict) and "text" in item:
                return str(item["text"])
    if isinstance(content, str):
        return content
    return None


def _normalize_lang_code(value: Optional[str]) -> str:
    """
    Normalize language inputs to ISO 639-1 lowercase codes when possible.
    Accepts locale ids (hi-IN, mr_IN), language names, or codes.
    """
    if not value:
        return "en"
    raw = str(value).strip().lower()
    if not raw:
        return "en"
    # Locale forms
    raw = raw.replace("_", "-")
    if "-" in raw:
        raw = raw.split("-", 1)[0]
    name_map = {
        "english": "en",
        "eng": "en",
        "hindi": "hi",
        "marathi": "mr",
        "मराठी": "mr",
        "हिंदी": "hi",
    }
    return name_map.get(raw, raw)


_WRAPPER_PATTERNS = [
    re.compile(r"^\s*\"(.+)\"\s*$", re.DOTALL),
    re.compile(r"^\s*'(.+)'\s*$", re.DOTALL),
    re.compile(r"^\s*`{3,}.*?\n(.+?)\n`{3,}\s*$", re.DOTALL),
    re.compile(r"^\s*translated\s*text\s*:\s*(.+)$", re.IGNORECASE | re.DOTALL),
    re.compile(r"^\s*translation\s*:\s*(.+)$", re.IGNORECASE | re.DOTALL),
]


def _sanitize_translation_output(text: str) -> str:
    """
    Trim wrapper text or formatting if the model returns extra labels/quotes.
    """
    if not text:
        return text
    cleaned = text.strip()
    for pattern in _WRAPPER_PATTERNS:
        match = pattern.match(cleaned)
        if match:
            cleaned = match.group(1).strip()
    return cleaned


_SHORT_PHRASES = {
    "good morning",
    "thank you",
    "please come tomorrow",
    "meeting is postponed",
    "water issue in our area",
}


def _normalize_short_source(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def _needs_strict_retry(
    source_text: str,
    target_language: str,
    output_text: str,
) -> bool:
    """
    Detect clearly broken literal outputs for very short phrases.
    Keep this narrow and conservative.
    """
    lang = _normalize_lang_code(target_language)
    if lang not in {"en", "hi", "mr"}:
        return False
    src = _normalize_short_source(source_text)
    if src not in _SHORT_PHRASES:
        return False
    if not output_text.strip():
        return True
    # If output is identical to source for non-English targets, retry
    if lang in {"hi", "mr"} and _normalize_short_source(output_text) == src:
        return True
    # Targeted guard for "good morning" unnatural literal outputs
    if src == "good morning":
        if lang == "mr":
            return ("सकाळ" in output_text) and ("शुभ" not in output_text)
        if lang == "hi":
            return ("सुबह" in output_text or "सवेरे" in output_text) and (
                "शुभ" not in output_text and "सुप्रभात" not in output_text
            )
    return False


class TranslationService:
    def __init__(self) -> None:
        self.model_id = _resolve_bedrock_model_id(settings.gpt_model)
        self._client = None

    def _get_region(self) -> Optional[str]:
        return (
            (settings.AWS_DEFAULT_REGION or "").strip()
            or os.environ.get("AWS_DEFAULT_REGION")
            or os.environ.get("AWS_REGION")
        )

    def _client_or_raise(self):
        region = self._get_region()
        if not region:
            raise RuntimeError("AWS_DEFAULT_REGION is not set")
        if self._client is None:
            access_key = (settings.AWS_ACCESS_KEY_ID or "").strip()
            secret_key = (settings.AWS_SECRET_ACCESS_KEY or "").strip()
            client_kwargs = {
                "region_name": region,
                "config": BotoConfig(retries={"max_attempts": 3, "mode": "standard"}),
            }
            if access_key and secret_key:
                client_kwargs["aws_access_key_id"] = access_key
                client_kwargs["aws_secret_access_key"] = secret_key
            self._client = boto3.client(
                "bedrock-runtime",
                **client_kwargs,
            )
        return self._client

    def _build_system_prompt(
        self,
        source_language: str,
        target_language: str,
        strict: bool = False,
    ) -> str:
        source_language = _normalize_lang_code(source_language)
        target_language = _normalize_lang_code(target_language)
        base = (
            "You are a translation engine. "
            f"Translate the text from {source_language} to {target_language}. "
            "Preserve the intended meaning, tone, and context. "
            "Use natural, fluent, native-sounding phrasing in the target language, "
            "not a literal word-for-word translation. "
            "For greetings and very short phrases, use the most natural everyday "
            "native greeting or expression. "
            "Preserve names, URLs, numbers, emojis, hashtags, and placeholders "
            "like {{name}} exactly. "
            "Return only the translated text and nothing else. "
            "If the source is already in the target language, return it unchanged. "
            "Do not add explanations, quotes, labels, or extra text. "
            "For very short phrases, infer the most natural everyday translation "
            "for chat context."
        )
        example = (
            " Example (Marathi): "
            "\"Good morning\" -> \"शुभ सकाळ\" (correct). "
            "Not: \"सकाळ मोठी\" (incorrect)."
        )
        if strict:
            return base + example + " Avoid literal word-by-word output."
        return base + example

    def _build_detect_prompt(self) -> str:
        return (
            "Detect the language of the following text. "
            "Return only the ISO 639-1 lowercase language code (e.g., 'en', 'hi', 'mr'). "
            "If uncertain, return 'en'."
        )

    def _invoke_converse(self, system_prompt: str, user_text: str) -> Optional[str]:
        client = self._client_or_raise()
        if not hasattr(client, "converse"):
            return None
        response = client.converse(
            modelId=self.model_id,
            system=[{"text": system_prompt}],
            messages=[{"role": "user", "content": [{"text": user_text}]}],
            inferenceConfig={"temperature": 0, "maxTokens": 1024},
        )
        return _extract_text_from_response(response)

    def _invoke_model(self, system_prompt: str, user_text: str) -> Optional[str]:
        client = self._client_or_raise()
        body = {
            "system": [{"text": system_prompt}],
            "messages": [{"role": "user", "content": [{"text": user_text}]}],
            "inferenceConfig": {"temperature": 0, "maxTokens": 1024},
        }
        response = client.invoke_model(
            modelId=self.model_id,
            contentType="application/json",
            accept="application/json",
            body=json.dumps(body),
        )
        payload = response.get("body")
        if hasattr(payload, "read"):
            raw = payload.read()
        else:
            raw = payload
        if isinstance(raw, (bytes, bytearray)):
            raw = raw.decode("utf-8")
        data = json.loads(raw)
        return _extract_text_from_response(data)

    def _call_model(self, system_prompt: str, user_text: str) -> Optional[str]:
        # Prefer Converse if available; fallback to invoke_model
        text = self._invoke_converse(system_prompt, user_text)
        if text:
            return text
        return self._invoke_model(system_prompt, user_text)

    async def translate_text(
        self,
        text: str,
        source_language: str,
        target_language: str,
    ) -> Optional[str]:
        if not text:
            return text
        source_language = _normalize_lang_code(source_language)
        target_language = _normalize_lang_code(target_language)
        if source_language == target_language:
            return text
        system_prompt = self._build_system_prompt(source_language, target_language)
        try:
            logger.info(
                "Bedrock translate call: model=%s source=%s target=%s chars=%s",
                self.model_id,
                source_language,
                target_language,
                len(text),
            )
            result = await asyncio.to_thread(self._call_model, system_prompt, text)
            if isinstance(result, str):
                cleaned = _sanitize_translation_output(result)
                if _needs_strict_retry(text, target_language, cleaned):
                    strict_prompt = self._build_system_prompt(
                        source_language, target_language, strict=True
                    )
                    retry = await asyncio.to_thread(
                        self._call_model, strict_prompt, text
                    )
                    if isinstance(retry, str):
                        cleaned = _sanitize_translation_output(retry)
                logger.info(
                    "Bedrock translate result: model=%s target=%s chars=%s",
                    self.model_id,
                    target_language,
                    len(cleaned),
                )
                return cleaned
            logger.warning(
                "Bedrock translate empty result: model=%s target=%s",
                self.model_id,
                target_language,
            )
            return None
        except Exception as exc:
            logger.warning(f"Translation failed: {exc}")
            return None

    async def detect_language(self, text: str) -> Optional[str]:
        if not text:
            return None
        system_prompt = self._build_detect_prompt()
        try:
            result = await asyncio.to_thread(self._call_model, system_prompt, text)
            if not isinstance(result, str):
                return None
            code = result.strip().lower()
            if len(code) >= 2:
                return code[:2]
            return None
        except Exception as exc:
            logger.warning(f"Language detection failed: {exc}")
            return None
