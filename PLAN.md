# Spendly — Hackathon Execution Plan
# "Buy or Wait?" | Deadline: 18:00 IST | Time Remaining: ~3h 55m

---

## Phase Map

```
Phase 1 [45 min] → DB Foundation      → schema + seed + queries
Phase 2 [75 min] → Core Agent Engine  → forecaster + planner + image reader
Phase 3 [60 min] → LangGraph + Output → graph wiring + main.py batch loop
Phase 4 [35 min] → Validate + Package → score vs samples + usage report + zip
                                         ─────────────────────────
                                         Total: ~215 min (3h 35m) ✅
```

---

## Phase 1 — DB Foundation (45 min)
**Goal:** All competition data loaded into SQLite, queryable by user_id + request_id.

### Files
| File | What to Build |
|---|---|
| `code/db/schema.sql` | All table DDL |
| `code/db/seed.py` | Parse all CSVs and INSERT into SQLite |
| `code/db/queries.py` | get_user_context(user_id, request_id) → full dict |
| `code/db/__init__.py` | DB connection singleton (get_db()) |

### CSV → Table Mapping
| CSV File | SQLite Table |
|---|---|
| financial_profiles.csv | users + financial_profiles |
| financial_events.csv | income_sources + expenses + pending_transactions |
| request_payment_options.csv | payment_options |
| exchange_rates.csv | exchange_rates |
| messages.csv | event_messages |
| images.csv | uploaded_documents |

### Completion Criteria
- [ ] python code/db/seed.py runs without error
- [ ] Can query any user's full financial context in one call
- [ ] All 250 request_ids resolvable

---

## Phase 2 — Core Agent Engine (75 min)
**Goal:** Pure deterministic financial engine. No LLM yet (except image reader).

### Files
| File | What to Build |
|---|---|
| `code/agent/state.py` | AgentState TypedDict — shared state object across all nodes |
| `code/agent/nodes/data_loader.py` | Node 1: Load user context from SQLite into AgentState |
| `code/agent/nodes/image_reader.py` | Node 2: For events with NULL amount, call Vision LLM on PNG |
| `code/agent/nodes/message_processor.py` | Node 3: Apply message overrides (cancellations, amendments) |
| `code/agent/nodes/forecaster.py` | Node 4: Core 90-day cash flow simulator |
| `code/agent/nodes/planner.py` | Node 5: Generate + rank all eligible payment plans |
| `code/agent/nodes/explainer.py` | Node 6: LLM writes decision_explanation |
| `code/utils/currency.py` | convert(amount, from_curr, to_curr, date, db) |

### forecaster.py — Key Logic
```
Input:  current_balance, min_balance, recurring_expenses[], income_sources[],
        pending_transactions[], request_amount, request_date

Output:
  - day_by_day balance array [90 entries]
  - amount_safe_to_pay (binary search: largest amount where balance never < min)
  - earliest_date_for_full_payment

Rules:
  - Recurring expenses: project on due_day each month
  - Income: add only on next_credit_date if is_confirmed=True
  - Pending debit transactions: subtract on expected_date if status=pending
  - Ignore: cancelled, failed, duplicate events, unrealized investments
  - Pending CREDITS: ignore (per problem statement)
```

### planner.py — Plan Ranking (from problem_statement)
```
For each eligible method (check payment_methods_accepted):
  1. full_payment   → safe on request_date?
  2. installments   → for each payment_option, simulate all payments
  3. partial_payment → allows_partial=True, amount_safe_to_pay day-1, rest on earliest_full_date
  4. wait           → earliest_full_date <= desired_completion_date?
  5. not_recommended → fallback

Rank by:
  1. Completes by desired_completion_date
  2. No spending changes needed
  3. Minimize total amount paid
  4. Start payment earlier
  5. Fewer payments
  6. Lowest payment_option_id
```

### Completion Criteria
- [ ] forecaster.py correct balance simulation for sample user
- [ ] amount_safe_to_pay correct for request_01 (expected: 25256)
- [ ] planner.py correct for request_06 (expected: full_payment + stop:event_476)

---

## Phase 3 — LangGraph Graph + Batch Output (60 min)
**Goal:** Wire all nodes into LangGraph graph. Run batch on all 250 requests. Write output.csv.

### Files
| File | What to Build |
|---|---|
| `code/agent/graph.py` | LangGraph StateGraph — compile all nodes |
| `code/agent/__init__.py` | Export run_agent(user_id, request_id, row) |
| `code/main.py` | Batch loop: requests.csv → agent → output.csv |
| `code/utils/output_writer.py` | Format DecisionResult → correct CSV row |

### Node Sequence
```
START
 → load_user_context        (data_loader.py)
 → resolve_image_amounts    (image_reader.py)  [conditional: only if NULL amounts]
 → apply_message_overrides  (message_processor.py)
 → simulate_90_day_forecast (forecaster.py)
 → generate_payment_plans   (planner.py)
 → rank_and_select_plan     (planner.py)
 → build_spending_changes   (planner.py)
 → generate_explanation     (explainer.py)
END → return DecisionResult
```

### output.csv column order (exact)
```
request_id, amount_safe_to_pay, affordability_status, recommended_payment_method,
payment_plan, earliest_date_for_full_payment, spending_changes_needed, decision_explanation
```

### Completion Criteria
- [ ] python code/main.py completes without errors
- [ ] output.csv has exactly 251 lines (1 header + 250 rows)
- [ ] All amount_safe_to_pay satisfy 0 <= amount <= requested_amount

---

## Phase 4 — Validate + Package (35 min)
**Goal:** Score against 25 samples, fill usage report, create submission zip.

### Files
| File | What to Build |
|---|---|
| `code/utils/scorer.py` | Compare output.csv vs sample_requests.csv — print % match per column |
| `evaluation/usage_report.md` | Token usage: model, calls, input/output tokens, cost estimate |
| `code/utils/packager.py` | Create code.zip with all required files |

### Submission Checklist
- [ ] output.csv — 250 rows + header, 8 columns in exact order
- [ ] Every amount_safe_to_pay: 0 <= value <= requested_amount
- [ ] Every installment plan matches a payment_option exactly
- [ ] Every spending change targets a flexible expense only (is_flexible=True)
- [ ] evaluation/usage_report.md filled
- [ ] code.zip ready

---

## Environment (setup NOW before Phase 1)

requirements.txt contents:
  langgraph
  langchain
  langchain-google-genai
  pandas
  pillow
  python-dotenv
  fastapi
  uvicorn

.env file:
  GOOGLE_API_KEY=your_key_here
  DATABASE_URL=./spendly.db
  DATASET_PATH=./dataset

---

## Full Folder Structure

Spendly/
├── PLAN.md
├── .env                             (gitignored)
├── .gitignore
├── requirements.txt
├── output.csv                       (generated)
├── log.txt
├── code/
│   ├── main.py
│   ├── agent/
│   │   ├── __init__.py
│   │   ├── graph.py
│   │   ├── state.py
│   │   └── nodes/
│   │       ├── __init__.py
│   │       ├── data_loader.py
│   │       ├── image_reader.py
│   │       ├── message_processor.py
│   │       ├── forecaster.py
│   │       ├── planner.py
│   │       └── explainer.py
│   ├── db/
│   │   ├── __init__.py
│   │   ├── schema.sql
│   │   ├── seed.py
│   │   └── queries.py
│   └── utils/
│       ├── __init__.py
│       ├── currency.py
│       ├── output_writer.py
│       └── scorer.py
└── evaluation/
    └── usage_report.md
