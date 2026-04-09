#!/usr/bin/env python3
"""
Программа финансового отчёта: Производство и Расходы.
Интерактивное меню для ввода данных и генерации Excel-отчётов.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from data_store import (EXPENSE_CATEGORIES, add_expense, add_product,
                        add_revenue, calc_expenses, calc_pnl, calc_production,
                        calc_revenue, get_periods, load_period, remove_expense,
                        remove_product, remove_revenue, save_period)
from report_generator import generate_report


# ─── Утилиты ввода ────────────────────────────────────────────────────────────

def ask(prompt: str, default: str = "") -> str:
    val = input(f"  {prompt}{f' [{default}]' if default else ''}: ").strip()
    return val if val else default

def ask_float(prompt: str, default: float = 0.0) -> float:
    while True:
        try:
            val = ask(prompt, str(default))
            return float(val.replace(",", ".").replace(" ", ""))
        except ValueError:
            print("  ❌ Введите число.")

def ask_int(prompt: str, default: int = 0) -> int:
    while True:
        try:
            return int(ask(prompt, str(default)))
        except ValueError:
            print("  ❌ Введите целое число.")

def divider(char="─", n=55):
    print(char * n)

def header(title: str):
    print()
    divider("═")
    print(f"  {title}")
    divider("═")

def section(title: str):
    print()
    divider()
    print(f"  {title}")
    divider()


# ─── Выбор / создание периода ─────────────────────────────────────────────────

def select_period() -> tuple[str, dict]:
    header("ВЫБОР ПЕРИОДА")
    periods = get_periods()
    if periods:
        print("  Существующие периоды:")
        for i, p in enumerate(periods, 1):
            print(f"    {i}. {p}")
        print(f"    {len(periods)+1}. Создать новый период")
        choice = ask_int("Выберите номер", len(periods) + 1)
        if 1 <= choice <= len(periods):
            period = periods[choice - 1]
            data = load_period(period)
            print(f"  ✅ Загружен период: {period}")
            return period, data

    period = ask("Введите название периода (например: Январь 2025)")
    if not period:
        period = "Период"
    data = load_period(period)
    company = ask("Название предприятия", data.get("company", ""))
    data["company"] = company
    print(f"  ✅ Период создан: {period}")
    return period, data


# ─── Производство ─────────────────────────────────────────────────────────────

def menu_production(period: str, data: dict):
    while True:
        section(f"ПРОИЗВОДСТВО  |  {period}")
        prod = calc_production(data)
        if prod:
            print(f"  {'Продукт':<20} {'Ед.':<6} {'План':>10} {'Факт':>10} {'%':>7} {'Ст-ть ед.':>12}")
            divider()
            for p in prod:
                print(f"  {p['name']:<20} {p['unit']:<6} {p['plan_qty']:>10,.0f} "
                      f"{p['fact_qty']:>10,.0f} {p['pct']:>6.1f}% {p['cost_per_unit']:>12,.2f}")
        else:
            print("  (нет данных)")

        print()
        print("  1. Добавить / изменить продукт")
        print("  2. Удалить продукт")
        print("  0. Назад")
        ch = ask("Выбор", "0")

        if ch == "1":
            print()
            name = ask("Название продукта")
            if not name:
                continue
            unit = ask("Единица измерения (шт, кг, л и т.д.)", "шт")
            plan_qty = ask_float("Плановое количество")
            fact_qty = ask_float("Фактическое количество")
            cost = ask_float("Себестоимость единицы (₽)")
            add_product(data, name, unit, plan_qty, fact_qty, cost)
            save_period(period, data)
            print("  ✅ Сохранено.")

        elif ch == "2":
            name = ask("Название продукта для удаления")
            remove_product(data, name)
            save_period(period, data)
            print("  ✅ Удалено.")

        elif ch == "0":
            break


# ─── Расходы ──────────────────────────────────────────────────────────────────

def menu_expenses(period: str, data: dict):
    while True:
        section(f"РАСХОДЫ  |  {period}")
        exp = calc_expenses(data)
        for _, (cat_key, cat_name) in EXPENSE_CATEGORIES.items():
            cat = exp[cat_key]
            print(f"\n  📂 {cat_name}: план {cat['plan']:,.2f} ₽  /  факт {cat['fact']:,.2f} ₽")
            for item in cat["items"]:
                dev = item["fact_amount"] - item["plan_amount"]
                sign = "+" if dev > 0 else ""
                print(f"     • {item['name']:<25} план {item['plan_amount']:>12,.2f}  "
                      f"факт {item['fact_amount']:>12,.2f}  откл {sign}{dev:,.2f}")

        grand = exp["_total"]
        print(f"\n  ИТОГО: план {grand['plan']:,.2f} ₽  /  факт {grand['fact']:,.2f} ₽")

        print()
        print("  1. Добавить / изменить статью расходов")
        print("  2. Удалить статью расходов")
        print("  0. Назад")
        ch = ask("Выбор", "0")

        if ch == "1":
            print()
            print("  Категории:")
            for num, (_, cat_name) in EXPENSE_CATEGORIES.items():
                print(f"    {num}. {cat_name}")
            cat_num = ask("Выберите категорию (1-6)", "1")
            if cat_num not in EXPENSE_CATEGORIES:
                print("  ❌ Неверный номер.")
                continue
            cat_key, cat_name = EXPENSE_CATEGORIES[cat_num]
            name = ask(f"Статья расходов ({cat_name})")
            if not name:
                continue
            plan = ask_float("Плановая сумма (₽)")
            fact = ask_float("Фактическая сумма (₽)")
            add_expense(data, cat_key, name, plan, fact)
            save_period(period, data)
            print("  ✅ Сохранено.")

        elif ch == "2":
            print()
            print("  Категории:")
            for num, (_, cat_name) in EXPENSE_CATEGORIES.items():
                print(f"    {num}. {cat_name}")
            cat_num = ask("Категория (1-6)", "1")
            if cat_num not in EXPENSE_CATEGORIES:
                continue
            cat_key, _ = EXPENSE_CATEGORIES[cat_num]
            name = ask("Статья для удаления")
            remove_expense(data, cat_key, name)
            save_period(period, data)
            print("  ✅ Удалено.")

        elif ch == "0":
            break


# ─── Выручка ──────────────────────────────────────────────────────────────────

def menu_revenue(period: str, data: dict):
    while True:
        section(f"ВЫРУЧКА  |  {period}")
        rev = calc_revenue(data)
        if rev["items"]:
            print(f"  {'Продукт':<25} {'Цена':>12} {'Кол-во':>10} {'Выручка':>15}")
            divider()
            for item in rev["items"]:
                print(f"  {item['product']:<25} {item['price']:>12,.2f} "
                      f"{item['qty']:>10,.2f} {item['total']:>15,.2f}")
            print(f"\n  ИТОГО: {rev['total']:,.2f} ₽")
        else:
            print("  (нет данных)")

        print()
        print("  1. Добавить / изменить выручку")
        print("  2. Удалить строку выручки")
        print("  0. Назад")
        ch = ask("Выбор", "0")

        if ch == "1":
            print()
            product = ask("Продукт / услуга")
            if not product:
                continue
            price = ask_float("Цена реализации (₽)")
            qty = ask_float("Количество реализовано")
            add_revenue(data, product, price, qty)
            save_period(period, data)
            print(f"  ✅ Выручка: {price * qty:,.2f} ₽")

        elif ch == "2":
            product = ask("Продукт для удаления")
            remove_revenue(data, product)
            save_period(period, data)
            print("  ✅ Удалено.")

        elif ch == "0":
            break


# ─── Сводка P&L ───────────────────────────────────────────────────────────────

def show_pnl(period: str, data: dict):
    header(f"P&L  |  {period}")
    pnl = calc_pnl(data)

    def row(label, val, bold=False):
        prefix = "►" if bold else " "
        if isinstance(val, float):
            sign = "+" if val > 0 else ""
            color = "✅" if val >= 0 else "❌"
            print(f"  {prefix} {label:<30} {color} {sign}{val:>14,.2f} ₽")
        else:
            print(f"  {prefix} {label:<30}     {val:>15}")

    row("Выручка от реализации",   pnl["revenue"])
    row("Себестоимость продукции",  pnl["cost_of_goods"])
    divider()
    row("ВАЛОВАЯ ПРИБЫЛЬ",         pnl["gross_profit"],    bold=True)
    row(f"  Валовая маржа",        f"{pnl['gross_margin']:.1f}%")
    divider()
    row("Операционные расходы",    pnl["total_expenses"])
    divider()
    row("ОПЕРАЦИОННАЯ ПРИБЫЛЬ",    pnl["operating_profit"], bold=True)
    divider("═")
    row("ЧИСТАЯ ПРИБЫЛЬ",         pnl["net_profit"],       bold=True)
    row("Чистая маржа",            f"{pnl['net_margin']:.1f}%")

    input("\n  Нажмите Enter...")


# ─── Главное меню ─────────────────────────────────────────────────────────────

def main():
    print()
    print("╔══════════════════════════════════════════════════╗")
    print("║    📊 ФИНАНСОВЫЙ ОТЧЁТ: ПРОИЗВОДСТВО И РАСХОДЫ  ║")
    print("╚══════════════════════════════════════════════════╝")

    period, data = select_period()

    while True:
        header(f"ГЛАВНОЕ МЕНЮ  |  {data.get('company', '') or period}")

        # Быстрая сводка
        pnl = calc_pnl(data)
        prod_count = len(data["production"])
        exp_count = sum(len(v) for v in data["expenses"].values())
        rev_total = pnl["revenue"]
        profit = pnl["net_profit"]
        profit_str = f"{'✅' if profit >= 0 else '❌'} {profit:+,.2f} ₽"

        print(f"  Период: {period}")
        print(f"  Продуктов: {prod_count}  |  Статей расходов: {exp_count}")
        print(f"  Выручка: {rev_total:,.2f} ₽  |  Прибыль: {profit_str}")
        divider()
        print("  1. 🏭  Производство")
        print("  2. 💸  Расходы")
        print("  3. 💰  Выручка")
        print("  4. 📈  Отчёт P&L (прибыли и убытки)")
        print("  5. 📥  Сгенерировать Excel-отчёт")
        print("  6. 🔄  Сменить период")
        print("  0. 🚪  Выход")
        print()
        ch = ask("Выбор", "0")

        if ch == "1":
            menu_production(period, data)
        elif ch == "2":
            menu_expenses(period, data)
        elif ch == "3":
            menu_revenue(period, data)
        elif ch == "4":
            show_pnl(period, data)
        elif ch == "5":
            print()
            default_path = f"Финотчёт_{period.replace(' ', '_')}.xlsx"
            out = ask("Путь для сохранения", default_path)
            try:
                path = generate_report(data, out)
                print(f"  ✅ Отчёт сохранён: {path}")
            except Exception as e:
                print(f"  ❌ Ошибка: {e}")
            input("  Нажмите Enter...")
        elif ch == "6":
            period, data = select_period()
        elif ch == "0":
            print("\n  До свидания!\n")
            break


if __name__ == "__main__":
    main()
