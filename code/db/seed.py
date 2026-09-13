"""
seed.py — Load all competition CSV files into SQLite.

Run: python code/db/seed.py

Reads from: dataset/*.csv
Writes to:  spendly.db (DATABASE_URL in .env)
"""
import os
import sys
import pandas as pd
from pathlib import Path
from dotenv import load_dotenv

# Allow imports from project root
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

load_dotenv()

from code.db import get_db, init_schema

DATASET = Path(os.getenv("DATASET_PATH", "./dataset"))


def seed_all():
    print("Initializing schema...")
    init_schema()
    conn = get_db()

    print("Seeding financial_profiles...")
    seed_financial_profiles(conn)

    print("Seeding financial_events...")
    seed_financial_events(conn)

    print("Seeding request_payment_options...")
    seed_payment_options(conn)

    print("Seeding exchange_rates...")
    seed_exchange_rates(conn)

    print("Seeding messages...")
    seed_messages(conn)

    print("Seeding images...")
    seed_images(conn)

    conn.commit()
    print("Seeding complete.")


def seed_financial_profiles(conn):
    df = pd.read_csv(DATASET / "financial_profiles.csv")
    for _, row in df.iterrows():
        conn.execute(
            "INSERT OR IGNORE INTO users (id, source) VALUES (?, 'hackathon')",
            (row["user_id"],)
        )
        conn.execute(
            """INSERT OR REPLACE INTO financial_profiles
               (user_id, home_currency, current_available_balance, minimum_balance_to_keep,
                financial_priorities, expense_categories_to_protect,
                expense_categories_user_is_willing_to_reduce,
                expense_categories_user_is_willing_to_stop,
                payment_methods_user_will_consider, max_installment_months)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                row["user_id"],
                row.get("home_currency", "INR"),
                float(row.get("current_available_balance", 0)),
                float(row.get("minimum_balance_to_keep", 0)),
                str(row.get("financial_priorities") or ""),
                str(row.get("expense_categories_to_protect") or ""),
                str(row.get("expense_categories_user_is_willing_to_reduce") or ""),
                str(row.get("expense_categories_user_is_willing_to_stop") or ""),
                str(row.get("payment_methods_user_will_consider") or ""),
                float(row["max_installment_months"]) if pd.notna(row.get("max_installment_months")) else None,
            )
        )


def seed_financial_events(conn):
    df = pd.read_csv(DATASET / "financial_events.csv")
    for _, row in df.iterrows():
        amount = row.get("amount", None)
        amount = None if pd.isna(amount) else float(amount)
        min_amount = row.get("minimum_allowed_amount", None)
        min_amount = None if pd.isna(min_amount) else float(min_amount)
        linked_id = row.get("linked_event_id", None)
        linked_id = None if pd.isna(linked_id) else str(linked_id)

        conn.execute(
            """INSERT OR REPLACE INTO financial_events
               (event_id, user_id, event_type, description, category, direction,
                amount, currency, event_date, settlement_date, status,
                linked_event_id, flexibility, minimum_allowed_amount)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                row["event_id"],
                row["user_id"],
                row["event_type"],
                row.get("description", ""),
                row.get("category", ""),
                row.get("direction", "debit"),
                amount,
                row.get("currency", None),
                str(row["event_date"]),
                str(row["settlement_date"]) if pd.notna(row.get("settlement_date")) else str(row["event_date"]),
                row.get("status", "settled"),
                linked_id,
                row.get("flexibility", "fixed"),
                min_amount,
            )
        )


def seed_payment_options(conn):
    df = pd.read_csv(DATASET / "request_payment_options.csv")
    for _, row in df.iterrows():
        freq = row.get("payment_frequency_days", None)
        freq = None if pd.isna(freq) else float(freq)
        fee = row.get("financing_fee", 0.0)
        fee = 0.0 if pd.isna(fee) else float(fee)

        conn.execute(
            """INSERT OR REPLACE INTO payment_options
               (payment_option_id, request_id, payment_method, payment_amount,
                number_of_payments, first_payment_date, payment_frequency_days,
                financing_fee, total_payable_amount)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                row["payment_option_id"],
                row["request_id"],
                row["payment_method"],
                float(row["payment_amount"]),
                int(row.get("number_of_payments", 1)),
                str(row["first_payment_date"]),
                freq,
                fee,
                float(row["total_payable_amount"]),
            )
        )


def seed_exchange_rates(conn):
    df = pd.read_csv(DATASET / "exchange_rates.csv")
    for _, row in df.iterrows():
        conn.execute(
            """INSERT OR IGNORE INTO exchange_rates
               (rate_date, from_currency, to_currency, rate)
               VALUES (?, ?, ?, ?)""",
            (
                str(row["rate_date"]),
                str(row["from_currency"]),
                str(row["to_currency"]),
                float(row["rate"]),
            )
        )


def seed_messages(conn):
    df = pd.read_csv(DATASET / "messages.csv")
    for _, row in df.iterrows():
        req_id = row.get("request_id", None)
        req_id = None if pd.isna(req_id) else str(req_id)
        evt_id = row.get("related_event_id", None)
        evt_id = None if pd.isna(evt_id) else str(evt_id)

        conn.execute(
            """INSERT OR REPLACE INTO event_messages
               (message_id, user_id, request_id, related_event_id, sent_at, source_type, message_text)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                row["message_id"],
                row["user_id"],
                req_id,
                evt_id,
                str(row.get("sent_at", "")),
                str(row.get("source_type", "")),
                str(row.get("message_text", "")),
            )
        )


def seed_images(conn):
    df = pd.read_csv(DATASET / "images.csv")
    img_dir = DATASET / "media" / "images"
    for _, row in df.iterrows():
        image_id = row["image_id"]
        file_path = str(img_dir / f"{image_id}.png")
        req_id = row.get("request_id", None)
        req_id = None if pd.isna(req_id) else str(req_id)
        evt_id = row.get("related_event_id", None)
        evt_id = None if pd.isna(evt_id) else str(evt_id)

        conn.execute(
            """INSERT OR REPLACE INTO uploaded_documents
               (image_id, user_id, request_id, related_event_id, file_path, extraction_status)
               VALUES (?, ?, ?, ?, ?, 'pending')""",
            (
                image_id,
                row.get("user_id", None),
                req_id,
                evt_id,
                file_path,
            )
        )


if __name__ == "__main__":
    seed_all()
