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
