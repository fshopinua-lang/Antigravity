"""
Модуль хранения данных финансового отчёта.
Сохраняет данные в JSON-файл, поддерживает несколько периодов.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

DATA_DIR = Path.home() / ".finance_reports"
DATA_DIR.mkdir(exist_ok=True)


def _data_file(period: str) -> Path:
    return DATA_DIR / f"{period}.json"


def get_periods() -> list[str]:
    """Возвращает список всех сохранённых периодов."""
    return sorted(f.stem for f in DATA_DIR.glob("*.json"))


def load_period(period: str) -> dict:
    """Загружает данные периода. Если нет — возвращает пустую структуру."""
    f = _data_file(period)
    if f.exists():
        return json.loads(f.read_text(encoding="utf-8"))
    return _empty_period(period)


def save_period(period: str, data: dict):
    """Сохраняет данные периода."""
    data["updated_at"] = datetime.now().isoformat()
    _data_file(period).write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _empty_period(period: str) -> dict:
    return {
        "period": period,
        "company": "",
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
        # Производство: список продуктов
        "production": [],
        # Расходы по категориям
        "expenses": {
            "raw_materials": [],      # Сырьё и материалы
            "labor": [],              # Фонд оплаты труда
            "overhead": [],           # Накладные расходы
            "depreciation": [],       # Амортизация
            "administrative": [],     # Административные расходы
            "other": [],              # Прочие расходы
        },
        # Выручка по продуктам
        "revenue": [],
    }


# ─── Производство ─────────────────────────────────────────────────────────────

def add_product(data: dict, name: str, unit: str, plan_qty: float,
                fact_qty: float, cost_per_unit: float) -> dict:
    """Добавляет или обновляет продукт в производстве."""
    for p in data["production"]:
        if p["name"] == name:
            p.update({"unit": unit, "plan_qty": plan_qty,
                       "fact_qty": fact_qty, "cost_per_unit": cost_per_unit})
            return data
    data["production"].append({
        "name": name,
        "unit": unit,
        "plan_qty": plan_qty,
        "fact_qty": fact_qty,
        "cost_per_unit": cost_per_unit,
    })
    return data


def remove_product(data: dict, name: str) -> dict:
    data["production"] = [p for p in data["production"] if p["name"] != name]
    return data


# ─── Расходы ──────────────────────────────────────────────────────────────────

EXPENSE_CATEGORIES = {
    "1": ("raw_materials", "Сырьё и материалы"),
    "2": ("labor", "Фонд оплаты труда"),
    "3": ("overhead", "Накладные расходы"),
    "4": ("depreciation", "Амортизация"),
    "5": ("administrative", "Административные расходы"),
    "6": ("other", "Прочие расходы"),
}

CATEGORY_NAMES = {k: v for k, (k, v) in EXPENSE_CATEGORIES.items()}
CATEGORY_KEYS = {k: key for k, (key, _) in EXPENSE_CATEGORIES.items()}


def add_expense(data: dict, category_key: str, name: str,
                plan_amount: float, fact_amount: float) -> dict:
    """Добавляет или обновляет статью расходов."""
    items = data["expenses"][category_key]
    for item in items:
        if item["name"] == name:
            item.update({"plan_amount": plan_amount, "fact_amount": fact_amount})
            return data
    items.append({"name": name, "plan_amount": plan_amount, "fact_amount": fact_amount})
    return data


def remove_expense(data: dict, category_key: str, name: str) -> dict:
    data["expenses"][category_key] = [
        e for e in data["expenses"][category_key] if e["name"] != name
    ]
    return data


# ─── Выручка ──────────────────────────────────────────────────────────────────

def add_revenue(data: dict, product: str, price: float, qty: float) -> dict:
    """Добавляет или обновляет выручку по продукту."""
    for r in data["revenue"]:
        if r["product"] == product:
            r.update({"price": price, "qty": qty})
            return data
    data["revenue"].append({"product": product, "price": price, "qty": qty})
    return data


def remove_revenue(data: dict, product: str) -> dict:
    data["revenue"] = [r for r in data["revenue"] if r["product"] != product]
    return data


# ─── Расчёты ──────────────────────────────────────────────────────────────────

def calc_production(data: dict) -> list[dict]:
    """Рассчитывает итоги по производству."""
    result = []
    for p in data["production"]:
        plan_cost = p["plan_qty"] * p["cost_per_unit"]
        fact_cost = p["fact_qty"] * p["cost_per_unit"]
        pct = (p["fact_qty"] / p["plan_qty"] * 100) if p["plan_qty"] else 0
        result.append({**p, "plan_cost": plan_cost, "fact_cost": fact_cost, "pct": pct})
    return result


def calc_expenses(data: dict) -> dict:
    """Рассчитывает итоги по расходам."""
    totals = {}
    grand_plan = grand_fact = 0
    for cat_num, (cat_key, cat_name) in EXPENSE_CATEGORIES.items():
        items = data["expenses"][cat_key]
        plan = sum(i["plan_amount"] for i in items)
        fact = sum(i["fact_amount"] for i in items)
        grand_plan += plan
        grand_fact += fact
        totals[cat_key] = {"name": cat_name, "items": items, "plan": plan, "fact": fact}
    totals["_total"] = {"plan": grand_plan, "fact": grand_fact}
    return totals


def calc_revenue(data: dict) -> dict:
    """Рассчитывает итоги по выручке."""
    items = [{"product": r["product"], "price": r["price"],
              "qty": r["qty"], "total": r["price"] * r["qty"]}
             for r in data["revenue"]]
    return {"items": items, "total": sum(i["total"] for i in items)}


def calc_pnl(data: dict) -> dict:
    """Считает P&L (прибыль и убытки)."""
    revenue = calc_revenue(data)
    expenses = calc_expenses(data)
    prod = calc_production(data)

    total_revenue = revenue["total"]
    total_cost_of_goods = sum(p["fact_cost"] for p in prod)  # себестоимость продукции
    total_expenses_fact = expenses["_total"]["fact"]

    gross_profit = total_revenue - total_cost_of_goods
    operating_profit = gross_profit - (total_expenses_fact - total_cost_of_goods)
    net_profit = operating_profit  # упрощённо

    gross_margin = (gross_profit / total_revenue * 100) if total_revenue else 0
    net_margin = (net_profit / total_revenue * 100) if total_revenue else 0

    return {
        "revenue": total_revenue,
        "cost_of_goods": total_cost_of_goods,
        "gross_profit": gross_profit,
        "gross_margin": gross_margin,
        "total_expenses": total_expenses_fact,
        "operating_profit": operating_profit,
        "net_profit": net_profit,
        "net_margin": net_margin,
    }
