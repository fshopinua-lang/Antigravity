#!/usr/bin/env python3
"""Flask веб-приложение: Финансовый отчёт — Производство и Расходы."""

import sys
import json
import threading
import tempfile
import webbrowser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "finance"))

import pandas as pd
from flask import Flask, jsonify, render_template, request, send_file
from data_store import (
    EXPENSE_CATEGORIES, add_expense, add_product, add_revenue,
    calc_expenses, calc_pnl, calc_production, calc_revenue,
    get_periods, load_period, remove_expense, remove_product,
    remove_revenue, save_period,
)
from report_generator import generate_report

app = Flask(__name__)
app.secret_key = "finance-report-secret-2025"


# ─── Страницы ─────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    periods = get_periods()
    return render_template("index.html", periods=periods)


@app.route("/period/<period>")
def dashboard(period):
    data = load_period(period)
    pnl = calc_pnl(data)
    exp_count = sum(len(v) for v in data["expenses"].values())
    return render_template("dashboard.html", period=period, data=data, pnl=pnl, exp_count=exp_count)


@app.route("/period/<period>/production")
def production(period):
    data = load_period(period)
    prod = calc_production(data)
    return render_template("production.html", period=period, prod=prod)


@app.route("/period/<period>/expenses")
def expenses(period):
    data = load_period(period)
    exp = calc_expenses(data)
    categories = {k: v for _, (k, v) in EXPENSE_CATEGORIES.items()}
    return render_template("expenses.html", period=period, exp=exp, categories=categories)


@app.route("/period/<period>/revenue")
def revenue(period):
    data = load_period(period)
    rev = calc_revenue(data)
    return render_template("revenue.html", period=period, rev=rev)


@app.route("/period/<period>/pnl")
def pnl_page(period):
    data = load_period(period)
    pnl = calc_pnl(data)
    exp = calc_expenses(data)
    prod = calc_production(data)
    return render_template("pnl.html", period=period, pnl=pnl, exp=exp, prod=prod)


# ─── API ──────────────────────────────────────────────────────────────────────

@app.route("/api/periods", methods=["GET"])
def api_periods():
    return jsonify(get_periods())


@app.route("/api/periods", methods=["POST"])
def api_create_period():
    body = request.json
    period = body.get("period", "").strip()
    company = body.get("company", "").strip()
    if not period:
        return jsonify({"error": "Укажите название периода"}), 400
    data = load_period(period)
    data["company"] = company
    save_period(period, data)
    return jsonify({"ok": True, "period": period})


@app.route("/api/period/<period>/product", methods=["POST"])
def api_add_product(period):
    b = request.json
    data = load_period(period)
    add_product(data, b["name"], b["unit"],
                float(b["plan_qty"]), float(b["fact_qty"]), float(b["cost_per_unit"]))
    save_period(period, data)
    return jsonify(calc_production(data))


@app.route("/api/period/<period>/product/<name>", methods=["DELETE"])
def api_del_product(period, name):
    data = load_period(period)
    remove_product(data, name)
    save_period(period, data)
    return jsonify({"ok": True})


@app.route("/api/period/<period>/expense", methods=["POST"])
def api_add_expense(period):
    b = request.json
    data = load_period(period)
    add_expense(data, b["category"], b["name"],
                float(b["plan_amount"]), float(b["fact_amount"]))
    save_period(period, data)
    return jsonify(calc_expenses(data))


@app.route("/api/period/<period>/expense/<cat>/<name>", methods=["DELETE"])
def api_del_expense(period, cat, name):
    data = load_period(period)
    remove_expense(data, cat, name)
    save_period(period, data)
    return jsonify({"ok": True})


@app.route("/api/period/<period>/revenue", methods=["POST"])
def api_add_revenue(period):
    b = request.json
    data = load_period(period)
    add_revenue(data, b["product"], float(b["price"]), float(b["qty"]))
    save_period(period, data)
    return jsonify(calc_revenue(data))


@app.route("/api/period/<period>/revenue/<product>", methods=["DELETE"])
def api_del_revenue(period, product):
    data = load_period(period)
    remove_revenue(data, product)
    save_period(period, data)
    return jsonify({"ok": True})


@app.route("/api/period/<period>/pnl")
def api_pnl(period):
    data = load_period(period)
    return jsonify(calc_pnl(data))


@app.route("/period/<period>/import")
def import_page(period):
    return render_template("import.html", period=period)


@app.route("/api/period/<period>/import/upload", methods=["POST"])
def api_import_upload(period):
    if "file" not in request.files:
        return jsonify({"error": "Файл не загружен"}), 400
    f = request.files["file"]
    suffix = Path(f.filename).suffix.lower()
    if suffix not in (".xlsx", ".xls", ".csv"):
        return jsonify({"error": "Поддерживаются только .xlsx, .xls, .csv"}), 400

    tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    f.save(tmp.name)
    tmp.close()

    try:
        if suffix == ".csv":
            df = pd.read_csv(tmp.name, nrows=6)
            sheet_names = ["Лист1"]
            sheets = {"Лист1": [str(c) for c in df.columns.tolist()]}
            preview = {"Лист1": df.fillna("").astype(str).values.tolist()}
        else:
            xl = pd.ExcelFile(tmp.name)
            sheet_names = xl.sheet_names
            sheets, preview = {}, {}
            for s in sheet_names:
                df = xl.parse(s, nrows=6)
                sheets[s] = [str(c) for c in df.columns.tolist()]
                preview[s] = df.fillna("").astype(str).values.tolist()
        return jsonify({"tmp_path": tmp.name, "sheet_names": sheet_names,
                        "sheets": sheets, "preview": preview})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/period/<period>/import/apply", methods=["POST"])
def api_import_apply(period):
    b = request.json
    tmp_path = b.get("tmp_path", "")
    mappings = b.get("mappings", {})

    if not Path(tmp_path).exists():
        return jsonify({"error": "Временный файл не найден, загрузите снова"}), 400

    try:
        suffix = Path(tmp_path).suffix.lower()
        if suffix == ".csv":
            dfs = {"Лист1": pd.read_csv(tmp_path)}
        else:
            xl = pd.ExcelFile(tmp_path)
            dfs = {s: xl.parse(s) for s in xl.sheet_names}

        data = load_period(period)
        imported = {"production": 0, "expenses": 0, "revenue": 0}

        # Production
        if "production" in mappings:
            m = mappings["production"]
            df = dfs[m["sheet"]].fillna("")
            cols = m["cols"]
            for _, row in df.iterrows():
                name = str(row.get(cols.get("name", ""), "")).strip()
                if not name:
                    continue
                add_product(data, name,
                    str(row.get(cols.get("unit", ""), "шт")).strip() or "шт",
                    _to_float(row.get(cols.get("plan_qty", ""), 0)),
                    _to_float(row.get(cols.get("fact_qty", ""), 0)),
                    _to_float(row.get(cols.get("cost_per_unit", ""), 0)))
                imported["production"] += 1

        # Expenses
        if "expenses" in mappings:
            m = mappings["expenses"]
            df = dfs[m["sheet"]].fillna("")
            cols = m["cols"]
            valid_cats = set(data["expenses"].keys())
            for _, row in df.iterrows():
                name = str(row.get(cols.get("name", ""), "")).strip()
                if not name:
                    continue
                cat = str(row.get(cols.get("category", ""), "other")).strip()
                cat_key = cat if cat in valid_cats else "other"
                add_expense(data, cat_key, name,
                    _to_float(row.get(cols.get("plan_amount", ""), 0)),
                    _to_float(row.get(cols.get("fact_amount", ""), 0)))
                imported["expenses"] += 1

        # Revenue
        if "revenue" in mappings:
            m = mappings["revenue"]
            df = dfs[m["sheet"]].fillna("")
            cols = m["cols"]
            for _, row in df.iterrows():
                product = str(row.get(cols.get("product", ""), "")).strip()
                if not product:
                    continue
                add_revenue(data, product,
                    _to_float(row.get(cols.get("price", ""), 0)),
                    _to_float(row.get(cols.get("qty", ""), 0)))
                imported["revenue"] += 1

        save_period(period, data)
        return jsonify({"ok": True, "imported": imported})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


def _to_float(val) -> float:
    try:
        return float(str(val).replace(",", ".").replace(" ", "") or 0)
    except (ValueError, TypeError):
        return 0.0


@app.route("/api/period/<period>/report")
def api_report(period):
    data = load_period(period)
    out = Path(f"/tmp/Финотчёт_{period.replace(' ', '_')}.xlsx")
    generate_report(data, str(out))
    return send_file(str(out), as_attachment=True,
                     download_name=out.name,
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@app.route("/api/period/<period>/charts")
def api_charts(period):
    data = load_period(period)
    exp = calc_expenses(data)
    prod = calc_production(data)
    pnl = calc_pnl(data)

    expense_chart = {
        "labels": [v for _, (_, v) in EXPENSE_CATEGORIES.items()],
        "values": [exp[k]["fact"] for _, (k, _) in EXPENSE_CATEGORIES.items()],
    }
    production_chart = {
        "labels": [p["name"] for p in prod],
        "plan": [p["plan_qty"] for p in prod],
        "fact": [p["fact_qty"] for p in prod],
    }
    pnl_chart = {
        "labels": ["Выручка", "Себестоимость", "Валовая прибыль", "Чистая прибыль"],
        "values": [pnl["revenue"], pnl["cost_of_goods"],
                   pnl["gross_profit"], pnl["net_profit"]],
    }
    return jsonify({
        "expense": expense_chart,
        "production": production_chart,
        "pnl": pnl_chart,
    })


def open_browser():
    webbrowser.open("http://127.0.0.1:5050")


if __name__ == "__main__":
    threading.Timer(1.0, open_browser).start()
    app.run(host="127.0.0.1", port=5050, debug=False)
