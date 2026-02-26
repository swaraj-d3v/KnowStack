import re

import httpx

from app.core.config import settings


def _build_prompts(
    question: str,
    context_snippets: list[str],
    conversation_context: list[str] | None = None,
) -> tuple[str, str]:
    system_prompt = (
        "You are KnowStack, a friendly document assistant. "
        "Answer only from provided context and never invent facts. "
        "Be natural, clear, and question-oriented. "
        "After each answer, end with one short follow-up question to continue the conversation."
    )
    context_block = "\n\n".join(f"- {item}" for item in context_snippets)
    memory_block = ""
    if conversation_context:
        memory_block = "\n".join(f"- {item}" for item in conversation_context[:4])
    user_prompt = (
        f"User question:\n{question}\n\n"
        + (f"Recent conversation:\n{memory_block}\n\n" if memory_block else "")
        + 
        f"Document context:\n{context_block}\n\n"
        "Output rules:\n"
        "1) Start directly with the answer, no meta text.\n"
        "2) Use simple language.\n"
        "3) If user asks to summarize, use short bullets.\n"
        "4) If evidence is weak, say exactly what is missing from the document.\n"
        "5) End with one short line that asks what the user wants next.\n"
    )
    return system_prompt, user_prompt


def _ensure_conversation_finish(answer: str) -> str:
    text = answer.strip()
    if not text:
        return text
    lower = text.lower()
    prompts = [
        "what would you like to ask next?",
        "what should i help you with next?",
        "do you want me to explain any part in more detail?",
    ]
    if any(p in lower for p in prompts):
        return text
    return f"{text}\n\nWhat would you like to ask next?"


def _normalize_line(text: str) -> str:
    line = text.replace("\u00a0", " ").replace("\u200b", " ")
    line = re.sub(r"([a-z])([A-Z])", r"\1 \2", line)
    line = re.sub(r"\s+", " ", line)
    line = line.strip(" -\t\n\r")
    return line


def _extract_sentences(context_snippets: list[str]) -> list[str]:
    sentences: list[str] = []
    seen: set[str] = set()
    for snippet in context_snippets:
        parts = re.split(r"[\n\r]+|(?<=[.!?])\s+", snippet)
        for part in parts:
            line = _normalize_line(part)
            if len(line) < 20:
                continue
            if sum(ch.isalpha() for ch in line) < 12:
                continue
            key = line.lower()
            if key in seen:
                continue
            seen.add(key)
            sentences.append(line)
    return sentences


def _build_bullets(sentences: list[str], limit: int = 4) -> list[str]:
    bullets: list[str] = []
    for sentence in sentences:
        if len(bullets) >= limit:
            break
        trimmed = sentence[:220].rstrip(" ,;:")
        bullets.append(f"- {trimmed}")
    return bullets


def _extract_term(question: str) -> str | None:
    match = re.search(r"\b(?:what is|define|explain)\s+([a-z0-9+\- ]{2,40})\??", question.lower())
    if not match:
        return None
    term = re.sub(r"\s+", " ", match.group(1)).strip()
    return term or None


def _follow_up_requested(question: str) -> bool:
    q = question.lower().strip()
    return any(
        token in q
        for token in ["tell me more", "more details", "elaborate", "explain more", "go deeper", "continue"]
    )


def _topic_from_context(conversation_context: list[str] | None) -> str | None:
    if not conversation_context:
        return None
    for item in conversation_context:
        line = _normalize_line(item)
        if len(line) >= 20:
            return line[:140]
    return None


def generate_fallback_answer(
    question: str,
    context_snippets: list[str],
    conversation_context: list[str] | None = None,
) -> str:
    sentences = _extract_sentences(context_snippets)
    q = question.lower().strip()
    prior_topic = _topic_from_context(conversation_context)

    if not sentences:
        return _ensure_conversation_finish(
            "I found the document, but I could not extract enough clean text to answer confidently."
        )

    term = _extract_term(question)
    if term:
        term_words = [w for w in term.split() if len(w) >= 2]
        matches = [
            s for s in sentences if any(word in s.lower() for word in term_words)
        ]
        if matches:
            answer = "From your document, here is what I found:\n" + "\n".join(_build_bullets(matches, limit=3))
            return _ensure_conversation_finish(answer)
        answer = (
            f"Your document mentions '{term}', but it does not clearly define it. "
            "I can still give a general explanation if you want."
        )
        return _ensure_conversation_finish(answer)

    if any(token in q for token in ["document about", "summar", "overview", "tell me about"]):
        profile_hint = ""
        joined = " ".join(sentences).lower()
        if any(k in joined for k in ["work experience", "technical skills", "profile summary", "resume"]):
            profile_hint = "This document looks like a resume/profile.\n"
        answer = profile_hint + "Main points from your document:\n" + "\n".join(_build_bullets(sentences, limit=5))
        return _ensure_conversation_finish(answer)

    if _follow_up_requested(question):
        lead = "Here are more details from the document:\n"
        if prior_topic:
            lead = f"Continuing from your previous question about \"{prior_topic}\", here are more details:\n"
        answer = lead + "\n".join(_build_bullets(sentences, limit=5))
        return _ensure_conversation_finish(answer)

    answer = "Based on the document, this is the most relevant information:\n" + "\n".join(_build_bullets(sentences, limit=4))
    return _ensure_conversation_finish(answer)


def _generate_with_gemini(
    question: str,
    context_snippets: list[str],
    conversation_context: list[str] | None = None,
) -> tuple[str | None, str]:
    if not settings.gemini_api_key:
        return None, ""
    system_prompt, user_prompt = _build_prompts(question, context_snippets, conversation_context)

    try:
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{settings.gemini_model}:generateContent?key={settings.gemini_api_key}"
        )
        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                url,
                json={
                    "system_instruction": {
                        "parts": [{"text": system_prompt}],
                    },
                    "contents": [
                        {
                            "role": "user",
                            "parts": [{"text": user_prompt}],
                        }
                    ],
                    "generationConfig": {"temperature": 0.15},
                },
            )
        response.raise_for_status()
        data = response.json()
        candidates = data.get("candidates", [])
        if not candidates:
            return None, ""
        parts = candidates[0].get("content", {}).get("parts", [])
        text = "\n".join(p.get("text", "") for p in parts if p.get("text"))
        final = _ensure_conversation_finish(text)
        return final or None, settings.gemini_model
    except Exception:
        return None, ""


def _generate_with_openai(
    question: str,
    context_snippets: list[str],
    conversation_context: list[str] | None = None,
) -> tuple[str | None, str]:
    if not settings.openai_api_key:
        return None, ""
    system_prompt, user_prompt = _build_prompts(question, context_snippets, conversation_context)

    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.openai_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": settings.openai_model,
                    "temperature": 0.15,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                },
            )
        response.raise_for_status()
        data = response.json()
        choices = data.get("choices", [])
        if not choices:
            return None, ""
        content = choices[0].get("message", {}).get("content", "")
        final = _ensure_conversation_finish(content)
        return final or None, settings.openai_model
    except Exception:
        return None, ""


def generate_grounded_answer(
    question: str,
    context_snippets: list[str],
    conversation_context: list[str] | None = None,
) -> tuple[str | None, str]:
    if not context_snippets:
        return None, ""

    provider = settings.llm_provider.strip().lower()
    if provider == "gemini":
        answer, model = _generate_with_gemini(question, context_snippets, conversation_context)
        if answer:
            return answer, model
        return _generate_with_openai(question, context_snippets, conversation_context)
    if provider == "openai":
        answer, model = _generate_with_openai(question, context_snippets, conversation_context)
        if answer:
            return answer, model
        return _generate_with_gemini(question, context_snippets, conversation_context)
    answer, model = _generate_with_gemini(question, context_snippets, conversation_context)
    if answer:
        return answer, model
    return _generate_with_openai(question, context_snippets, conversation_context)

