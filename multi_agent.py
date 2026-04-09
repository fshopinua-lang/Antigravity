import anyio
from claude_agent_sdk import (
    query,
    ClaudeAgentOptions,
    AgentDefinition,
    ResultMessage,
    SystemMessage,
)


async def main():
    print("Мульти-агент запущен. Введите задачу (или 'выход' для завершения).\n")

    while True:
        prompt = input("Задача: ").strip()
        if prompt.lower() in ("выход", "exit", "quit"):
            print("Завершение работы.")
            break
        if not prompt:
            continue

        print()
        async for message in query(
            prompt=prompt,
            options=ClaudeAgentOptions(
                cwd=".",
                allowed_tools=["Read", "Write", "Edit", "Glob", "Grep", "Bash", "Agent"],
                permission_mode="acceptEdits",
                agents={
                    # Агент для анализа кода
                    "code-analyzer": AgentDefinition(
                        description="Анализирует код — структуру, качество, архитектуру.",
                        prompt=(
                            "Ты опытный code reviewer. "
                            "Анализируй структуру файлов, читаемость кода и соблюдение паттернов. "
                            "Давай конкретные рекомендации с указанием файлов и строк."
                        ),
                        tools=["Read", "Glob", "Grep"],
                    ),
                    # Агент для проверки безопасности
                    "security-reviewer": AgentDefinition(
                        description="Ищет уязвимости: SQL-инъекции, XSS, утечки секретов, небезопасные зависимости.",
                        prompt=(
                            "Ты эксперт по безопасности. "
                            "Ищи SQL-инъекции, XSS, хардкод паролей/токенов, небезопасные импорты. "
                            "Для каждой проблемы укажи: файл, строку, описание угрозы и как исправить."
                        ),
                        tools=["Read", "Glob", "Grep"],
                    ),
                    # Агент для работы с файлами
                    "file-manager": AgentDefinition(
                        description="Создаёт, редактирует и организует файлы проекта.",
                        prompt=(
                            "Ты помощник по работе с файлами. "
                            "Создавай, редактируй и организуй файлы аккуратно. "
                            "Всегда сначала читай существующий файл перед изменением."
                        ),
                        tools=["Read", "Write", "Edit", "Glob"],
                    ),
                    # Агент для тестирования
                    "test-runner": AgentDefinition(
                        description="Запускает тесты и анализирует результаты.",
                        prompt=(
                            "Ты QA-инженер. "
                            "Запускай тесты, анализируй ошибки и предлагай исправления. "
                            "Сообщай о провалах с точным указанием причины."
                        ),
                        tools=["Read", "Bash", "Glob"],
                    ),
                },
            ),
        ):
            if isinstance(message, ResultMessage):
                print(f"\nРезультат: {message.result}\n")
            elif isinstance(message, SystemMessage) and message.subtype == "init":
                session_id = message.data.get("session_id", "")
                print(f"Сессия: {session_id}\n")


if __name__ == "__main__":
    anyio.run(main)
