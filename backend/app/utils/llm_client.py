"""
LLM 클라이언트 래퍼
OpenAI 호환 형식으로 통일해 호출합니다.
"""

import json
import os
import re
from typing import Optional, Dict, Any, List
from urllib.parse import urlparse
import requests
from openai import OpenAI

from ..config import Config
from .logger import get_logger

logger = get_logger('mirofish.llm_client')


class LLMClient:
    """LLM 클라이언트"""
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None
    ):
        self.api_key = api_key or Config.LLM_API_KEY
        self.base_url = base_url or Config.LLM_BASE_URL
        self.model = model or Config.LLM_MODEL_NAME
        
        if not self.api_key:
            raise ValueError("LLM_API_KEY가 설정되지 않았습니다.")
        
        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url
        )

    def _is_ollama(self) -> bool:
        parsed = urlparse(self.base_url)
        return parsed.hostname in {"localhost", "127.0.0.1"} and parsed.port == 11434

    def _ollama_base_url(self) -> str:
        parsed = urlparse(self.base_url)
        scheme = parsed.scheme or "http"
        netloc = parsed.netloc or "localhost:11434"
        return f"{scheme}://{netloc}"

    def _ollama_chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: int,
        json_mode: bool = False
    ) -> str:
        # Ollama 기본 num_ctx는 4096이라, 엔터티 컨텍스트가 큰 프롬프트(시뮬레이션
        # 설정 등)는 입력만으로 컨텍스트를 채워 출력이 잘린다(done_reason=length).
        # 모델이 지원하는 범위에서 컨텍스트 창을 넉넉히 잡는다(env로 조정 가능).
        num_ctx = int(os.environ.get("OLLAMA_NUM_CTX", "16384"))
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "think": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
                "num_ctx": num_ctx,
            },
        }
        if json_mode:
            payload["format"] = "json"

        response = requests.post(
            f"{self._ollama_base_url()}/api/chat",
            json=payload,
            timeout=1800,
        )
        response.raise_for_status()
        data = response.json()
        if data.get("done_reason") == "length":
            content = (data.get("message") or {}).get("content", "").strip()
            # JSON은 잘리면 파싱 불가 → 에러로 올려 상위에서 재시도/복구하게 한다.
            if json_mode:
                raise ValueError(f"Ollama stopped at token limit before finishing the response: {content[:2000]}")
            # 평문은 잘려도 사용 가능 → 전체 실패 대신 부분 응답을 반환한다.
            logger.warning("Ollama가 토큰 한도에서 응답을 끊음(평문) — 부분 응답 반환")
            return content
        return (data.get("message") or {}).get("content", "").strip()
    
    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 4096,
        response_format: Optional[Dict] = None
    ) -> str:
        """
        채팅 요청을 전송합니다.
        
        Args:
            messages: 메시지 목록
            temperature: 온도 파라미터
            max_tokens: 최대 토큰 수
            response_format: 응답 형식(예: JSON 모드)
            
        Returns:
            모델 응답 텍스트
        """
        if self._is_ollama():
            return self._ollama_chat(messages, temperature, max_tokens)

        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        
        if response_format:
            kwargs["response_format"] = response_format
        
        response = self.client.chat.completions.create(**kwargs)
        content = response.choices[0].message.content
        # 일부 모델(예: MiniMax M2.5)은 content에 <think>를 포함하므로 제거
        content = re.sub(r'<think>[\s\S]*?</think>', '', content).strip()
        return content
    
    def chat_json(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.3,
        max_tokens: int = 4096
    ) -> Dict[str, Any]:
        """
        채팅 요청을 전송하고 JSON으로 반환합니다.
        
        Args:
            messages: 메시지 목록
            temperature: 온도 파라미터
            max_tokens: 최대 토큰 수
            
        Returns:
            파싱된 JSON 객체
        """
        if self._is_ollama():
            response = self._ollama_chat(
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                json_mode=True,
            )
        else:
            response = self.chat(
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                response_format={"type": "json_object"}
            )
        # 마크다운 코드 블록 표기 제거
        cleaned_response = response.strip()
        cleaned_response = re.sub(r'^```(?:json)?\s*\n?', '', cleaned_response, flags=re.IGNORECASE)
        cleaned_response = re.sub(r'\n?```\s*$', '', cleaned_response)
        cleaned_response = cleaned_response.strip()

        if not cleaned_response.startswith("{"):
            start = cleaned_response.find("{")
            end = cleaned_response.rfind("}")
            if start != -1 and end != -1 and end > start:
                cleaned_response = cleaned_response[start:end + 1]

        try:
            return json.loads(cleaned_response)
        except json.JSONDecodeError:
            pass

        # JSON 파싱 실패 시 1회 재시도 (temperature 올려 다른 응답 유도)
        if self._is_ollama():
            retry_response = self._ollama_chat(
                messages=messages,
                temperature=min(temperature + 0.1, 1.0),
                max_tokens=max_tokens,
                json_mode=True,
            )
        else:
            retry_response = self.chat(
                messages=messages,
                temperature=min(temperature + 0.1, 1.0),
                max_tokens=max_tokens,
                response_format={"type": "json_object"}
            )
        retry_cleaned = retry_response.strip()
        retry_cleaned = re.sub(r'^```(?:json)?\s*\n?', '', retry_cleaned, flags=re.IGNORECASE)
        retry_cleaned = re.sub(r'\n?```\s*$', '', retry_cleaned)
        retry_cleaned = retry_cleaned.strip()
        if not retry_cleaned.startswith("{"):
            start = retry_cleaned.find("{")
            end = retry_cleaned.rfind("}")
            if start != -1 and end != -1 and end > start:
                retry_cleaned = retry_cleaned[start:end + 1]

        try:
            return json.loads(retry_cleaned)
        except json.JSONDecodeError:
            preview = cleaned_response[:2000]
            raise ValueError(f"LLM returned invalid JSON: {preview}")
