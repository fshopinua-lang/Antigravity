#!/usr/bin/env python3
"""
Агент-маркетолог: глубокий анализ Google Ads и Meta Ads, e-commerce, настройка рекламы.
"""

import json
import math
from pathlib import Path

import anthropic
import pandas as pd

client = anthropic.Anthropic()

# ─── Инструменты ─────────────────────────────────────────────────────────────

def read_ads_report(path: str, sheet: str = None) -> dict:
    """Читает выгрузку из Google Ads, Meta Ads или любой рекламной платформы (Excel, CSV)."""
    p = Path(path)
    if not p.exists():
        return {"error": f"Файл не найден: {path}"}
    try:
        ext = p.suffix.lower()
        if ext in (".xlsx", ".xls"):
            xl = pd.ExcelFile(path)
            sheet_names = xl.sheet_names
            target = sheet or sheet_names[0]
            df = pd.read_excel(path, sheet_name=target)
            return {
                "sheets": sheet_names,
                "active_sheet": target,
                "rows": len(df),
                "columns": list(df.columns),
                "dtypes": {c: str(t) for c, t in df.dtypes.items()},
                "preview": df.head(15).to_dict(orient="records"),
                "nulls": df.isnull().sum().to_dict(),
            }
        elif ext == ".csv":
            df = pd.read_csv(path, sep=None, engine="python", encoding_errors="replace")
            return {
                "rows": len(df),
                "columns": list(df.columns),
                "dtypes": {c: str(t) for c, t in df.dtypes.items()},
                "preview": df.head(15).to_dict(orient="records"),
                "nulls": df.isnull().sum().to_dict(),
            }
        else:
            return {"error": f"Неподдерживаемый формат: {ext}"}
    except Exception as e:
        return {"error": str(e)}


def calculate_metrics(data: dict) -> dict:
    """
    Рассчитывает ключевые рекламные метрики по переданным данным.

    data может содержать:
      impressions, clicks, spend, conversions, revenue,
      reach, video_views, add_to_cart, purchases
    """
    try:
        imp   = float(data.get("impressions", 0) or 0)
        clk   = float(data.get("clicks", 0) or 0)
        spend = float(data.get("spend", 0) or 0)
        conv  = float(data.get("conversions", 0) or 0)
        rev   = float(data.get("revenue", 0) or 0)
        reach = float(data.get("reach", 0) or 0)
        freq  = float(data.get("frequency", 0) or 0)

        def safe(num, den):
            return round(num / den, 4) if den else None

        ctr   = safe(clk, imp)           # Click-Through Rate
        cpc   = safe(spend, clk)         # Cost Per Click
        cpm   = safe(spend * 1000, imp)  # Cost Per Mille
        cvr   = safe(conv, clk)          # Conversion Rate
        cpa   = safe(spend, conv)        # Cost Per Acquisition
        roas  = safe(rev, spend)         # Return on Ad Spend
        roi   = round((rev - spend) / spend * 100, 2) if spend else None  # ROI %
        aov   = safe(rev, conv)          # Average Order Value

        result = {
            "CTR_%":  round(ctr * 100, 2) if ctr is not None else None,
            "CPC":    cpc,
            "CPM":    cpm,
            "CVR_%":  round(cvr * 100, 2) if cvr is not None else None,
            "CPA":    cpa,
            "ROAS":   roas,
            "ROI_%":  roi,
            "AOV":    aov,
        }

        # Частота (если передан reach)
        if imp and reach:
            result["Frequency"] = round(imp / reach, 2)
        elif freq:
            result["Frequency"] = freq

        # Оценка по бенчмаркам e-commerce
        assessments = []
        if ctr is not None:
            if ctr < 0.005:
                assessments.append("⚠️ CTR ниже нормы (<0.5%) — проверьте объявления и аудиторию")
            elif ctr >= 0.02:
                assessments.append("✅ CTR отличный (≥2%)")
        if roas is not None:
            if roas < 2:
                assessments.append("🔴 ROAS < 2 — реклама убыточна, нужна оптимизация")
            elif roas < 4:
                assessments.append("🟡 ROAS 2–4 — на грани окупаемости, есть куда расти")
            else:
                assessments.append("🟢 ROAS > 4 — хороший результат")
        if cpa is not None and aov is not None and aov > 0:
            if cpa / aov > 0.3:
                assessments.append("⚠️ CPA составляет более 30% от AOV — высокая стоимость привлечения")

        result["assessments"] = assessments
        return result

    except Exception as e:
        return {"error": str(e)}


def analyze_campaign_data(path: str, platform: str = "auto", sheet: str = None) -> dict:
    """
    Глубокий анализ рекламной кампании по файлу выгрузки.
    platform: 'google', 'meta', 'auto'
    """
    p = Path(path)
    if not p.exists():
        return {"error": f"Файл не найден: {path}"}
    try:
        ext = p.suffix.lower()
        if ext in (".xlsx", ".xls"):
            df = pd.read_excel(path, sheet_name=sheet or 0)
        elif ext == ".csv":
            df = pd.read_csv(path, sep=None, engine="python", encoding_errors="replace")
        else:
            return {"error": f"Неподдерживаемый формат: {ext}"}

        # Нормализуем названия столбцов
        col_map = {}
        for col in df.columns:
            low = col.lower().replace(" ", "_").replace(".", "").replace("/", "_")
            col_map[col] = low
        df.rename(columns=col_map, inplace=True)

        # Маппинг возможных названий столбцов
        aliases = {
            "impressions": ["impressions", "показы", "impr", "impression"],
            "clicks":      ["clicks", "клики", "click"],
            "spend":       ["spend", "cost", "затраты", "расход", "бюджет", "cost_(usd)", "cost_(rub)"],
            "conversions": ["conversions", "конверсии", "conv", "conv_value", "all_conv"],
            "revenue":     ["revenue", "доход", "выручка", "conv_value", "conversion_value", "revenue_(usd)"],
            "ctr":         ["ctr", "ctr_(%)"],
            "cpc":         ["avg_cpc", "cpc", "avg_cost"],
            "campaign":    ["campaign", "кампания", "campaign_name"],
            "ad_group":    ["ad_group", "группа_объявлений", "adset_name", "ad_set_name"],
            "keyword":     ["keyword", "ключевое_слово", "search_term"],
        }

        def find_col(key):
            for alias in aliases[key]:
                if alias in df.columns:
                    return alias
            return None

        imp_col  = find_col("impressions")
        clk_col  = find_col("clicks")
        spd_col  = find_col("spend")
        cnv_col  = find_col("conversions")
        rev_col  = find_col("revenue")
        cmp_col  = find_col("campaign")
        adg_col  = find_col("ad_group")
        kwd_col  = find_col("keyword")

        numeric_cols = [c for c in [imp_col, clk_col, spd_col, cnv_col, rev_col] if c]
        for c in numeric_cols:
            df[c] = pd.to_numeric(df[c].astype(str).str.replace(",", ".").str.replace("[^0-9.]", "", regex=True), errors="coerce").fillna(0)

        result = {
            "platform_detected": platform,
            "total_rows": len(df),
            "columns_found": list(df.columns),
        }

        # Итоги по всей выгрузке
        totals = {}
        if imp_col:  totals["total_impressions"] = int(df[imp_col].sum())
        if clk_col:  totals["total_clicks"]      = int(df[clk_col].sum())
        if spd_col:  totals["total_spend"]        = round(df[spd_col].sum(), 2)
        if cnv_col:  totals["total_conversions"]  = round(df[cnv_col].sum(), 2)
        if rev_col:  totals["total_revenue"]      = round(df[rev_col].sum(), 2)
        result["totals"] = totals

        # Расчёт сводных метрик
        if totals:
            metrics = calculate_metrics({
                "impressions": totals.get("total_impressions", 0),
                "clicks":      totals.get("total_clicks", 0),
                "spend":       totals.get("total_spend", 0),
                "conversions": totals.get("total_conversions", 0),
                "revenue":     totals.get("total_revenue", 0),
            })
            result["summary_metrics"] = metrics

        # Разбивка по кампаниям
        if cmp_col and spd_col:
            group_cols = [cmp_col]
            agg = {c: "sum" for c in [imp_col, clk_col, spd_col, cnv_col, rev_col] if c}
            camp_df = df.groupby(group_cols).agg(agg).reset_index()
            camp_df = camp_df.sort_values(spd_col, ascending=False)
            result["by_campaign"] = camp_df.head(20).to_dict(orient="records")

        # Разбивка по группам объявлений
        if adg_col and spd_col:
            agg = {c: "sum" for c in [imp_col, clk_col, spd_col, cnv_col, rev_col] if c}
            adg_df = df.groupby([adg_col]).agg(agg).reset_index()
            adg_df = adg_df.sort_values(spd_col, ascending=False)
            result["by_ad_group"] = adg_df.head(20).to_dict(orient="records")

        # Топ ключевых слов
        if kwd_col and spd_col:
            agg = {c: "sum" for c in [imp_col, clk_col, spd_col, cnv_col, rev_col] if c}
            kwd_df = df.groupby([kwd_col]).agg(agg).reset_index()
            kwd_df = kwd_df.sort_values(spd_col, ascending=False)
            result["top_keywords"] = kwd_df.head(20).to_dict(orient="records")

        return result

    except Exception as e:
        return {"error": str(e)}


def calculate_budget_recommendation(
    target_revenue: float,
    current_roas: float = None,
    current_cpa: float = None,
    target_cpa: float = None,
    avg_order_value: float = None,
    margin_pct: float = None,
) -> dict:
    """
    Рассчитывает рекомендуемый бюджет для достижения целевой выручки или количества заказов.
    """
    try:
        result = {"target_revenue": target_revenue}

        if current_roas and current_roas > 0:
            budget_needed = target_revenue / current_roas
            result["budget_needed_by_roas"] = round(budget_needed, 2)
            result["explanation_roas"] = (
                f"При текущем ROAS={current_roas}, чтобы получить {target_revenue} в выручке, "
                f"нужно потратить {round(budget_needed, 2)}"
            )

        if current_cpa and avg_order_value:
            target_orders = target_revenue / avg_order_value
            budget_by_cpa = target_orders * current_cpa
            result["target_orders"] = round(target_orders)
            result["budget_needed_by_cpa"] = round(budget_by_cpa, 2)
            result["explanation_cpa"] = (
                f"Нужно ~{round(target_orders)} заказов × CPA {current_cpa} = {round(budget_by_cpa, 2)}"
            )

        if margin_pct and current_roas:
            breakeven_roas = 1 / (margin_pct / 100)
            result["breakeven_roas"] = round(breakeven_roas, 2)
            result["profitable"] = current_roas > breakeven_roas
            if current_roas > breakeven_roas:
                result["profit_margin_on_adspend"] = round(
                    (1 - 1 / current_roas) * 100 * margin_pct / 100, 2
                )

        if target_cpa and avg_order_value:
            max_budget_per_order = target_cpa
            result["max_cpa_target"] = target_cpa
            result["target_conversion_rate_pct"] = round(
                (1 / (target_cpa / (avg_order_value * 0.01))) * 0.01, 4
            ) if avg_order_value else None

        return result

    except Exception as e:
        return {"error": str(e)}


def audit_google_ads_structure(data: dict) -> dict:
    """
    Проводит аудит структуры Google Ads аккаунта по переданным данным.
    data: словарь с информацией о кампаниях, группах, ключевых словах, объявлениях.
    """
    issues = []
    recommendations = []

    campaigns = data.get("campaigns", [])
    ad_groups = data.get("ad_groups", [])
    keywords  = data.get("keywords", [])
    ads       = data.get("ads", [])

    # Проверки структуры
    if len(campaigns) == 0:
        issues.append("❌ Нет данных о кампаниях")
    else:
        for c in campaigns:
            name = c.get("name", "")
            budget = float(c.get("daily_budget", 0) or 0)
            status = str(c.get("status", "")).lower()

            if budget == 0 and "enable" in status:
                issues.append(f"⚠️ Кампания '{name}': бюджет = 0, но активна")

            if not any(x in name.lower() for x in ["search", "display", "shopping", "performance", "brand", "competitor", "generic", "retarget", "ремаркетинг", "поиск", "дисплей", "шоппинг"]):
                recommendations.append(f"💡 Кампания '{name}': рекомендуется включить тип в название (Search/Display/Shopping/PMax)")

    # Проверки групп объявлений
    if ad_groups:
        kw_per_group = {}
        for kw in keywords:
            ag = kw.get("ad_group", "")
            kw_per_group[ag] = kw_per_group.get(ag, 0) + 1

        for ag_name, count in kw_per_group.items():
            if count > 20:
                issues.append(f"⚠️ Группа '{ag_name}': {count} ключевых слов — слишком много (рекомендуется ≤15–20)")
            elif count < 3:
                recommendations.append(f"💡 Группа '{ag_name}': только {count} ключевых слово — возможно нужно расширить")

    # Проверка объявлений
    if ads:
        ad_per_group = {}
        for ad in ads:
            ag = ad.get("ad_group", "")
            ad_per_group[ag] = ad_per_group.get(ag, 0) + 1

        for ag_name, count in ad_per_group.items():
            if count < 2:
                issues.append(f"⚠️ Группа '{ag_name}': только {count} объявление — рекомендуется минимум 2–3")
            elif count > 5:
                recommendations.append(f"💡 Группа '{ag_name}': {count} объявлений — убедитесь, что A/B тест настроен корректно")

    # Проверка типов соответствия
    if keywords:
        match_types = [str(k.get("match_type", "")).lower() for k in keywords]
        has_broad = sum(1 for m in match_types if "broad" in m or "широкое" in m)
        has_exact = sum(1 for m in match_types if "exact" in m or "точное" in m)
        total = len(keywords)

        if total > 0 and has_broad / total > 0.7:
            issues.append(f"⚠️ {round(has_broad/total*100)}% ключевых слов — широкое соответствие. Рекомендуется добавить точные и фразовые")
        if has_exact == 0:
            recommendations.append("💡 Нет ключевых слов с точным соответствием [exact] — добавьте для контроля трафика")

    score = max(0, 100 - len(issues) * 15 - len(recommendations) * 5)

    return {
        "account_score": score,
        "issues_count": len(issues),
        "recommendations_count": len(recommendations),
        "issues": issues,
        "recommendations": recommendations,
        "summary": f"Аккаунт оценён на {score}/100. Найдено {len(issues)} проблем и {len(recommendations)} рекомендаций.",
    }


def audit_meta_ads_structure(data: dict) -> dict:
    """
    Проводит аудит структуры Meta Ads (Facebook/Instagram) аккаунта.
    data: словарь с кампаниями, адсетами, объявлениями и метриками.
    """
    issues = []
    recommendations = []

    campaigns = data.get("campaigns", [])
    adsets    = data.get("adsets", [])
    ads       = data.get("ads", [])

    # Проверка кампаний
    for c in campaigns:
        name       = c.get("name", "")
        objective  = str(c.get("objective", "")).upper()
        budget     = float(c.get("daily_budget", 0) or c.get("lifetime_budget", 0) or 0)

        if budget == 0:
            issues.append(f"⚠️ Кампания '{name}': бюджет = 0")

        if objective == "CONVERSIONS" or objective == "PURCHASE":
            recommendations.append(f"✅ Кампания '{name}': цель Conversions — правильно для e-commerce")
        elif objective in ("REACH", "BRAND_AWARENESS"):
            recommendations.append(f"💡 Кампания '{name}': цель {objective} — убедитесь, что это этап охвата воронки, не конверсий")

    # Проверка адсетов
    for adset in adsets:
        name       = adset.get("name", "")
        opt_goal   = str(adset.get("optimization_goal", "")).upper()
        audience   = adset.get("audience_size", 0)
        freq       = float(adset.get("frequency", 0) or 0)
        ctr        = float(adset.get("ctr", 0) or 0)
        roas       = float(adset.get("roas", 0) or 0)
        spend      = float(adset.get("spend", 0) or 0)

        if freq > 3.5:
            issues.append(f"⚠️ Адсет '{name}': частота {round(freq,1)} — аудитория перегрета, нужно расширить или сменить креативы")
        if ctr < 0.5 and spend > 100:
            issues.append(f"⚠️ Адсет '{name}': CTR={round(ctr,2)}% при расходе {spend} — низкая кликабельность, проверьте креативы")
        if roas and roas < 1:
            issues.append(f"🔴 Адсет '{name}': ROAS={round(roas,2)} < 1 — убыточный адсет")

        if audience and int(audience) < 50000:
            recommendations.append(f"💡 Адсет '{name}': аудитория {audience} — может быть мала для обучения алгоритма")
        elif audience and int(audience) > 10_000_000:
            recommendations.append(f"💡 Адсет '{name}': аудитория {audience} — очень широкая, возможно стоит сегментировать")

    # Проверка объявлений
    ads_per_adset = {}
    for ad in ads:
        ag = ad.get("adset", "")
        ads_per_adset[ag] = ads_per_adset.get(ag, 0) + 1

    for ag_name, count in ads_per_adset.items():
        if count < 2:
            recommendations.append(f"💡 Адсет '{ag_name}': только {count} объявление — рекомендуется 3–5 для A/B теста креативов")
        elif count > 6:
            recommendations.append(f"💡 Адсет '{ag_name}': {count} объявлений — много, алгоритм может не успеть обучиться на каждом")

    score = max(0, 100 - len(issues) * 15 - len(recommendations) * 5)

    return {
        "account_score": score,
        "issues_count": len(issues),
        "recommendations_count": len(recommendations),
        "issues": issues,
        "recommendations": recommendations,
        "summary": f"Аккаунт Meta оценён на {score}/100. Найдено {len(issues)} проблем и {len(recommendations)} рекомендаций.",
    }


def get_benchmarks(industry: str = "ecommerce", platform: str = "google") -> dict:
    """Возвращает отраслевые бенчмарки для сравнения метрик."""
    benchmarks = {
        "google": {
            "ecommerce": {
                "CTR_%":     {"good": 2.0,   "average": 1.0,   "poor": 0.5,  "unit": "%"},
                "CPC":       {"good": 0.5,   "average": 1.5,   "poor": 3.0,  "unit": "USD", "note": "зависит от ниши"},
                "CVR_%":     {"good": 4.0,   "average": 2.0,   "poor": 0.5,  "unit": "%"},
                "ROAS":      {"good": 5.0,   "average": 3.0,   "poor": 1.5,  "unit": "x"},
                "CPA":       {"note": "зависит от AOV и маржинальности"},
                "QS":        {"good": 8,     "average": 6,     "poor": 4,    "unit": "из 10"},
            },
            "b2b": {
                "CTR_%":     {"good": 3.0,   "average": 1.5,   "poor": 0.5,  "unit": "%"},
                "CPC":       {"good": 2.0,   "average": 5.0,   "poor": 10.0, "unit": "USD"},
                "CVR_%":     {"good": 2.0,   "average": 0.8,   "poor": 0.2,  "unit": "%"},
            },
        },
        "meta": {
            "ecommerce": {
                "CTR_%":     {"good": 1.5,   "average": 0.9,   "poor": 0.5,  "unit": "%"},
                "CPC":       {"good": 0.3,   "average": 0.8,   "poor": 2.0,  "unit": "USD"},
                "CPM":       {"good": 5.0,   "average": 12.0,  "poor": 25.0, "unit": "USD"},
                "ROAS":      {"good": 4.0,   "average": 2.5,   "poor": 1.0,  "unit": "x"},
                "Frequency": {"good": 2.0,   "average": 3.0,   "poor": 4.5,  "unit": "показов/человек", "note": "высокая = перегрев аудитории"},
                "CVR_%":     {"good": 2.5,   "average": 1.0,   "poor": 0.3,  "unit": "%"},
            },
        },
    }

    plat_data = benchmarks.get(platform.lower(), {})
    ind_data  = plat_data.get(industry.lower(), plat_data.get("ecommerce", {}))

    return {
        "platform": platform,
        "industry": industry,
        "benchmarks": ind_data,
        "note": "Бенчмарки являются ориентировочными и зависят от ниши, гео, сезона и конкуренции.",
    }


def calculate_funnel(
    sessions: float,
    pdp_views: float = None,
    add_to_cart: float = None,
    checkout_starts: float = None,
    purchases: float = None,
    revenue: float = None,
) -> dict:
    """Рассчитывает конверсию на каждом этапе e-commerce воронки."""
    def pct(a, b):
        return round(a / b * 100, 2) if b else None

    funnel = {"sessions": sessions}

    if pdp_views is not None:
        funnel["pdp_views"]           = pdp_views
        funnel["sessions_to_pdp_%"]   = pct(pdp_views, sessions)
    if add_to_cart is not None:
        funnel["add_to_cart"]         = add_to_cart
        base = pdp_views or sessions
        funnel["pdp_to_cart_%"]       = pct(add_to_cart, base)
    if checkout_starts is not None:
        funnel["checkout_starts"]     = checkout_starts
        base = add_to_cart or pdp_views or sessions
        funnel["cart_to_checkout_%"]  = pct(checkout_starts, base)
    if purchases is not None:
        funnel["purchases"]           = purchases
        base = checkout_starts or add_to_cart or sessions
        funnel["checkout_to_purchase_%"] = pct(purchases, base)
        funnel["overall_cvr_%"]       = pct(purchases, sessions)
    if revenue is not None and purchases:
        funnel["revenue"]             = revenue
        funnel["AOV"]                 = round(revenue / purchases, 2)

    # Оценка узких мест
    bottlenecks = []
    if funnel.get("sessions_to_pdp_%", 100) < 30:
        bottlenecks.append("📍 Мало переходов на страницы товаров — проверьте навигацию и релевантность трафика")
    if funnel.get("pdp_to_cart_%", 100) < 5:
        bottlenecks.append("📍 Низкая конверсия PDP→Корзина (<5%) — улучшите описания, фото, цену, CTA")
    if funnel.get("cart_to_checkout_%", 100) < 50:
        bottlenecks.append("📍 Много брошенных корзин (<50% переходят к оформлению) — настройте ретаргетинг")
    if funnel.get("checkout_to_purchase_%", 100) < 60:
        bottlenecks.append("📍 Высокий процент отказов при оформлении (<60%) — упростите чекаут, добавьте способы оплаты")

    funnel["bottlenecks"] = bottlenecks
    return funnel


def generate_utm(
    base_url: str,
    source: str,
    medium: str,
    campaign: str,
    content: str = None,
    term: str = None,
) -> dict:
    """Генерирует UTM-ссылку и проверяет корректность параметров."""
    import urllib.parse

    issues = []
    # Проверка типичных ошибок
    if " " in source:
        issues.append("⚠️ utm_source содержит пробелы — замените на '_' или '-'")
        source = source.replace(" ", "_")
    if " " in medium:
        issues.append("⚠️ utm_medium содержит пробелы — замените на '_' или '-'")
        medium = medium.replace(" ", "_")
    if " " in campaign:
        issues.append("⚠️ utm_campaign содержит пробелы — замените на '_' или '-'")
        campaign = campaign.replace(" ", "_")

    params = {
        "utm_source":   source.lower(),
        "utm_medium":   medium.lower(),
        "utm_campaign": campaign.lower(),
    }
    if content:
        params["utm_content"] = content.replace(" ", "_").lower()
    if term:
        params["utm_term"] = term.replace(" ", "_").lower()

    separator = "&" if "?" in base_url else "?"
    utm_url = base_url + separator + urllib.parse.urlencode(params)

    # Типичные значения medium
    known_mediums = {"cpc", "ppc", "cpm", "email", "social", "organic", "referral", "display", "video", "sms", "push"}
    if medium.lower() not in known_mediums:
        issues.append(f"💡 utm_medium='{medium}' нестандартный — стандарты: cpc, email, social, display, referral")

    return {
        "utm_url": utm_url,
        "params": params,
        "issues": issues,
        "tip": "Сохраняй UTM-ссылки в таблице: кампания / дата / URL / канал / результат",
    }


def save_report(data: dict, output_path: str, title: str = "Отчёт по рекламе") -> dict:
    """Сохраняет результаты анализа в Excel-файл с несколькими листами."""
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill, Alignment
        from openpyxl.utils import get_column_letter

        wb = Workbook()
        ws = wb.active
        ws.title = "Сводка"

        header_color = Font(bold=True, color="FFFFFF", size=11)
        title_font   = Font(bold=True, size=14)

        # Заголовок
        ws["A1"] = title
        ws["A1"].font = title_font
        ws.merge_cells("A1:D1")
        row = 3

        def write_section(ws, start_row, section_title, items):
            ws.cell(start_row, 1, section_title).font = Font(bold=True, size=11, color="1F4E79")
            start_row += 1
            if isinstance(items, dict):
                for k, v in items.items():
                    ws.cell(start_row, 1, str(k))
                    ws.cell(start_row, 2, str(v))
                    start_row += 1
            elif isinstance(items, list):
                for item in items:
                    if isinstance(item, dict):
                        if start_row == 3 or ws.cell(start_row - 1, 1).value != list(item.keys())[0]:
                            for ci, col in enumerate(item.keys(), 1):
                                cell = ws.cell(start_row, ci, str(col))
                                cell.font = header_color
                                cell.fill = PatternFill("solid", fgColor="2E75B6")
                            start_row += 1
                        for ci, val in enumerate(item.values(), 1):
                            ws.cell(start_row, ci, str(val))
                    else:
                        ws.cell(start_row, 1, str(item))
                    start_row += 1
            return start_row + 1

        # Записываем секции
        for section_name, section_data in data.items():
            row = write_section(ws, row, section_name, section_data)

        # Автоширина
        for col in ws.columns:
            max_len = max((len(str(cell.value or "")) for cell in col), default=0)
            ws.column_dimensions[get_column_letter(col[0].column)].width = min(max_len + 3, 60)

        # Если есть разбивка по кампаниям — отдельный лист
        if "by_campaign" in data and isinstance(data["by_campaign"], list) and data["by_campaign"]:
            ws2 = wb.create_sheet("По кампаниям")
            df_camp = pd.DataFrame(data["by_campaign"])
            headers = list(df_camp.columns)
            for ci, h in enumerate(headers, 1):
                cell = ws2.cell(1, ci, h)
                cell.font = Font(bold=True, color="FFFFFF")
                cell.fill = PatternFill("solid", fgColor="1F4E79")
            for ri, row_data in enumerate(df_camp.values.tolist(), 2):
                for ci, val in enumerate(row_data, 1):
                    ws2.cell(ri, ci, val)
            for col in ws2.columns:
                mx = max((len(str(c.value or "")) for c in col), default=0)
                ws2.column_dimensions[get_column_letter(col[0].column)].width = min(mx + 3, 50)

        wb.save(output_path)
        return {"saved": output_path, "sheets": wb.sheetnames}

    except Exception as e:
        return {"error": str(e)}


def compare_periods(
    period1: dict,
    period2: dict,
    period1_name: str = "Период 1",
    period2_name: str = "Период 2",
) -> dict:
    """
    Сравнивает два рекламных периода и считает изменения по всем метрикам.
    Каждый период: {impressions, clicks, spend, conversions, revenue}
    """
    def calc(d):
        return calculate_metrics(d)

    m1 = calc(period1)
    m2 = calc(period2)

    comparison = {}
    all_keys = set(list(period1.keys()) + list(period2.keys()) + list(m1.keys()) + list(m2.keys()))
    all_keys.discard("assessments")

    raw_keys = ["impressions", "clicks", "spend", "conversions", "revenue"]

    for key in raw_keys:
        v1 = float(period1.get(key, 0) or 0)
        v2 = float(period2.get(key, 0) or 0)
        delta = v2 - v1
        pct   = round((v2 - v1) / v1 * 100, 1) if v1 else None
        arrow = "▲" if delta > 0 else ("▼" if delta < 0 else "→")
        comparison[key] = {
            period1_name: v1,
            period2_name: v2,
            "delta":      round(delta, 2),
            "change_%":   pct,
            "trend":      arrow,
        }

    metric_keys = ["CTR_%", "CPC", "CPM", "CVR_%", "CPA", "ROAS", "ROI_%", "AOV"]
    for key in metric_keys:
        v1 = m1.get(key)
        v2 = m2.get(key)
        if v1 is None and v2 is None:
            continue
        v1 = float(v1 or 0)
        v2 = float(v2 or 0)
        delta = v2 - v1
        pct   = round((v2 - v1) / v1 * 100, 1) if v1 else None
        # Для CPA и CPC рост — плохо
        positive_is_good = key not in ("CPA", "CPC", "CPM")
        if delta > 0:
            arrow = "🟢▲" if positive_is_good else "🔴▲"
        elif delta < 0:
            arrow = "🔴▼" if positive_is_good else "🟢▼"
        else:
            arrow = "→"
        comparison[key] = {
            period1_name: v1,
            period2_name: v2,
            "delta":      round(delta, 4),
            "change_%":   pct,
            "trend":      arrow,
        }

    return {
        "comparison": comparison,
        "period1_metrics": {k: v for k, v in m1.items() if k != "assessments"},
        "period2_metrics": {k: v for k, v in m2.items() if k != "assessments"},
    }


# ─── Схемы инструментов ──────────────────────────────────────────────────────

TOOLS = [
    {
        "name": "read_ads_report",
        "description": "Читает файл выгрузки из Google Ads, Meta Ads или другой рекламной платформы (Excel, CSV) и показывает структуру данных.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path":  {"type": "string", "description": "Путь к файлу"},
                "sheet": {"type": "string", "description": "Название листа (для Excel)"},
            },
            "required": ["path"],
        },
    },
    {
        "name": "analyze_campaign_data",
        "description": "Глубокий анализ рекламных кампаний: итоги, ROAS, CPA, CTR, CPC, разбивка по кампаниям/группам/ключевым словам. Используй после read_ads_report.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path":     {"type": "string", "description": "Путь к файлу"},
                "platform": {"type": "string", "description": "google / meta / auto", "default": "auto"},
                "sheet":    {"type": "string", "description": "Название листа (для Excel)"},
            },
            "required": ["path"],
        },
    },
    {
        "name": "calculate_metrics",
        "description": "Рассчитывает CTR, CPC, CPM, CVR, CPA, ROAS, ROI, AOV по переданным числам. Используй для быстрого расчёта по данным из чата.",
        "input_schema": {
            "type": "object",
            "properties": {
                "data": {
                    "type": "object",
                    "description": "Объект с числовыми значениями: impressions, clicks, spend, conversions, revenue, reach, frequency",
                },
            },
            "required": ["data"],
        },
    },
    {
        "name": "calculate_budget_recommendation",
        "description": "Рассчитывает необходимый рекламный бюджет для достижения целевой выручки или количества заказов.",
        "input_schema": {
            "type": "object",
            "properties": {
                "target_revenue":   {"type": "number", "description": "Целевая выручка"},
                "current_roas":     {"type": "number", "description": "Текущий ROAS"},
                "current_cpa":      {"type": "number", "description": "Текущий CPA"},
                "target_cpa":       {"type": "number", "description": "Целевой CPA"},
                "avg_order_value":  {"type": "number", "description": "Средний чек (AOV)"},
                "margin_pct":       {"type": "number", "description": "Маржинальность в % (например 40 = 40%)"},
            },
            "required": ["target_revenue"],
        },
    },
    {
        "name": "audit_google_ads_structure",
        "description": "Аудит структуры Google Ads аккаунта: проверяет кампании, группы объявлений, ключевые слова, объявления на ошибки и даёт рекомендации.",
        "input_schema": {
            "type": "object",
            "properties": {
                "data": {
                    "type": "object",
                    "description": "Данные аккаунта: {campaigns: [...], ad_groups: [...], keywords: [...], ads: [...]}",
                },
            },
            "required": ["data"],
        },
    },
    {
        "name": "audit_meta_ads_structure",
        "description": "Аудит структуры Meta Ads (Facebook/Instagram) аккаунта: кампании, адсеты, объявления, частота, CTR, ROAS.",
        "input_schema": {
            "type": "object",
            "properties": {
                "data": {
                    "type": "object",
                    "description": "Данные аккаунта: {campaigns: [...], adsets: [...], ads: [...]}",
                },
            },
            "required": ["data"],
        },
    },
    {
        "name": "get_benchmarks",
        "description": "Возвращает отраслевые бенчмарки (CTR, CPC, ROAS, CVR и др.) для сравнения показателей аккаунта.",
        "input_schema": {
            "type": "object",
            "properties": {
                "industry": {"type": "string", "description": "ecommerce / b2b / saas / finance / education", "default": "ecommerce"},
                "platform": {"type": "string", "description": "google / meta", "default": "google"},
            },
            "required": [],
        },
    },
    {
        "name": "calculate_funnel",
        "description": "Рассчитывает конверсию по этапам e-commerce воронки и находит узкие места.",
        "input_schema": {
            "type": "object",
            "properties": {
                "sessions":         {"type": "number", "description": "Визиты / сессии"},
                "pdp_views":        {"type": "number", "description": "Просмотры страниц товаров"},
                "add_to_cart":      {"type": "number", "description": "Добавления в корзину"},
                "checkout_starts":  {"type": "number", "description": "Начатые оформления"},
                "purchases":        {"type": "number", "description": "Покупки / заказы"},
                "revenue":          {"type": "number", "description": "Выручка"},
            },
            "required": ["sessions"],
        },
    },
    {
        "name": "generate_utm",
        "description": "Генерирует правильную UTM-ссылку и проверяет параметры на типичные ошибки.",
        "input_schema": {
            "type": "object",
            "properties": {
                "base_url":  {"type": "string", "description": "Базовый URL страницы"},
                "source":    {"type": "string", "description": "utm_source: google, facebook, instagram, email и т.д."},
                "medium":    {"type": "string", "description": "utm_medium: cpc, email, social, display и т.д."},
                "campaign":  {"type": "string", "description": "utm_campaign: название кампании"},
                "content":   {"type": "string", "description": "utm_content: название объявления или баннера (опционально)"},
                "term":      {"type": "string", "description": "utm_term: ключевое слово (опционально, для поиска)"},
            },
            "required": ["base_url", "source", "medium", "campaign"],
        },
    },
    {
        "name": "compare_periods",
        "description": "Сравнивает показатели двух рекламных периодов (месяц к месяцу, неделя к неделе и т.д.) и рассчитывает динамику всех метрик.",
        "input_schema": {
            "type": "object",
            "properties": {
                "period1":       {"type": "object", "description": "Данные первого периода: {impressions, clicks, spend, conversions, revenue}"},
                "period2":       {"type": "object", "description": "Данные второго периода: {impressions, clicks, spend, conversions, revenue}"},
                "period1_name":  {"type": "string", "description": "Название первого периода, напр. 'Март 2025'"},
                "period2_name":  {"type": "string", "description": "Название второго периода, напр. 'Апрель 2025'"},
            },
            "required": ["period1", "period2"],
        },
    },
    {
        "name": "save_report",
        "description": "Сохраняет результаты анализа в Excel-файл (.xlsx).",
        "input_schema": {
            "type": "object",
            "properties": {
                "data":         {"type": "object", "description": "Данные для сохранения (словарь секций)"},
                "output_path":  {"type": "string", "description": "Путь для сохранения файла, напр. 'report.xlsx'"},
                "title":        {"type": "string", "description": "Заголовок отчёта"},
            },
            "required": ["data", "output_path"],
        },
    },
]

TOOL_FUNCTIONS = {
    "read_ads_report":                 read_ads_report,
    "analyze_campaign_data":           analyze_campaign_data,
    "calculate_metrics":               calculate_metrics,
    "calculate_budget_recommendation": calculate_budget_recommendation,
    "audit_google_ads_structure":      audit_google_ads_structure,
    "audit_meta_ads_structure":        audit_meta_ads_structure,
    "get_benchmarks":                  get_benchmarks,
    "calculate_funnel":                calculate_funnel,
    "generate_utm":                    generate_utm,
    "compare_periods":                 compare_periods,
    "save_report":                     save_report,
}

SYSTEM_PROMPT = """Ты опытный performance-маркетолог с 10+ годами практики в e-commerce.

## Твои специализации:

### Google Ads
- Поиск (Search): структура кампаний, типы соответствия, минус-слова, расширения, QS
- Performance Max (PMax): сигналы аудиторий, asset groups, интерпретация отчётов
- Shopping / Google Merchant Center: фид товаров, правила фида, Merchant promotions
- Display & YouTube: аудитории, форматы, исключения плейсментов
- Аудит аккаунтов: структура, минус-слова, конверсии, ставки, Quality Score
- Настройка конверсий: gtag, Tag Manager, GA4, импорт конверсий из CRM
- Стратегии ставок: tROAS, tCPA, Maximize Conversions, Enhanced CPC

### Meta Ads (Facebook / Instagram)
- Структура: кампания → адсет → объявление, уровни бюджетирования (ABO vs CBO)
- Цели: Conversions, Catalog Sales, Traffic, Reach, Lead Generation
- Аудитории: Lookalike, Custom Audiences (pixel, CRM, video), Interest, Broad
- Pixel: события, CAPI (Conversions API), дедупликация, event matching quality
- Креативы: форматы (image/video/carousel/collection/reels), тексты, хуки
- Алгоритм: фаза обучения (learning phase), стабилизация, reset
- ROAS, частота, усталость аудитории, scaling (вертикальный / горизонтальный)

### E-commerce аналитика
- Воронка: трафик → PDP → корзина → чекаут → покупка
- Метрики: ROAS, CPA, AOV, LTV, CAC, CR, CTR, CPM, CPC, Frequency
- Когортный анализ, retention, повторные покупки
- Атрибуция: Last Click, Data-Driven, first-touch, linear
- Google Analytics 4: события, конверсии, аудитории для ремаркетинга
- Сезонность, конкурентный анализ, управление бюджетом

### Настройка рекламы (пошаговые инструкции)
- Запуск рекламы с нуля: от структуры до первых результатов
- A/B тестирование: гипотезы, статистическая значимость, итерации
- Ретаргетинг: сегменты, окна атрибуции, исключения конвертированных

### Дополнительные задачи
- UTM-разметка: генерация правильных ссылок, проверка ошибок, стандарты
- Сравнение периодов: WoW, MoM, YoY — динамика всех метрик с оценкой тренда
- Сохранение отчётов в Excel с несколькими листами

## Как ты работаешь:

1. **Анализ данных**: используй инструменты для чтения файлов и расчёта метрик
2. **Сравнение с бенчмарками**: всегда сравнивай показатели с отраслевыми нормами
3. **Конкретные рекомендации**: не общие слова, а точные действия с приоритетами
4. **Структура ответов**:
   - Коротко: что нашёл
   - Что хорошо / что плохо
   - Топ-3 действия (по приоритету)
5. **Числа**: всегда опирайся на данные, избегай абстрактных советов

## Формат ответов:
- Используй эмодзи-иконки для статусов: ✅ хорошо, ⚠️ внимание, 🔴 критично, 💡 рекомендация
- Таблицы для сравнения метрик
- Чёткие пункты для action items
- Отвечай на русском языке

При анализе файлов: сначала прочитай структуру (read_ads_report), потом запускай полный анализ (analyze_campaign_data)."""


# ─── Основной цикл ───────────────────────────────────────────────────────────

def run_agent(user_message: str, messages: list) -> str:
    messages.append({"role": "user", "content": user_message})

    while True:
        response = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=8096,
            thinking={"type": "adaptive"},
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages,
        )

        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "end_turn":
            return "\n".join(b.text for b in response.content if b.type == "text")

        if response.stop_reason == "tool_use":
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    print(f"  🔧 [{block.name}] {json.dumps(block.input, ensure_ascii=False)[:120]}...")
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
    print("=" * 65)
    print("  📊 Агент-маркетолог | Google Ads · Meta Ads · E-commerce")
    print("=" * 65)
    print()
    print("Примеры запросов:")
    print("  • Проанализируй файл google_ads_export.csv")
    print("  • Рассчитай ROAS и CPA: потратил 50000 руб, выручка 180000 руб, 120 заказов")
    print("  • Какой нужен бюджет для выручки 500000 при текущем ROAS=3.5?")
    print("  • Оцени воронку: 10000 сессий, 3000 pdp, 500 корзин, 150 заказов, выручка 120000")
    print("  • Сравни март (расход 40000, выручка 120000) и апрель (расход 55000, выручка 190000)")
    print("  • Сгенерируй UTM-ссылку для Google Ads кампании на https://myshop.ru/sale")
    print("  • Какие бенчмарки CTR и ROAS для e-commerce в Meta Ads?")
    print("  • Как правильно настроить Performance Max для интернет-магазина?")
    print("  • Помоги провести аудит Meta Ads аккаунта")
    print()
    print("Введите 'выход' для завершения.\n")

    messages: list = []

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
            if messages and messages[-1]["role"] == "user":
                messages.pop()

        # Ограничиваем историю
        if len(messages) > 50:
            messages = messages[-50:]


if __name__ == "__main__":
    main()
