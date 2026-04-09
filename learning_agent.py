#!/usr/bin/env python3
"""
Агент, который обучается на ваших запросах.
Сохраняет историю взаимодействий и адаптируется к вашим предпочтениям.
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

import anthropic

# Файлы для хранения памяти
MEMORY_DIR = Path.home() / ".learning_agent"
HISTORY_FILE = MEMORY_DIR / "history.jsonl"
PROFILE_FILE = MEMORY_DIR / "user_profile.json"

MEMORY_DIR.mkdir(exist_ok=True)

client = anthropic.Anthropic()


def load_history(limit: int = 20) -> list[dict]:
    """Загружает последние N взаимодействий из истории."""
    if not HISTORY_FILE.exists():
        return []
    lines = HISTORY_FILE.read_text(encoding="utf-8").strip().splitlines()
    entries = [json.loads(line) for line in lines if line.strip()]
    return entries[-limit:]


def save_interaction(user_request: str, assistant_response: str):
    """Сохраняет взаимодействие в историю."""
    entry = {
        "timestamp": datetime.now().isoformat(),
        "user": user_request,
        "assistant": assistant_response,
    }
    with HISTORY_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def load_profile() -> dict:
    """Загружает профиль пользователя."""
    if not PROFILE_FILE.exists():
        return {}
    return json.loads(PROFILE_FILE.read_text(encoding="utf-8"))


def save_profile(profile: dict):
    """Сохраняет обновлённый профиль."""
    PROFILE_FILE.write_text(json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8")


def update_profile(history: list[dict]) -> dict:
    """Анализирует историю и обновляет профиль пользователя с помощью Claude."""
    if len(history) < 3:
        return load_profile()

    history_text = "\n".join(
        f"[{e['timestamp'][:10]}] Пользователь: {e['user']}\nАгент: {e['assistant'][:200]}..."
        for e in history[-10:]
    )

    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=1024,
        messages=[
            {
                "role": "user",
                "content": f"""Проанализируй эту историю взаимодействий и выдели ключевые паттерны о пользователе.
Верни JSON с полями:
- language: предпочитаемый язык программирования
- style: стиль общения (формальный/неформальный/технический)
- topics: список частых тем
- preferences: особые предпочтения и привычки
- expertise: уровень экспертизы

История:
{history_text}

Верни только валидный JSON без markdown-блоков.""",
            }
        ],
    )

    try:
        profile = json.loads(response.content[0].text)
        save_profile(profile)
        return profile
    except json.JSONDecodeError:
        return load_profile()


def build_system_prompt(profile: dict, history: list[dict]) -> str:
    """Строит системный промпт на основе профиля и истории."""
    parts = [
        "Ты персональный ИИ-ассистент, который учится на запросах пользователя.",
        "Адаптируй свои ответы под стиль и предпочтения пользователя.",
    ]

    if profile:
        parts.append("\n## Что я знаю о пользователе:")
        if profile.get("language"):
            parts.append(f"- Предпочитаемый язык программирования: {profile['language']}")
        if profile.get("style"):
            parts.append(f"- Стиль общения: {profile['style']}")
        if profile.get("expertise"):
            parts.append(f"- Уровень экспертизы: {profile['expertise']}")
        if profile.get("topics"):
            parts.append(f"- Частые темы: {', '.join(profile['topics'])}")
        if profile.get("preferences"):
            parts.append(f"- Предпочтения: {profile['preferences']}")

    if history:
        parts.append("\n## Последние взаимодействия (для контекста):")
        for entry in history[-5:]:
            parts.append(f"Пользователь: {entry['user']}")
            parts.append(f"Ответ: {entry['assistant'][:300]}...")

    return "\n".join(parts)


def chat(messages: list[dict], system: str) -> str:
    """Отправляет запрос в Claude и возвращает ответ."""
    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=4096,
        thinking={"type": "adaptive"},
        system=system,
        messages=messages,
    )
    # Возвращаем только текстовые блоки
    return "\n".join(
        block.text for block in response.content if block.type == "text"
    )


def main():
    print("🤖 Обучающийся агент запущен.")
    print(f"📁 Память хранится в: {MEMORY_DIR}")
    print("Введите 'выход' для завершения, 'профиль' — чтобы посмотреть что я знаю о вас.\n")

    conversation: list[dict] = []
    history = load_history()
    profile = load_profile()

    # Обновляем профиль каждые 5 запросов
    request_count = len(history)

    while True:
        try:
            user_input = input("Вы: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nДо свидания!")
            break

        if not user_input:
            continue

        if user_input.lower() in ("выход", "exit", "quit"):
            print("До свидания!")
            break

        if user_input.lower() == "профиль":
            if profile:
                print("\n📊 Что я знаю о вас:")
                print(json.dumps(profile, ensure_ascii=False, indent=2))
            else:
                print("Профиль ещё не сформирован. Задайте несколько вопросов.")
            print()
            continue

        if user_input.lower() == "история":
            entries = load_history(10)
            print(f"\n📜 Последние {len(entries)} запросов:")
            for e in entries:
                print(f"  [{e['timestamp'][:16]}] {e['user'][:80]}")
            print()
            continue

        # Добавляем запрос в диалог
        conversation.append({"role": "user", "content": user_input})

        # Строим системный промпт
        system = build_system_prompt(profile, history)

        # Получаем ответ
        print("Агент: ", end="", flush=True)
        try:
            response_text = chat(conversation, system)
        except anthropic.APIError as e:
            print(f"\n❌ Ошибка API: {e}")
            conversation.pop()
            continue

        print(response_text)
        print()

        # Добавляем ответ в диалог
        conversation.append({"role": "assistant", "content": response_text})

        # Сохраняем взаимодействие
        save_interaction(user_input, response_text)
        history.append({"timestamp": datetime.now().isoformat(), "user": user_input, "assistant": response_text})

        # Обновляем профиль каждые 5 запросов
        request_count += 1
        if request_count % 5 == 0:
            print("(обновляю профиль...)")
            profile = update_profile(history)

        # Ограничиваем длину диалога в памяти
        if len(conversation) > 20:
            conversation = conversation[-20:]


if __name__ == "__main__":
    main()
