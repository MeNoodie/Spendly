"""
main.py — Spendly "Buy or Wait?" Competition Batch Entry Point

Usage:
    python -m code.main             # Run full competition batch on dataset/requests.csv (250 rows)
    python -m code.main --sample    # Run validation batch on dataset/sample_requests.csv (25 rows) & score
"""
import sys
import time
import os
import pandas as pd
from pathlib import Path
from dotenv import load_dotenv

# Allow imports from Spendly root
sys.path.insert(0, str(Path(__file__).parent.parent))

load_dotenv()

DATASET = Path(os.getenv("DATASET_PATH", "./dataset"))


def main():
    is_sample = "--sample" in sys.argv
    print("=" * 60)
    mode = "SAMPLE VALIDATION (25 cases)" if is_sample else "FULL BATCH (250 requests)"
    print(f"Spendly — Buy or Wait? Runner [{mode}]")
    print("=" * 60)

    # ── Step 1: Initialize DB (only seed if empty or --seed flag) ────────
    print("\n[1/4] Checking database...")
    from code.db import get_db, init_schema
    init_schema()
    conn = get_db()
    user_count = conn.execute("SELECT count(*) FROM users").fetchone()[0]
    if user_count == 0 or "--seed" in sys.argv:
        print("      Database empty or --seed passed. Seeding data...")
        from code.db.seed import seed_all
        seed_all()
    else:
        print(f"      Database ready ({user_count} users loaded).")

    # ── Step 2: Load requests ────────────────────────────────
    target_csv = "sample_requests.csv" if is_sample else "requests.csv"
    print(f"\n[2/4] Loading {target_csv}...")
    requests_df = pd.read_csv(DATASET / target_csv)
    print(f"      {len(requests_df)} requests found.")

    # ── Step 3: Run agent for each request ───────────────────
    print("\n[3/4] Running agent...")
    from code.agent.graph import run_agent
    from code.agent.state import AgentState
    from code.utils.output_writer import state_to_row, write_output_csv
    from code.db.queries import save_decision

    output_rows = []
    errors = []

    for idx, req in requests_df.iterrows():
        request_id = req["request_id"]
        user_id = req["user_id"]
        print(f"      [{idx+1}/{len(requests_df)}] {request_id} ({user_id})...", end=" ", flush=True)

        start_ms = time.time()
        try:
            initial_state: AgentState = {
                "request_id": str(request_id),
                "user_id": str(user_id),
                "request_date": str(req["request_date"]),
                "request_type": str(req.get("request_type", "")),
                "requested_amount": float(req["requested_amount"]),
                "desired_completion_date": str(req["desired_completion_date"]),
                "allows_partial": str(req.get("allows_partial_payment", "false")).lower() == "true",
                "request_text": str(req.get("request_text", "")),
                "profile": {},
                "income_sources": [],
                "expenses": [],
                "pending_transactions": [],
                "payment_options": [],
                "messages": [],
                "images": [],
                "resolved_income": [],
                "resolved_expenses": [],
                "active_income": [],
                "active_expenses": [],
                "daily_balances": [],
                "amount_safe_to_pay": 0.0,
                "earliest_full_payment_date": None,
                "candidate_plans": [],
                "selected_plan": None,
                "spending_changes": [],
                "affordability_status": "not_affordable",
                "recommended_method": "not_recommended",
                "payment_plan": [],
                "explanation": "",
                "llm_tokens_used": 0,
                "processing_ms": 0,
                "errors": [],
            }

            final_state = run_agent(initial_state)
            elapsed_ms = int((time.time() - start_ms) * 1000)
            final_state["processing_ms"] = elapsed_ms

            # Save decision
            save_decision({
                **final_state,
                "requested_amount": float(req["requested_amount"]),
                "request_date": str(req["request_date"]),
                "desired_completion_date": str(req["desired_completion_date"]),
                "allows_partial": final_state.get("allows_partial", False),
                "request_text": str(req.get("request_text", "")),
                "request_type": str(req.get("request_type", "")),
            })

            row = state_to_row(final_state)
            output_rows.append(row)
            print(f"[OK] {final_state.get('affordability_status')} | {final_state.get('recommended_method')} ({elapsed_ms}ms)")

        except Exception as e:
            elapsed_ms = int((time.time() - start_ms) * 1000)
            print(f"[ERR] {e}")

            errors.append({"request_id": request_id, "error": str(e)})
            output_rows.append({
                "request_id": request_id,
                "amount_safe_to_pay": 0.0,
                "affordability_status": "not_affordable",
                "recommended_payment_method": "not_recommended",
                "payment_plan": "none",
                "earliest_date_for_full_payment": "",
                "spending_changes_needed": "none",
                "decision_explanation": f"System error processing request: {e}",
            })

    # ── Step 4: Write output.csv ─────────────────────────────
    out_file = "./output_sample.csv" if is_sample else "./output.csv"
    print(f"\n[4/4] Writing {out_file}...")
    write_output_csv(output_rows, output_path=out_file)

    if errors:
        print(f"\n[WARN] {len(errors)} errors occurred:")
        for err in errors[:5]:
            print(f"   - {err['request_id']}: {err['error']}")

    # If sample run, trigger scorer
    if is_sample:
        print("\nScoring against ground truth...")
        from code.utils.scorer import score
        score(sample_output_path=out_file)

    print("\n[DONE] Run completed successfully.")



if __name__ == "__main__":
    main()
