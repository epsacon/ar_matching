from fastapi import FastAPI, HTTPException, Security, Depends  # ADD Security, Depends
from fastapi.security import APIKeyHeader  # ADD this line
from pydantic import BaseModel
from typing import List, Optional, Dict
import uvicorn
from rapidfuzz import fuzz
from datetime import datetime
from collections import defaultdict
import os  # ADD this if not already imported

app = FastAPI(title="AR Reconciliation Engine", version="11.0")

# API Key Security
API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=True)
def get_api_key(api_key: str = Security(api_key_header)):
    """Validate API key from header"""
    correct_api_key = os.getenv("API_KEY")
    if not correct_api_key:
        raise HTTPException(status_code=500, detail="API_KEY not configured on server")
    if api_key != correct_api_key:
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing API Key"
        )
    return api_key
# === END OF SECURITY SECTION ===

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "ar-matching-api",
        "version": "1.0.0"
    }

# === 1. INPUT MODELS (NO FEES) ===
class Payment(BaseModel):
    payment_id: str
    invoice_ids: List[str] = []           # Must list all target invoices
    customer_name: str = ""
    memo_text: str = ""
    amount: float                         # WHAT YOU RECEIVE
    is_negative_payment: bool = False     # True = credit
    payment_date: str                     # YYYYMMDD
    value_date: Optional[str] = None
    payment_terms_hint: str = ""

class OpenItem(BaseModel):
    invoice_id: str
    customer_name: str
    total_open_amount: float
    due_in_date: str
    isOpen: bool = True
    payment_terms: str = ""
    memo_line: str = ""
    is_credit: bool = False

class ReconciliationRequest(BaseModel):
    payments: List[Payment]
    open_items: List[OpenItem]

# === 2. OUTPUT MODEL ===
class MatchGroup(BaseModel):
    payment_ids: List[str]
    invoice_ids: List[str]
    total_payment_amount: float
    total_invoice_amount: float
    net_amount_diff: float
    avg_score: float
    id_scores: List[float]
    amount_scores: List[float]
    name_scores: List[float]
    date_scores: List[float]
    memo_scores: List[float]
    terms_scores: List[float]
    confidence: str
    reason: str = ""
    is_negative_payment: bool = False
    payment_memo_text: str = ""
    invoice_payment_terms: List[str] = []
    invoice_memo_lines: List[str] = []
    invoice_credit_flags: List[bool] = []

class ReconciliationSummary(BaseModel):
    high_confidence_payments: int
    hitl_review_payments: int
    no_match_payments: int
    no_match_invoices: int
    total_payments_processed: int
    total_invoices_processed: int

class ReconciliationResponse(BaseModel):
    high_confidence: List[MatchGroup]
    hitl_review: List[MatchGroup]
    no_match: List[MatchGroup]
    summary: ReconciliationSummary

# === 3. SCORING FUNCTIONS ===
def name_score(p1: str, p2: str) -> float:
    if not p1 or not p2: return 0.0
    s = fuzz.token_set_ratio(p1.upper(), p2.upper())
    if s == 100: return 100.0
    if s >= 95: return 95.0
    if s >= 90: return 90.0
    if s >= 80: return 80.0
    if s >= 70: return 70.0
    return 0.0

def date_score(pay_date: str, due_date: str, value_date: Optional[str] = None) -> float:
    try:
        pay = datetime.strptime(value_date or pay_date, "%Y%m%d")
        due = datetime.strptime(due_date, "%Y%m%d")
        days = abs((pay - due).days)
        if days == 0: return 100.0
        if days <= 1: return 95.0
        if days <= 3: return 90.0
        if days <= 7: return 80.0
        if days <= 10: return 70.0
        if days <= 30: return 50.0
        return 20.0
    except: return 50.0

def memo_line_score(pay_memo: str, inv_memo: str) -> float:
    if not pay_memo or not inv_memo: return 0.0
    score = fuzz.token_set_ratio(pay_memo.upper(), inv_memo.upper())
    if score >= 90: return 100.0
    if score >= 70: return 70.0
    return 0.0

def payment_terms_score(pay_hint: str, inv_terms: str) -> float:
    if not inv_terms: return 0.0
    pay_norm = pay_hint.upper() if pay_hint else ""
    inv_norm = inv_terms.upper()
    if pay_norm == inv_norm: return 100.0
    if pay_norm in inv_norm or inv_norm in pay_hint: return 80.0
    if inv_norm in {"NET 30", "NET 15", "DUE ON RECEIPT", "2/10 NET 30"}: return 50.0
    return 0.0

# === 4. ENGINE: 1:1 → N:1 → 1:N ===
@app.post("/reconcile", response_model=ReconciliationResponse, dependencies=[Depends(get_api_key)])
async def reconcile(request: ReconciliationRequest):
    if len(request.payments) > 1000 or len(request.open_items) > 1000:
        raise HTTPException(400, "Max 1000 payments and 1000 open items")

    inv_map = {inv.invoice_id: inv for inv in request.open_items if inv.isOpen}
    pay_map = {pay.payment_id: pay for pay in request.payments}
    used_invoices = set()
    used_payments = set()

    high_conf = []
    hitl = []
    no_match = []

    # === STEP 1: 1:1 MATCHING (One payment → one invoice) ===
    for pay in request.payments:
        if pay.payment_id in used_payments: continue
        if len(pay.invoice_ids) != 1: continue  # Only 1:1

        iid = pay.invoice_ids[0]
        if iid not in inv_map or iid in used_invoices: continue
        inv = inv_map[iid]

        net_diff = abs(pay.amount - inv.total_open_amount)
        amount_score_net = 100.0 if net_diff <= 1.0 else 95.0 if net_diff <= 5.0 else 60.0

        name_s = name_score(pay.customer_name, inv.customer_name)
        date_s = date_score(pay.payment_date, inv.due_in_date, pay.value_date)
        memo_s = memo_line_score(pay.memo_text, inv.memo_line)
        terms_s = payment_terms_score(pay.payment_terms_hint, inv.payment_terms)

        final_score = min(100.0,
            0.50 * 100.0 +
            0.40 * amount_score_net +
            0.05 * name_s +
            0.025 * date_s +
            0.015 * memo_s +
            0.01 * terms_s
        )

        if final_score >= 90 and net_diff <= 1.0:
            group = MatchGroup(
                payment_ids=[pay.payment_id],
                invoice_ids=[iid],
                total_payment_amount=pay.amount,
                total_invoice_amount=inv.total_open_amount,
                net_amount_diff=net_diff,
                avg_score=round(final_score, 2),
                id_scores=[100.0],
                amount_scores=[amount_score_net],
                name_scores=[name_s],
                date_scores=[date_s],
                memo_scores=[memo_s],
                terms_scores=[terms_s],
                confidence="high",
                reason="1:1 perfect match",
                is_negative_payment=pay.is_negative_payment,
                payment_memo_text=pay.memo_text,
                invoice_payment_terms=[inv.payment_terms],
                invoice_memo_lines=[inv.memo_line],
                invoice_credit_flags=[inv.is_credit]
            )

            # Check for egregious name mismatch only if both names exist
            if pay.customer_name.strip() and inv.customer_name.strip():
                if name_s < 85:  # CHANGED from 40 to 85
                    group.confidence = "hitl"
                    if name_s < 40:
                        group.reason = "1:1 match but customer name mismatch - review required"
                    else:
                        group.reason = f"1:1 match but name similarity only {name_s}% - review required"
                    hitl.append(group)
                    used_invoices.add(iid)
                    used_payments.add(pay.payment_id)
                    continue

            high_conf.append(group)
            used_invoices.add(iid)
            used_payments.add(pay.payment_id)

    # === STEP 2: N:1 (Many payments → one invoice) ===
    inv_to_pays = defaultdict(list)
    for pay in request.payments:
        if pay.payment_id in used_payments: continue

        # ONLY include payments that reference EXACTLY ONE invoice
        # Payments with multiple invoices belong in STEP 3 (1:N)
        if len(pay.invoice_ids) == 1:
            iid = pay.invoice_ids[0]
            if iid in inv_map and iid not in used_invoices:
                inv_to_pays[iid].append(pay)

    for inv_id, pays in inv_to_pays.items():
        inv = inv_map[inv_id]

        net_pay = sum((-1 if pay.is_negative_payment else 1) * pay.amount for pay in pays)
        net_diff = abs(net_pay - inv.total_open_amount)
        amount_score_net = 100.0 if net_diff <= 1.0 else 95.0 if net_diff <= 5.0 else 60.0

        soft_scores = []
        for pay in pays:
            soft_scores.append({
                "name": name_score(pay.customer_name, inv.customer_name),
                "date": date_score(pay.payment_date, inv.due_in_date, pay.value_date),
                "memo": memo_line_score(pay.memo_text, inv.memo_line),
                "terms": payment_terms_score(pay.payment_terms_hint, inv.payment_terms)
            })

        # Check for individual name score violations
        force_hitl = False
        force_hitl_reason = ""
        for pay, scores in zip(pays, soft_scores):
            if pay.customer_name.strip() and inv.customer_name.strip():
                if scores["name"] < 85:
                    force_hitl = True
                    force_hitl_reason = f"N:1 match but {pay.payment_id} has {scores['name']:.0f}% name similarity - review required"
                    break  # Found one bad match, that's enough

        avg_name = sum(s["name"] for s in soft_scores) / len(soft_scores)
        avg_date = sum(s["date"] for s in soft_scores) / len(soft_scores)
        avg_memo = sum(s["memo"] for s in soft_scores) / len(soft_scores)
        avg_terms = sum(s["terms"] for s in soft_scores) / len(soft_scores)

        final_score = min(100.0,
            0.50 * 100.0 +
            0.40 * amount_score_net +
            0.05 * avg_name +
            0.025 * avg_date +
            0.015 * avg_memo +
            0.01 * avg_terms
        )

        pay_ids = [pay.payment_id for pay in pays]
        group = MatchGroup(
            payment_ids=pay_ids,
            invoice_ids=[inv_id],
            total_payment_amount=sum(pay.amount for pay in pays),
            total_invoice_amount=inv.total_open_amount,
            net_amount_diff=net_diff,
            avg_score=round(final_score, 2),
            id_scores=[100.0] * len(pays),
            amount_scores=[amount_score_net] * len(pays),
            name_scores=[s["name"] for s in soft_scores],
            date_scores=[s["date"] for s in soft_scores],
            memo_scores=[s["memo"] for s in soft_scores],
            terms_scores=[s["terms"] for s in soft_scores],
            confidence="",
            reason="",
            is_negative_payment=any(pay.is_negative_payment for pay in pays),
            payment_memo_text="; ".join(pay.memo_text for pay in pays),
            invoice_payment_terms=[inv.payment_terms],
            invoice_memo_lines=[inv.memo_line],
            invoice_credit_flags=[inv.is_credit]
        )

        # Check for forced HITL first (due to name score violations)
        if force_hitl:
            group.confidence = "hitl"
            group.reason = force_hitl_reason
            hitl.append(group)
        elif final_score >= 90 and net_diff <= 1.0:
            group.confidence = "high"
            group.reason = "N:1 perfect net match"
            high_conf.append(group)
        elif final_score >= 80:
            group.confidence = "hitl"
            group.reason = "N:1 good match"
            hitl.append(group)
        else:
            group.confidence = "no_match"
            group.reason = "N:1 score too low"
            no_match.append(group)

        # Always mark invoice as used, regardless of confidence
        used_invoices.add(inv_id)
        for pay in pays:
            used_payments.add(pay.payment_id)

    # === STEP 3: 1:N (One payment → many invoices) ===
    for pay in request.payments:
        if pay.payment_id in used_payments: continue
        if len(pay.invoice_ids) <= 1: continue  # Skip 1:1

        valid_invoices = [
            inv_map[iid] for iid in pay.invoice_ids
            if iid in inv_map and iid not in used_invoices
        ]

        if len(valid_invoices) <= 1:
            no_match.append(MatchGroup(
                payment_ids=[pay.payment_id],
                invoice_ids=[],
                total_payment_amount=pay.amount,
                total_invoice_amount=0.0,
                net_amount_diff=pay.amount,
                avg_score=0.0,
                id_scores=[], amount_scores=[], name_scores=[], date_scores=[],
                memo_scores=[], terms_scores=[],
                confidence="no_match",
                reason="No valid multi-invoice match",
                is_negative_payment=pay.is_negative_payment,
                payment_memo_text=pay.memo_text
            ))
            used_payments.add(pay.payment_id)
            continue

        net_open = sum((-1 if inv.is_credit else 1) * inv.total_open_amount for inv in valid_invoices)
        target = -pay.amount if pay.is_negative_payment else pay.amount
        net_diff = abs(net_open - target)
        amount_score_net = 100.0 if net_diff <= 1.0 else 95.0 if net_diff <= 5.0 else 60.0

        soft_scores = []
        for inv in valid_invoices:
            soft_scores.append({
                "name": name_score(pay.customer_name, inv.customer_name),
                "date": date_score(pay.payment_date, inv.due_in_date, pay.value_date),
                "memo": memo_line_score(pay.memo_text, inv.memo_line),
                "terms": payment_terms_score(pay.payment_terms_hint, inv.payment_terms)
            })

        # Check for individual name score violations (same as N:1 logic)
        force_hitl = False
        force_hitl_reason = ""
        for inv, scores in zip(valid_invoices, soft_scores):
            if pay.customer_name.strip() and inv.customer_name.strip():
                if scores["name"] < 85:
                    force_hitl = True
                    force_hitl_reason = f"1:N match but {inv.invoice_id} has {scores['name']:.0f}% name similarity - review required"
                    break  # Found one bad match, that's enough


        avg_name = sum(s["name"] for s in soft_scores) / len(soft_scores)
        avg_date = sum(s["date"] for s in soft_scores) / len(soft_scores)
        avg_memo = sum(s["memo"] for s in soft_scores) / len(soft_scores)
        avg_terms = sum(s["terms"] for s in soft_scores) / len(soft_scores)

        final_score = min(100.0,
            0.50 * 100.0 +
            0.40 * amount_score_net +
            0.05 * avg_name +
            0.025 * avg_date +
            0.015 * avg_memo +
            0.01 * avg_terms
        )

        inv_ids = [inv.invoice_id for inv in valid_invoices]
        group = MatchGroup(
            payment_ids=[pay.payment_id],
            invoice_ids=inv_ids,
            total_payment_amount=pay.amount,
            total_invoice_amount=net_open,
            net_amount_diff=net_diff,
            avg_score=round(final_score, 2),
            id_scores=[100.0] * len(inv_ids),
            amount_scores=[amount_score_net] * len(inv_ids),
            name_scores=[s["name"] for s in soft_scores],
            date_scores=[s["date"] for s in soft_scores],
            memo_scores=[s["memo"] for s in soft_scores],
            terms_scores=[s["terms"] for s in soft_scores],
            confidence="",
            reason="",
            is_negative_payment=pay.is_negative_payment,
            payment_memo_text=pay.memo_text,
            invoice_payment_terms=[inv.payment_terms for inv in valid_invoices],
            invoice_memo_lines=[inv.memo_line for inv in valid_invoices],
            invoice_credit_flags=[inv.is_credit for inv in valid_invoices]
        )

        # Check for forced HITL first (due to name score violations)
        if force_hitl:
            group.confidence = "hitl"
            group.reason = force_hitl_reason
            hitl.append(group)
        elif final_score >= 90 and net_diff <= 1.0:
            group.confidence = "high"
            group.reason = "1:N perfect net match"
            high_conf.append(group)
        elif final_score >= 80:
            group.confidence = "hitl"
            group.reason = "1:N good match"
            hitl.append(group)
        else:
            group.confidence = "no_match"
            group.reason = "1:N score too low"
            no_match.append(group)

        # Always mark invoices as used, regardless of confidence
        used_invoices.update(inv_ids)
        used_payments.add(pay.payment_id)

    # === STEP 4.5: FUZZY MATCH within Customer Groups ===
    # Get unmatched items with customer names
    unmatched_payments = [
        pay for pay in request.payments
        if pay.payment_id not in used_payments and pay.customer_name.strip()
    ]

    unmatched_invoices = [
        inv for inv in request.open_items
        if inv.invoice_id not in used_invoices and inv.isOpen and inv.customer_name.strip()
    ]

    # Create fuzzy customer groups
    customer_groups = []  # Each group: {'name': str, 'payments': [], 'invoices': []}

    # Group payments by fuzzy customer name
    for pay in unmatched_payments:
        found_group = False
        for group in customer_groups:
            if name_score(pay.customer_name, group['name']) >= 90:
                group['payments'].append(pay)
                found_group = True
                break

        if not found_group:
            customer_groups.append({
                'name': pay.customer_name,
                'payments': [pay],
                'invoices': []
            })

    # Group invoices by fuzzy customer name
    for inv in unmatched_invoices:
        found_group = False
        for group in customer_groups:
            if name_score(inv.customer_name, group['name']) >= 90:
                group['invoices'].append(inv)
                found_group = True
                break

        if not found_group:
            customer_groups.append({
                'name': inv.customer_name,
                'payments': [],
                'invoices': [inv]
            })

    # Within each customer group, do 1:1 fuzzy matching
    for group in customer_groups:
        for pay in group['payments']:
            if pay.payment_id in used_payments:
                continue

            best_match = None
            best_score = 0

            for inv in group['invoices']:
                if inv.invoice_id in used_invoices:
                    continue

                # Score this potential match
                amount_diff = abs(pay.amount - inv.total_open_amount)
                amount_score_val = 100.0 if amount_diff <= 1.0 else 95.0 if amount_diff <= 5.0 else 60.0

                name_s = name_score(pay.customer_name, inv.customer_name)
                date_s = date_score(pay.payment_date, inv.due_in_date, pay.value_date)
                memo_s = memo_line_score(pay.memo_text, inv.memo_line)
                terms_s = payment_terms_score(pay.payment_terms_hint, inv.payment_terms)

                final_score = min(100.0,
                                  0.40 * amount_score_val +
                                  0.25 * name_s +
                                  0.20 * date_s +
                                  0.10 * memo_s +
                                  0.05 * terms_s
                                  )

                # Keep track of best match
                if final_score > best_score and final_score >= 70:
                    best_score = final_score
                    best_match = (inv, amount_diff, amount_score_val, name_s, date_s, memo_s, terms_s)

            # If found a good match, create a match group
            if best_match:
                inv, amount_diff, amount_score_val, name_s, date_s, memo_s, terms_s = best_match

                group_match = MatchGroup(
                    payment_ids=[pay.payment_id],
                    invoice_ids=[inv.invoice_id],
                    total_payment_amount=pay.amount,
                    total_invoice_amount=inv.total_open_amount,
                    net_amount_diff=amount_diff,
                    avg_score=round(best_score, 2),
                    id_scores=[0.0],
                    amount_scores=[amount_score_val],
                    name_scores=[name_s],
                    date_scores=[date_s],
                    memo_scores=[memo_s],
                    terms_scores=[terms_s],
                    confidence="",
                    reason="",
                    is_negative_payment=pay.is_negative_payment,
                    payment_memo_text=pay.memo_text,
                    invoice_payment_terms=[inv.payment_terms],
                    invoice_memo_lines=[inv.memo_line],
                    invoice_credit_flags=[inv.is_credit]
                )

                if best_score >= 85 and amount_diff <= 1.0:
                    group_match.confidence = "high"
                    group_match.reason = "Fuzzy match - exact amount + strong signals"
                    high_conf.append(group_match)
                    used_invoices.add(inv.invoice_id)
                    used_payments.add(pay.payment_id)
                elif best_score >= 75:
                    group_match.confidence = "hitl"
                    group_match.reason = "Fuzzy match - good candidate"
                    hitl.append(group_match)
                    used_invoices.add(inv.invoice_id)
                    used_payments.add(pay.payment_id)


    # === STEP 4: UNMATCHED ===
    for pay in request.payments:
        if pay.payment_id not in used_payments:
            no_match.append(MatchGroup(
                payment_ids=[pay.payment_id],
                invoice_ids=[],
                total_payment_amount=pay.amount,
                total_invoice_amount=0.0,
                net_amount_diff=pay.amount,
                avg_score=0.0,
                id_scores=[], amount_scores=[], name_scores=[], date_scores=[],
                memo_scores=[], terms_scores=[],
                confidence="no_match",
                reason="Unmatched payment",
                is_negative_payment=pay.is_negative_payment,
                payment_memo_text=pay.memo_text
            ))

    for inv in request.open_items:
        if inv.invoice_id not in used_invoices and inv.isOpen:
            no_match.append(MatchGroup(
                payment_ids=[],
                invoice_ids=[inv.invoice_id],
                total_payment_amount=0.0,
                total_invoice_amount=inv.total_open_amount,
                net_amount_diff=inv.total_open_amount,
                avg_score=0.0,
                id_scores=[], amount_scores=[], name_scores=[], date_scores=[],
                memo_scores=[], terms_scores=[],
                confidence="no_match",
                reason="Unmatched invoice",
                invoice_payment_terms=[inv.payment_terms],
                invoice_memo_lines=[inv.memo_line],
                invoice_credit_flags=[inv.is_credit]
            ))

    # Calculate summary statistics (AFTER all processing is done)
    hc_payments = sum(len(g.payment_ids) for g in high_conf)
    hitl_payments = sum(len(g.payment_ids) for g in hitl)
    nm_payments = sum(len(g.payment_ids) for g in no_match if len(g.payment_ids) > 0)
    nm_invoices = sum(1 for g in no_match if len(g.invoice_ids) > 0 and len(g.payment_ids) == 0)

    summary = ReconciliationSummary(
        high_confidence_payments=hc_payments,
        hitl_review_payments=hitl_payments,
        no_match_payments=nm_payments,
        no_match_invoices=nm_invoices,
        total_payments_processed=len(request.payments),
        total_invoices_processed=len(request.open_items)
    )

    return ReconciliationResponse(
        high_confidence=high_conf,
        hitl_review=hitl,
        no_match=no_match,
        summary=summary
    )

# === 5. RUN ===
if __name__ == "__main__":
    uvicorn.run("reconciliation:app", host="0.0.0.0", port=8000, reload=True)