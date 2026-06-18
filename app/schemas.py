"""
SentinelBank — Pydantic Schemas for Transaction Input / Prediction Output

# VULNERABILITY: No input validation beyond Pydantic types
# - No range checks on `amount` (allows negative values, absurdly large numbers)
# - No enum validation on `type` (any string accepted)
# - No cross-field consistency checks
"""

from pydantic import BaseModel


class TransactionInput(BaseModel):
    """
    Transaction input matching PaySim-derived features.

    # VULNERABILITY: No field-level constraints (e.g., ge=0 on amount,
    # Literal/enum restriction on type). An attacker can submit
    # out-of-range or nonsensical values.
    """

    step: int
    type: str                   # VULNERABILITY: accepts any string, not restricted to CASH_IN/CASH_OUT/DEBIT/PAYMENT/TRANSFER
    amount: float               # VULNERABILITY: no min/max range check
    oldbalanceOrg: float
    newbalanceOrig: float
    oldbalanceDest: float
    newbalanceDest: float
    errorBalanceOrig: float     # computed feature
    errorBalanceDest: float     # computed feature
    type_CASH_IN: int           # one-hot encoded
    type_CASH_OUT: int
    type_DEBIT: int
    type_PAYMENT: int
    type_TRANSFER: int


class PredictionResponse(BaseModel):
    fraud_probability: float    # VULNERABILITY: raw float returned (enables model extraction attacks)
    fraud_label: str
    model_version: str
