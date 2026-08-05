"""Render and send the daily PSX portfolio email.

Queries mart_portfolio_snapshot and mart_portfolio_summary (built by
`dbt build` earlier in .github/workflows/daily_pipeline.yml) plus
mart_portfolio_trades for realized P&L, then emails an HTML summary via
Gmail SMTP using SMTP_USER/SMTP_PASSWORD, to EMAIL_TO.
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

EMAIL_TEMPLATE = Template("""\
<html>
<body style="font-family: Arial, sans-serif; color: #1a1a1a;">
  <h2>PSX Portfolio — $price_date</h2>

  <table cellpadding="6" style="border-collapse: collapse; margin-bottom: 20px;">
    <tr><td>Total Current Value</td><td><b>PKR $total_current_value</b></td></tr>
    <tr><td>Total Invested</td><td>PKR $total_invested</td></tr>
    <tr><td>Unrealized P&amp;L</td><td style="color:$unrealized_color;"><b>PKR $total_unrealized_pnl ($total_unrealized_pct%)</b></td></tr>
    <tr><td>Realized P&amp;L (all closed trades)</td><td style="color:$realized_color;"><b>PKR $realized_pnl</b></td></tr>
    <tr><td>Holdings</td><td>$holdings_count</td></tr>
  </table>

  <h3>Per-Ticker Day Change</h3>
  <table cellpadding="6" style="border-collapse: collapse; border: 1px solid #ddd;">
    <tr style="background:#f2f2f2;">
      <th align="left">Symbol</th>
      <th align="right">Price</th>
      <th align="right">Day Change</th>
      <th align="right">Value</th>
      <th align="right">Unrealized P&amp;L</th>
    </tr>
    $ticker_rows
  </table>

  <div style="font-size: 12px; color: #666;">
    $technicals_lines
  </div>
</body>
</html>
""")

ROW_TEMPLATE = Template("""\
    <tr>
      <td>$symbol</td>
      <td align="right">$current_price</td>
      <td align="right" style="color:$change_color;">$todays_change_pct%</td>
      <td align="right">$current_value</td>
      <td align="right" style="color:$pnl_color;">$unrealized_pnl</td>
    </tr>
""")

TECH_LINE_TEMPLATE = Template("""\
    <div><b>$symbol</b> — $technicals_line</div>
""")


def _color(value):
    return "#0a7d2c" if value is not None and value >= 0 else "#c02626"


def _fmt_signed_pct(value):
    return f"{value:+.0f}%" if value is not None else "n/a"


def _fmt_rsi(value):
    return f"{value:.0f}" if value is not None else "n/a"


def _fmt_ratio(value):
    return f"{value:.1f}x" if value is not None else "n/a"


def _technicals_line(tech):
    if tech is None:
        return "n/a"
    return (
        f"vs 200DMA: {_fmt_signed_pct(tech['pct_vs_sma_200'])} | "
        f"RSI: {_fmt_rsi(tech['rsi_14'])} | "
        f"vol: {_fmt_ratio(tech['volume_ratio_20'])}"
    )


def build_email_html(conn):
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(SUMMARY_SQL)
        summary = cur.fetchone()

        cur.execute(SNAPSHOT_SQL)
        snapshot_rows = cur.fetchall()

        cur.execute(REALIZED_PNL_SQL)
        realized_pnl, realized_count = cur.fetchone().values()

        cur.execute(TECHNICALS_SQL)
        technicals = {row["symbol"]: row for row in cur.fetchall()}

    if summary is None:
        raise RuntimeError("mart_portfolio_summary returned no rows")

    ticker_rows = "".join(
        ROW_TEMPLATE.substitute(
            symbol=row["symbol"],
            current_price=f"{row['current_price']:.2f}",
            todays_change_pct=f"{row['todays_change_pct']:.2f}",
            change_color=_color(row["todays_change_pct"]),
            current_value=f"{row['current_value']:.2f}",
            unrealized_pnl=f"{row['unrealized_pnl']:.2f}",
            pnl_color=_color(row["unrealized_pnl"]),
        )
        for row in snapshot_rows
    )

    technicals_lines = "".join(
        TECH_LINE_TEMPLATE.substitute(
            symbol=row["symbol"],
            technicals_line=_technicals_line(technicals.get(row["symbol"])),
        )
        for row in snapshot_rows
    )

    html = EMAIL_TEMPLATE.substitute(
        price_date=summary["price_date"],
        total_current_value=f"{summary['total_current_value']:.2f}",
        total_invested=f"{summary['total_invested']:.2f}",
        total_unrealized_pnl=f"{summary['total_unrealized_pnl']:.2f}",
        total_unrealized_pct=f"{summary['total_unrealized_pct']:.2f}",
        unrealized_color=_color(summary["total_unrealized_pnl"]),
        holdings_count=summary["holdings_count"],
        realized_pnl=f"{realized_pnl:.2f}",
        realized_color=_color(realized_pnl),
        ticker_rows=ticker_rows,
        technicals_lines=technicals_lines,
    )
    subject = f"PSX Portfolio Update — {summary['price_date']}"
    return subject, html


def send_email(subject, html_body):
    sender = os.environ["SMTP_USER"]
    recipient = os.environ["EMAIL_TO"]

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = recipient
    msg.attach(MIMEText(html_body, "html"))

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls()
        server.login(sender, os.environ["SMTP_PASSWORD"])
        server.sendmail(sender, [recipient], msg.as_string())


def main():
    conn = psycopg2.connect(os.environ["NEON_DATABASE_URL"])
    try:
        subject, html = build_email_html(conn)
    finally:
        conn.close()

    send_email(subject, html)
    log.info("[EMAIL] Sent: %s", subject)


if __name__ == "__main__":
    main()
