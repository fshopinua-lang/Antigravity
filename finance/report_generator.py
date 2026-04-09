"""
Генератор финансовых отчётов в Excel с форматированием.
"""

from datetime import datetime
from pathlib import Path

from openpyxl import Workbook
from openpyxl.chart import BarChart, PieChart, Reference
from openpyxl.styles import (Alignment, Border, Font, GradientFill,
                              PatternFill, Side)
from openpyxl.utils import get_column_letter

from data_store import (EXPENSE_CATEGORIES, calc_expenses, calc_pnl,
                        calc_production, calc_revenue)

# ─── Стили ────────────────────────────────────────────────────────────────────

def _font(bold=False, size=11, color="000000", italic=False):
    return Font(bold=bold, size=size, color=color, italic=italic, name="Calibri")

def _fill(hex_color):
    return PatternFill("solid", fgColor=hex_color)

def _border(style="thin"):
    side = Side(style=style)
    return Border(left=side, right=side, top=side, bottom=side)

def _align(h="center", v="center", wrap=False):
    return Alignment(horizontal=h, vertical=v, wrap_text=wrap)

# Цветовая схема
C_DARK_BLUE  = "1F3864"   # заголовки разделов
C_MID_BLUE   = "2E75B6"   # подзаголовки
C_LIGHT_BLUE = "DEEAF1"   # строки заголовков таблиц
C_ORANGE     = "C55A11"   # итоги
C_LIGHT_GRAY = "F2F2F2"   # зебра
C_GREEN      = "375623"   # положительные значения
C_RED        = "C00000"   # отрицательные значения
C_YELLOW     = "FFD966"   # предупреждения

def _num(val, fmt="#,##0.00"):
    """Форматирует число."""
    return val

def _pct_color(val: float) -> str:
    """Цвет в зависимости от процента выполнения."""
    if val >= 100:
        return C_GREEN
    if val >= 80:
        return "7F6000"
    return C_RED


# ─── Вспомогательные функции ──────────────────────────────────────────────────

def _set_col_widths(ws, widths: dict):
    for col_letter, width in widths.items():
        ws.column_dimensions[col_letter].width = width

def _row_title(ws, row: int, col_start: int, col_end: int,
               text: str, bg: str, font_color="FFFFFF", size=12):
    ws.merge_cells(start_row=row, start_column=col_start,
                   end_row=row, end_column=col_end)
    cell = ws.cell(row=row, column=col_start, value=text)
    cell.font = _font(bold=True, size=size, color=font_color)
    cell.fill = _fill(bg)
    cell.alignment = _align("center", "center")
    cell.border = _border()

def _header_row(ws, row: int, headers: list[str], bg=C_LIGHT_BLUE):
    for col, h in enumerate(headers, 1):
        cell = ws.cell(row=row, column=col, value=h)
        cell.font = _font(bold=True, size=10, color="000000")
        cell.fill = _fill(bg)
        cell.alignment = _align("center", "center", wrap=True)
        cell.border = _border()

def _data_row(ws, row: int, values: list, zebra=False, bold=False,
              align_right_from=2):
    bg = C_LIGHT_GRAY if zebra else "FFFFFF"
    for col, val in enumerate(values, 1):
        cell = ws.cell(row=row, column=col, value=val)
        cell.font = _font(bold=bold, size=10)
        cell.fill = _fill(bg)
        cell.border = _border()
        if isinstance(val, (int, float)) or col >= align_right_from:
            cell.alignment = _align("right", "center")
            if isinstance(val, float):
                cell.number_format = "#,##0.00"
        else:
            cell.alignment = _align("left", "center")

def _total_row(ws, row: int, values: list, bg=C_ORANGE):
    for col, val in enumerate(values, 1):
        cell = ws.cell(row=row, column=col, value=val)
        cell.font = _font(bold=True, size=10, color="FFFFFF")
        cell.fill = _fill(bg)
        cell.border = _border()
        if isinstance(val, float):
            cell.number_format = "#,##0.00"
        cell.alignment = _align("right" if col > 1 else "left", "center")


# ─── Листы отчёта ─────────────────────────────────────────────────────────────

def _sheet_cover(wb: Workbook, data: dict, pnl: dict):
    """Титульный лист — сводка ключевых показателей."""
    ws = wb.active
    ws.title = "Сводка"
    ws.sheet_view.showGridLines = False

    _set_col_widths(ws, {"A": 5, "B": 30, "C": 20, "D": 20, "E": 5})

    # Заголовок
    ws.row_dimensions[1].height = 10
    ws.row_dimensions[2].height = 40
    _row_title(ws, 2, 2, 4,
               f"ФИНАНСОВЫЙ ОТЧЁТ  •  {data.get('company', 'Предприятие')}",
               C_DARK_BLUE, size=16)
    ws.row_dimensions[3].height = 20
    _row_title(ws, 3, 2, 4, f"Период: {data['period']}", C_MID_BLUE, size=11)

    ws.row_dimensions[4].height = 15

    # KPI блок
    kpis = [
        ("💰 Выручка",          pnl["revenue"],          "#FFFFFF"),
        ("🏭 Себестоимость",    pnl["cost_of_goods"],    "#FFFFFF"),
        ("📊 Валовая прибыль",  pnl["gross_profit"],
         C_GREEN if pnl["gross_profit"] >= 0 else C_RED),
        ("📈 Маржа валовая",    f"{pnl['gross_margin']:.1f}%",  "#FFFFFF"),
        ("💼 Всего расходов",   pnl["total_expenses"],   "#FFFFFF"),
        ("✅ Чистая прибыль",   pnl["net_profit"],
         C_GREEN if pnl["net_profit"] >= 0 else C_RED),
        ("📉 Чистая маржа",     f"{pnl['net_margin']:.1f}%",   "#FFFFFF"),
    ]

    row = 5
    for label, value, txt_color in kpis:
        ws.row_dimensions[row].height = 28
        lc = ws.cell(row=row, column=2, value=label)
        lc.font = _font(size=11, bold=True)
        lc.fill = _fill(C_LIGHT_GRAY)
        lc.border = _border()
        lc.alignment = _align("left", "center")

        ws.merge_cells(start_row=row, start_column=3, end_row=row, end_column=4)
        vc = ws.cell(row=row, column=3, value=value)
        vc.font = _font(size=12, bold=True,
                        color=txt_color if txt_color != "#FFFFFF" else "000000")
        vc.fill = _fill(C_LIGHT_GRAY)
        vc.border = _border()
        vc.alignment = _align("right", "center")
        if isinstance(value, float):
            vc.number_format = "#,##0.00 ₽"
        row += 1

    # Дата формирования
    ws.row_dimensions[row + 1].height = 20
    dc = ws.cell(row=row + 1, column=2,
                 value=f"Сформирован: {datetime.now().strftime('%d.%m.%Y %H:%M')}")
    dc.font = _font(italic=True, size=9, color="808080")
    dc.alignment = _align("left")


def _sheet_production(wb: Workbook, data: dict):
    """Лист: Производство."""
    ws = wb.create_sheet("Производство")
    ws.sheet_view.showGridLines = False
    _set_col_widths(ws, {
        "A": 3, "B": 28, "C": 10, "D": 14, "E": 14,
        "F": 12, "G": 16, "H": 16, "I": 14,
    })

    prod = calc_production(data)

    _row_title(ws, 1, 2, 9, "ОТЧЁТ О ПРОИЗВОДСТВЕ", C_DARK_BLUE, size=13)
    _row_title(ws, 2, 2, 9, f"Период: {data['period']}", C_MID_BLUE, size=10)

    headers = ["Продукт", "Ед.", "План (кол-во)", "Факт (кол-во)",
               "Выполн. %", "Цена/ед. (₽)", "План (₽)", "Факт (₽)"]
    _header_row(ws, 4, headers)

    plan_total = fact_total = 0
    for i, p in enumerate(prod):
        row = 5 + i
        pct = p["pct"]
        _data_row(ws, row, [
            p["name"], p["unit"],
            p["plan_qty"], p["fact_qty"],
            f"{pct:.1f}%",
            p["cost_per_unit"],
            p["plan_cost"], p["fact_cost"],
        ], zebra=(i % 2 == 0))
        # Цвет % выполнения
        pct_cell = ws.cell(row=row, column=6)
        pct_cell.font = _font(bold=True, color=_pct_color(pct))
        plan_total += p["plan_cost"]
        fact_total += p["fact_cost"]

    total_row = 5 + len(prod)
    _total_row(ws, total_row, [
        "ИТОГО", "", "", "", "",
        "", plan_total, fact_total,
    ])

    # Заморозить строки заголовков
    ws.freeze_panes = "B5"


def _sheet_expenses(wb: Workbook, data: dict):
    """Лист: Расходы."""
    ws = wb.create_sheet("Расходы")
    ws.sheet_view.showGridLines = False
    _set_col_widths(ws, {
        "A": 3, "B": 32, "C": 18, "D": 18, "E": 16, "F": 3,
    })

    exp = calc_expenses(data)

    _row_title(ws, 1, 2, 5, "ОТЧЁТ О РАСХОДАХ", C_DARK_BLUE, size=13)
    _row_title(ws, 2, 2, 5, f"Период: {data['period']}", C_MID_BLUE, size=10)

    row = 4
    for _, (cat_key, cat_name) in EXPENSE_CATEGORIES.items():
        cat = exp[cat_key]
        # Заголовок категории
        _row_title(ws, row, 2, 5, cat_name.upper(), C_MID_BLUE, size=10)
        row += 1
        _header_row(ws, row, ["Статья расходов", "План (₽)", "Факт (₽)", "Откл. (₽)"])
        row += 1

        for i, item in enumerate(cat["items"]):
            deviation = item["fact_amount"] - item["plan_amount"]
            _data_row(ws, row, [
                item["name"],
                item["plan_amount"],
                item["fact_amount"],
                deviation,
            ], zebra=(i % 2 == 0))
            # Цвет отклонения
            dev_cell = ws.cell(row=row, column=5)
            dev_cell.font = _font(bold=True,
                                  color=C_RED if deviation > 0 else C_GREEN)
            row += 1

        # Итог категории
        dev = cat["fact"] - cat["plan"]
        _total_row(ws, row, [
            f"Итого: {cat_name}",
            cat["plan"], cat["fact"], dev,
        ])
        row += 2

    # Общий итог
    grand = exp["_total"]
    dev = grand["fact"] - grand["plan"]
    ws.row_dimensions[row].height = 22
    _row_title(ws, row, 2, 5, "ИТОГО РАСХОДОВ", C_DARK_BLUE, size=11)
    row += 1
    _total_row(ws, row, ["", grand["plan"], grand["fact"], dev])

    ws.freeze_panes = "B5"


def _sheet_revenue(wb: Workbook, data: dict):
    """Лист: Выручка."""
    ws = wb.create_sheet("Выручка")
    ws.sheet_view.showGridLines = False
    _set_col_widths(ws, {
        "A": 3, "B": 28, "C": 16, "D": 14, "E": 18,
    })

    rev = calc_revenue(data)

    _row_title(ws, 1, 2, 5, "ОТЧЁТ О ВЫРУЧКЕ", C_DARK_BLUE, size=13)
    _row_title(ws, 2, 2, 5, f"Период: {data['period']}", C_MID_BLUE, size=10)
    _header_row(ws, 4, ["Продукт / Услуга", "Цена (₽)", "Кол-во", "Выручка (₽)"])

    for i, item in enumerate(rev["items"]):
        _data_row(ws, 5 + i, [
            item["product"], item["price"],
            item["qty"], item["total"],
        ], zebra=(i % 2 == 0))

    _total_row(ws, 5 + len(rev["items"]), [
        "ИТОГО", "", "", rev["total"],
    ])
    ws.freeze_panes = "B5"


def _sheet_pnl(wb: Workbook, data: dict):
    """Лист: Прибыли и убытки (P&L)."""
    ws = wb.create_sheet("P&L")
    ws.sheet_view.showGridLines = False
    _set_col_widths(ws, {"A": 3, "B": 35, "C": 22, "D": 3})

    pnl = calc_pnl(data)

    _row_title(ws, 1, 2, 3, "ОТЧЁТ О ПРИБЫЛЯХ И УБЫТКАХ", C_DARK_BLUE, size=13)
    _row_title(ws, 2, 2, 3, f"Период: {data['period']}", C_MID_BLUE, size=10)

    rows_data = [
        ("Выручка от реализации",   pnl["revenue"],          False, C_MID_BLUE),
        ("Себестоимость продукции",  pnl["cost_of_goods"],    False, None),
        ("ВАЛОВАЯ ПРИБЫЛЬ",         pnl["gross_profit"],     True,  None),
        (f"  Маржа: {pnl['gross_margin']:.1f}%", "",         False, None),
        ("Операционные расходы",    pnl["total_expenses"],   False, None),
        ("ОПЕРАЦИОННАЯ ПРИБЫЛЬ",    pnl["operating_profit"], True,  None),
        ("ЧИСТАЯ ПРИБЫЛЬ",         pnl["net_profit"],       True,  None),
        (f"  Чистая маржа: {pnl['net_margin']:.1f}%", "",   False, None),
    ]

    row = 4
    for label, value, is_total, bg in rows_data:
        ws.row_dimensions[row].height = 22
        if is_total:
            color = C_GREEN if (isinstance(value, (int, float)) and value >= 0) else C_RED
            _total_row(ws, row, [label, value], bg=color)
        else:
            lc = ws.cell(row=row, column=2, value=label)
            vc = ws.cell(row=row, column=3, value=value)
            lc.font = _font(size=11, bold=bg is not None)
            vc.font = _font(size=11)
            lc.fill = _fill(bg or "FFFFFF")
            vc.fill = _fill(bg or "FFFFFF")
            lc.border = _border()
            vc.border = _border()
            lc.alignment = _align("left", "center")
            vc.alignment = _align("right", "center")
            if isinstance(value, float):
                vc.number_format = "#,##0.00 ₽"
        row += 1


def _sheet_analytics(wb: Workbook, data: dict):
    """Лист: Аналитика — диаграммы структуры расходов."""
    ws = wb.create_sheet("Аналитика")
    ws.sheet_view.showGridLines = False

    exp = calc_expenses(data)
    prod = calc_production(data)

    _row_title(ws, 1, 1, 8, "АНАЛИТИКА", C_DARK_BLUE, size=13)

    # Таблица структуры расходов для диаграммы
    ws.cell(row=3, column=1, value="Категория расходов").font = _font(bold=True)
    ws.cell(row=3, column=2, value="Сумма (₽)").font = _font(bold=True)

    cat_row = 4
    for _, (cat_key, cat_name) in EXPENSE_CATEGORIES.items():
        cat = exp[cat_key]
        ws.cell(row=cat_row, column=1, value=cat_name)
        ws.cell(row=cat_row, column=2, value=cat["fact"])
        cat_row += 1

    # Круговая диаграмма расходов
    pie = PieChart()
    pie.title = "Структура расходов"
    pie.style = 10
    pie.width = 15
    pie.height = 12

    labels = Reference(ws, min_col=1, min_row=4, max_row=cat_row - 1)
    data_ref = Reference(ws, min_col=2, min_row=4, max_row=cat_row - 1)
    pie.add_data(data_ref)
    pie.set_categories(labels)
    ws.add_chart(pie, "D3")

    # Таблица выполнения плана производства
    if prod:
        pr_row = 3
        ws.cell(row=pr_row, column=10, value="Продукт").font = _font(bold=True)
        ws.cell(row=pr_row, column=11, value="План").font = _font(bold=True)
        ws.cell(row=pr_row, column=12, value="Факт").font = _font(bold=True)
        pr_row += 1
        for p in prod:
            ws.cell(row=pr_row, column=10, value=p["name"])
            ws.cell(row=pr_row, column=11, value=p["plan_qty"])
            ws.cell(row=pr_row, column=12, value=p["fact_qty"])
            pr_row += 1

        # Столбчатая диаграмма план/факт
        bar = BarChart()
        bar.type = "col"
        bar.style = 10
        bar.title = "План vs Факт (производство)"
        bar.y_axis.title = "Количество"
        bar.x_axis.title = "Продукт"
        bar.width = 18
        bar.height = 12

        bar_data = Reference(ws, min_col=11, max_col=12, min_row=3, max_row=pr_row - 1)
        cats = Reference(ws, min_col=10, min_row=4, max_row=pr_row - 1)
        bar.add_data(bar_data, titles_from_data=True)
        bar.set_categories(cats)
        ws.add_chart(bar, "J16")


# ─── Главная функция генерации ────────────────────────────────────────────────

def generate_report(data: dict, output_path: str | None = None) -> str:
    """Генерирует Excel-отчёт и возвращает путь к файлу."""
    pnl = calc_pnl(data)

    wb = Workbook()

    _sheet_cover(wb, data, pnl)
    _sheet_production(wb, data)
    _sheet_expenses(wb, data)
    _sheet_revenue(wb, data)
    _sheet_pnl(wb, data)
    _sheet_analytics(wb, data)

    if output_path is None:
        period = data["period"].replace(" ", "_").replace("/", "-")
        output_path = str(Path.cwd() / f"Финотчёт_{period}.xlsx")

    wb.save(output_path)
    return output_path
