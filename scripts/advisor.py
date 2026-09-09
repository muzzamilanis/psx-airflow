"""Rule-based advisor cards for the daily PSX email. Not trade orders."""

CORE_SYMBOLS = {"FFC", "OGDC", "LUCK"}
DO_NOT_ADD_DEFAULT = {"KEL", "CLOV"}

FUNDAMENTALS_SQL = """
    select symbol, pe_ttm_psx, latest_fy_eps, fy_eps_growth_pct,
           latest_qtr, latest_qtr_eps, results_stale_flag, notes
    from mart_fundamentals
"""

NEWS_SQL = """
    select symbol, source, title, published_at
    from raw_news
    where published_at >= now() - interval '14 days'
      and (
            symbol = any(%s)
            or title ~* %s
          )
    order by published_at desc nulls last
    limit 40
"""


def fmt_signed_pct(value):
    return f"{value:+.0f}%" if value is not None else "n/a"


def fmt_rsi(value):
    return f"{value:.0f}" if value is not None else "n/a"


def fmt_ratio(value):
    return f"{value:.1f}x" if value is not None else "n/a"


def fmt_pe(value):
    return f"{value:.1f}" if value is not None else "n/a"


def technicals_line(tech):
    if tech is None:
        return "n/a"
    return (
        f"vs 200DMA: {fmt_signed_pct(tech['pct_vs_sma_200'])} | "
        f"RSI: {fmt_rsi(tech['rsi_14'])} | "
        f"vol: {fmt_ratio(tech['volume_ratio_20'])}"
    )


def news_by_symbol(news_rows, symbols):
    buckets = {sym: [] for sym in symbols}
    market = []
    for row in news_rows:
        title = row.get("title") or ""
        tagged = row.get("symbol")
        placed = False
        if tagged in buckets:
            buckets[tagged].append(title)
            placed = True
        else:
            for sym in symbols:
                if sym.lower() in title.lower():
                    buckets[sym].append(title)
                    placed = True
                    break
        if not placed:
            market.append(title)
    return buckets, market


def build_call(symbol, tech, fund):
    stale = bool(fund and fund.get("results_stale_flag"))
    rsi = tech.get("rsi_14") if tech else None
    vs200 = tech.get("pct_vs_sma_200") if tech else None
    pe = fund.get("pe_ttm_psx") if fund else None
    growth = fund.get("fy_eps_growth_pct") if fund else None

    if stale or symbol in DO_NOT_ADD_DEFAULT:
        return (
            "HOLD — do not add",
            "Numbers are stale or the story is messy (share count / old results). "
            "Keep the existing lot. Do not use SIP cash here.",
            "#b45309",
        )

    if pe is not None and pe > 40:
        return (
            "HOLD — do not chase",
            "PSX P/E is unusually high, so the official earnings figure is a poor "
            "guide. Keep what you own; do not add.",
            "#b45309",
        )

    if rsi is not None and rsi >= 70:
        return (
            "HOLD — stretched",
            "RSI is high (name has already run). Adding here is chasing. Keep the lot.",
            "#b45309",
        )

    if rsi is not None and rsi <= 30:
        return (
            "HOLD — washed out",
            "RSI is low. That can be a bargain or a falling knife. Watch; do not "
            "auto-buy just because the oscillator looks cheap.",
            "#1d4ed8",
        )

    if symbol in CORE_SYMBOLS:
        bits = ["This is a core holding."]
        if pe is not None:
            bits.append(f"PSX P/E is {fmt_pe(pe)}.")
        if growth is not None:
            bits.append(f"Last full-year EPS change {growth:+.0f}%.")
        if vs200 is not None:
            bits.append(f"Price vs 200-day average: {fmt_signed_pct(vs200)}.")
        bits.append("Keep it. No extra SIP unless you separately decide.")
        return ("HOLD — core", " ".join(bits), "#0a7d2c")

    bits = ["Keep the position."]
    if pe is not None:
        bits.append(f"PSX P/E {fmt_pe(pe)}.")
    if vs200 is not None:
        bits.append(f"Vs 200-day: {fmt_signed_pct(vs200)}.")
    bits.append("Not a core SIP name unless the next results stay clean.")
    return ("HOLD", " ".join(bits), "#1d4ed8")


def render_cards(snapshot_rows, technicals, fundamentals, news_rows, card_template):
    symbols = [row["symbol"] for row in snapshot_rows]
    news_map, market_news = news_by_symbol(news_rows, symbols)
    cards = []
    for row in snapshot_rows:
        symbol = row["symbol"]
        tech = technicals.get(symbol)
        fund = fundamentals.get(symbol)
        call, reason, call_color = build_call(symbol, tech, fund)
        facts = (
            f"Price {row['current_price']:.2f} | "
            f"{technicals_line(tech)} | "
            f"P/E {fmt_pe(fund.get('pe_ttm_psx') if fund else None)}"
        )
        if fund and fund.get("latest_qtr"):
            q_eps = fund.get("latest_qtr_eps")
            q_eps_txt = f"{q_eps:.2f}" if q_eps is not None else "n/a"
            facts += f" | {fund['latest_qtr']} EPS {q_eps_txt}"
        if fund and fund.get("results_stale_flag"):
            facts += " | results flagged STALE"
        headlines = news_map.get(symbol) or []
        if headlines:
            news_txt = " | ".join(headlines[:2])
        elif market_news:
            news_txt = "No company headline. Market: " + market_news[0]
        else:
            news_txt = "No headline in the last 14 days"
        cards.append(
            card_template.substitute(
                symbol=symbol,
                call=call,
                call_color=call_color,
                reason=reason,
                facts=facts,
                news=news_txt,
            )
        )
    return "".join(cards)
