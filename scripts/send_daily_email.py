"""Render and send the daily PSX portfolio email.

Queries marts built by dbt build, then emails HTML via Gmail SMTP.
Advisor cards come from scripts/advisor.py (rule-based, not trade orders).
"""
import logging
import os
import smtplib
import sys
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from string import Template

import psycopg2
import psycopg2.extras

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import advisor

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587

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
