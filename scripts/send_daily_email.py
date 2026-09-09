"""Render and send the daily PSX portfolio email.

Queries mart_portfolio_snapshot and mart_portfolio_summary (built by
`dbt build` earlier in .github/workflows/daily_pipeline.yml) plus
mart_portfolio_trades for realized P&L, mart_technical_indicators,
mart_fundamentals, and recent raw_news, then emails an HTML summary
via Gmail SMTP using SMTP_USER/SMTP_PASSWORD, to EMAIL_TO.

Advisor cards are rule-based (no LLM). They are not trade orders.
"""
import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from string import Template

import psycopg2
import psycopg2.extras

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587

CORE_SYMBOLS = {"FFC", "OGDC", "LUCK"}
DO_NOT_ADD_DEFAULT = {"KEL", "CLOV"}

SUMMARY_SQL = """
    select price_date, total_invested, total_current_value,
           total_unrealized_pnl, total_unrealized_pct, holdings_count
    from mart_portfolio_summary
    order by price_date desc
    limit 1
"""

SNAPSHOT_SQL = """
    select symbol, current_price, todays_change_pct, current_value, unrealized_pnl
    from mart_portfolio_snapshot
    order by symbol
"""

REALIZED_PNL_SQL = """
    select coalesce(sum(net_pnl), 0), count(*)
    from mart_portfolio_trades
"""

TECHNICALS_SQL = """
    select symbol, pct_vs_sma_200, rsi_14, volume_ratio_20
    from mart_technical_indicators
"""

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
