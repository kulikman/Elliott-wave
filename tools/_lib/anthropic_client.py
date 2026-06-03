"""Единый Anthropic API client с retry/backoff."""

import time
import anthropic
from tools._lib.config import get_api_key
from tools._lib.log import warn


def get_client() -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=get_api_key())


def call_with_retry(
    client: anthropic.Anthropic,
    model: str,
    messages: list[dict],
    system: str = "",
    max_tokens: int = 4096,
    max_retries: int = 3,
    temperature: float = 0.0,
) -> str:
    """Вызов API с экспоненциальным backoff. Возвращает текст ответа."""
    delay = 2.0
    last_error: Exception | None = None

    for attempt in range(1, max_retries + 1):
        try:
            kwargs: dict = dict(
                model=model,
                max_tokens=max_tokens,
                messages=messages,
                temperature=temperature,
            )
            if system:
                kwargs["system"] = system

            response = client.messages.create(**kwargs)
            return response.content[0].text

        except anthropic.RateLimitError as e:
            last_error = e
            wait = delay * (2 ** (attempt - 1))
            warn(f"Rate limit. Попытка {attempt}/{max_retries}. Жду {wait:.0f}с...")
            time.sleep(wait)

        except anthropic.APIStatusError as e:
            last_error = e
            if e.status_code >= 500:
                wait = delay * (2 ** (attempt - 1))
                warn(f"Ошибка сервера {e.status_code}. Попытка {attempt}/{max_retries}. Жду {wait:.0f}с...")
                time.sleep(wait)
            else:
                raise

        except Exception as e:
            raise

    raise RuntimeError(
        f"❌ API недоступен после {max_retries} попыток. "
        f"Последняя ошибка: {last_error}"
    )
