#!/usr/bin/env python3
"""
Агент для работы с файлами выгрузки и таблицами Excel.
Умеет читать, анализировать, фильтровать, преобразовывать и создавать Excel/CSV файлы.
"""

import json
import os
import sys
from pathlib import Path

import anthropic
import pandas as pd
from tabulate import tabulate

client = anthropic.Anthropic()

# ─── Инструменты агента ──────────────────────────────────────────────────────

def read_file(path: str, sheet: str = None, rows: int = 100) -> dict:
    """Читает Excel, CSV, JSON или другой файл выгрузки."""
    p = Path(path)
    if not p.exists():
        return {"error": f"Файл не найден: {path}"}

    try:
        ext = p.suffix.lower()

        if ext in (".xlsx", ".xls", ".xlsm"):
            if sheet:
                df = pd.read_excel(path, sheet_name=sheet, nrows=rows)
            else:
                # Читаем все листы
                xl = pd.ExcelFile(path)
                sheets = xl.sheet_names
                df = pd.read_excel(path, sheet_name=sheets[0], nrows=rows)
                return {
                    "sheets": sheets,
                    "active_sheet": sheets[0],
                    "shape": df.shape,
                    "columns": list(df.columns),
                    "dtypes": {col: str(dt) for col, dt in df.dtypes.items()},
                    "preview": df.head(10).to_dict(orient="records"),
                    "nulls": df.isnull().sum().to_dict(),
                }

        elif ext == ".csv":
            # Определяем разделитель автоматически
            df = pd.read_csv(path, sep=None, engine="python", nrows=rows, encoding_errors="replace")

        elif ext == ".json":
            df = pd.read_json(path)
            df = df.head(rows)

        elif ext in (".tsv", ".txt"):
            df = pd.read_csv(path, sep="\t", nrows=rows, encoding_errors="replace")

        else:
            return {"error": f"Неподдерживаемый формат: {ext}"}

        return {
            "shape": df.shape,
            "columns": list(df.columns),
            "dtypes": {col: str(dt) for col, dt in df.dtypes.items()},
            "preview": df.head(10).to_dict(orient="records"),
            "nulls": df.isnull().sum().to_dict(),
        }

    except Exception as e:
        return {"error": str(e)}


def analyze_file(path: str, sheet: str = None) -> dict:
    """Полный статистический анализ файла."""
    p = Path(path)
    if not p.exists():
        return {"error": f"Файл не найден: {path}"}

    try:
        ext = p.suffix.lower()
        if ext in (".xlsx", ".xls", ".xlsm"):
            df = pd.read_excel(path, sheet_name=sheet or 0)
        elif ext == ".csv":
            df = pd.read_csv(path, sep=None, engine="python", encoding_errors="replace")
        elif ext == ".json":
            df = pd.read_json(path)
        else:
            return {"error": f"Неподдерживаемый формат: {ext}"}

        result = {
            "rows": len(df),
            "columns": len(df.columns),
            "column_names": list(df.columns),
            "dtypes": {col: str(dt) for col, dt in df.dtypes.items()},
            "nulls": df.isnull().sum().to_dict(),
            "duplicates": int(df.duplicated().sum()),
        }

        # Статистика числовых столбцов
        numeric = df.select_dtypes(include="number")
        if not numeric.empty:
            desc = numeric.describe().round(2)
            result["numeric_stats"] = desc.to_dict()

        # Топ значений категориальных столбцов
        categorical = df.select_dtypes(include=["object", "category"])
        top_values = {}
        for col in categorical.columns[:10]:
            top_values[col] = df[col].value_counts().head(5).to_dict()
        result["top_values"] = top_values

        return result

    except Exception as e:
        return {"error": str(e)}


def filter_data(path: str, filters: dict, sheet: str = None) -> dict:
    """Фильтрует данные по условиям. filters: {"колонка": {"op": ">", "value": 100}}"""
    p = Path(path)
    if not p.exists():
        return {"error": f"Файл не найден: {path}"}

    try:
        ext = p.suffix.lower()
        if ext in (".xlsx", ".xls", ".xlsm"):
            df = pd.read_excel(path, sheet_name=sheet or 0)
        elif ext == ".csv":
            df = pd.read_csv(path, sep=None, engine="python", encoding_errors="replace")
        else:
            return {"error": f"Неподдерживаемый формат: {ext}"}

        original_len = len(df)
        for col, condition in filters.items():
            if col not in df.columns:
                return {"error": f"Столбец '{col}' не найден"}
            op = condition.get("op", "==")
            val = condition.get("value")
            if op == "==":
                df = df[df[col] == val]
            elif op == "!=":
                df = df[df[col] != val]
            elif op == ">":
                df = df[df[col] > val]
            elif op == ">=":
                df = df[df[col] >= val]
            elif op == "<":
                df = df[df[col] < val]
            elif op == "<=":
                df = df[df[col] <= val]
            elif op == "contains":
                df = df[df[col].astype(str).str.contains(str(val), case=False, na=False)]
            elif op == "in":
                df = df[df[col].isin(val)]

        return {
            "original_rows": original_len,
            "filtered_rows": len(df),
            "preview": df.head(20).to_dict(orient="records"),
        }

    except Exception as e:
        return {"error": str(e)}


def run_formula(path: str, formula: str, sheet: str = None) -> dict:
    """Выполняет pandas-код на датафрейме. formula — строка Python-кода."""
    p = Path(path)
    if not p.exists():
        return {"error": f"Файл не найден: {path}"}

    try:
        ext = p.suffix.lower()
        if ext in (".xlsx", ".xls", ".xlsm"):
            df = pd.read_excel(path, sheet_name=sheet or 0)
        elif ext == ".csv":
            df = pd.read_csv(path, sep=None, engine="python", encoding_errors="replace")
        elif ext == ".json":
            df = pd.read_json(path)
        else:
            return {"error": f"Неподдерживаемый формат: {ext}"}

        # Выполняем код в изолированном пространстве
        local_vars = {"df": df, "pd": pd, "result": None}
        exec(formula, {"__builtins__": {}}, local_vars)  # noqa: S102

        result = local_vars.get("result", local_vars.get("df"))

        if isinstance(result, pd.DataFrame):
            return {"type": "dataframe", "shape": result.shape, "data": result.head(50).to_dict(orient="records")}
        elif isinstance(result, pd.Series):
            return {"type": "series", "data": result.head(50).to_dict()}
        else:
            return {"type": "value", "data": str(result)}

    except Exception as e:
        return {"error": str(e)}


def save_file(path: str, data: list[dict], output_path: str, sheet_name: str = "Лист1") -> dict:
    """Сохраняет данные в Excel или CSV."""
    try:
        df = pd.DataFrame(data)
        ext = Path(output_path).suffix.lower()

        if ext in (".xlsx", ".xlsm"):
            with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
                df.to_excel(writer, sheet_name=sheet_name, index=False)
                # Автоширина столбцов
                ws = writer.sheets[sheet_name]
                for col in ws.columns:
                    max_len = max(len(str(cell.value or "")) for cell in col)
                    ws.column_dimensions[col[0].column_letter].width = min(max_len + 2, 50)
        elif ext == ".csv":
            df.to_csv(output_path, index=False, encoding="utf-8-sig")
        elif ext == ".json":
            df.to_json(output_path, orient="records", ensure_ascii=False, indent=2)
        else:
            return {"error": f"Неподдерживаемый формат: {ext}"}

        return {"saved": output_path, "rows": len(df), "columns": list(df.columns)}

    except Exception as e:
        return {"error": str(e)}


def list_sheets(path: str) -> dict:
    """Возвращает список листов Excel-файла."""
    try:
        xl = pd.ExcelFile(path)
        return {"sheets": xl.sheet_names}
    except Exception as e:
        return {"error": str(e)}


# ─── Схемы инструментов ──────────────────────────────────────────────────────

TOOLS = [
    {
        "name": "read_file",
        "description": "Читает файл (Excel, CSV, JSON, TSV) и показывает структуру и первые строки.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Путь к файлу"},
                "sheet": {"type": "string", "description": "Название листа (для Excel)"},
                "rows": {"type": "integer", "description": "Максимальное количество строк для чтения", "default": 100},
            },
            "required": ["path"],
        },
    },
    {
        "name": "analyze_file",
        "description": "Полный статистический анализ файла: типы данных, статистика, пустые значения, дубликаты, топ значений.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Путь к файлу"},
                "sheet": {"type": "string", "description": "Название листа (для Excel)"},
            },
            "required": ["path"],
        },
    },
    {
        "name": "filter_data",
        "description": "Фильтрует данные по условиям.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Путь к файлу"},
                "filters": {
                    "type": "object",
                    "description": 'Условия фильтрации. Пример: {"Сумма": {"op": ">", "value": 1000}, "Статус": {"op": "==", "value": "Оплачено"}}. Операторы: ==, !=, >, >=, <, <=, contains, in',
                },
                "sheet": {"type": "string", "description": "Название листа (для Excel)"},
            },
            "required": ["path", "filters"],
        },
    },
    {
        "name": "run_formula",
        "description": "Выполняет вычисления на данных. Переменная df — это датафрейм. Результат записывается в переменную result.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Путь к файлу"},
                "formula": {
                    "type": "string",
                    "description": 'Python-код для выполнения. Пример: result = df.groupby("Категория")["Сумма"].sum().reset_index()',
                },
                "sheet": {"type": "string", "description": "Название листа (для Excel)"},
            },
            "required": ["path", "formula"],
        },
    },
    {
        "name": "save_file",
        "description": "Сохраняет данные в Excel (.xlsx), CSV или JSON файл.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Путь к исходному файлу"},
                "data": {"type": "array", "items": {"type": "object"}, "description": "Данные для сохранения"},
                "output_path": {"type": "string", "description": "Путь для сохранения результата"},
                "sheet_name": {"type": "string", "description": "Название листа Excel", "default": "Лист1"},
            },
            "required": ["path", "data", "output_path"],
        },
    },
    {
        "name": "list_sheets",
        "description": "Показывает список листов в Excel-файле.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Путь к Excel-файлу"},
            },
            "required": ["path"],
        },
    },
]

TOOL_FUNCTIONS = {
    "read_file": read_file,
    "analyze_file": analyze_file,
    "filter_data": filter_data,
    "run_formula": run_formula,
    "save_file": save_file,
    "list_sheets": list_sheets,
}

SYSTEM_PROMPT = """Ты эксперт по анализу данных и работе с таблицами.
Ты умеешь работать с файлами Excel (.xlsx, .xls), CSV, JSON и другими форматами выгрузки данных.

Твои возможности:
- Читать и анализировать структуру файлов
- Вычислять статистику (суммы, средние, минимумы, максимумы)
- Фильтровать и группировать данные
- Находить дубликаты и пустые значения
- Создавать сводные таблицы
- Сохранять результаты в новые файлы

При работе с данными:
1. Сначала прочитай файл, чтобы понять его структуру
2. Используй точные названия столбцов из файла
3. Объясняй результаты понятно, выделяй ключевые инсайты
4. Если нужно сохранить результат — предложи сохранить в новый файл

Отвечай на русском языке."""


# ─── Основной цикл агента ────────────────────────────────────────────────────

def run_agent(user_message: str, messages: list[dict]) -> str:
    """Запускает агентный цикл с инструментами."""
    messages.append({"role": "user", "content": user_message})

    while True:
        response = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages,
        )

        # Добавляем ответ ассистента
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "end_turn":
            # Возвращаем текстовый ответ
            return "\n".join(b.text for b in response.content if b.type == "text")

        if response.stop_reason == "tool_use":
            # Выполняем инструменты
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    print(f"  🔧 [{block.name}] {json.dumps(block.input, ensure_ascii=False)[:100]}...")
                    fn = TOOL_FUNCTIONS.get(block.name)
                    if fn:
                        result = fn(**block.input)
                    else:
                        result = {"error": f"Инструмент {block.name} не найден"}

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(result, ensure_ascii=False, default=str),
                    })

            messages.append({"role": "user", "content": tool_results})
        else:
            break

    return "Нет ответа"


def main():
    print("📊 Excel-агент запущен.")
    print("Укажите путь к файлу и задайте вопрос.")
    print("Примеры:")
    print("  • Прочитай файл data.xlsx и покажи структуру")
    print("  • Посчитай сумму по столбцу 'Сумма' из sales.csv")
    print("  • Найди дубликаты в файле clients.xlsx")
    print("  • Сделай сводную таблицу по категориям и сохрани в result.xlsx")
    print("\nВведите 'выход' для завершения.\n")

    messages: list[dict] = []

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

        print()
        try:
            answer = run_agent(user_input, messages)
            print(f"Агент: {answer}\n")
        except anthropic.APIError as e:
            print(f"❌ Ошибка API: {e}\n")
            messages.pop()  # убираем неудавшийся запрос

        # Ограничиваем историю
        if len(messages) > 40:
            messages = messages[-40:]


if __name__ == "__main__":
    main()
