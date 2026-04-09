import anyio
from claude_agent_sdk import query, ClaudeAgentOptions, ResultMessage, SystemMessage


async def main():
    print("Агент для работы с файлами запущен. Введите задачу (или 'выход' для завершения).\n")

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
                allowed_tools=["Read", "Write", "Edit", "Glob", "Grep", "Bash"],
                permission_mode="acceptEdits",
            ),
        ):
            if isinstance(message, ResultMessage):
                print(f"\nРезультат: {message.result}\n")
            elif isinstance(message, SystemMessage) and message.subtype == "init":
                session_id = message.data.get("session_id", "")
                print(f"Сессия: {session_id}\n")


if __name__ == "__main__":
    anyio.run(main)
