"""
api/app.py
----------
FastAPI service exposing a /predict endpoint for the Bank Loan Approval
and Creditworthiness Predictor.

Run with:
    uvicorn api.app:app --reload --port 8000
(run from the project root: bank-loan-predictor/)
"""

import os
import pickle

import pandas as pd
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

MODEL_PATH = os.path.join(os.path.dirname(__file__), "..", "models", "best_loan_model.pkl")

app = FastAPI(
    title="Bank Loan Approval Predictor",
    description="Predicts whether a loan applicant is creditworthy.",
    version="1.0.0",
)

_artifact = None


def get_artifact():
    global _artifact
    if _artifact is None:
        if not os.path.exists(MODEL_PATH):
            raise HTTPException(
                status_code=500,
                detail="Model file not found. Run `python src/train.py` first.",
            )
        with open(MODEL_PATH, "rb") as f:
            _artifact = pickle.load(f)
    return _artifact


class LoanApplication(BaseModel):
    no_of_dependents: int = Field(..., ge=0, example=2)
    education: str = Field(..., example="Graduate", description="'Graduate' or 'Not Graduate'")
    self_employed: str = Field(..., example="No", description="'Yes' or 'No'")
    income_annum: float = Field(..., gt=0, example=4200000)
    loan_amount: float = Field(..., gt=0, example=15000000)
    loan_term: int = Field(..., gt=0, example=10)
    cibil_score: int = Field(..., ge=300, le=900, example=680)
    residential_assets_value: float = Field(..., ge=0, example=8000000)
    commercial_assets_value: float = Field(..., ge=0, example=2000000)
    luxury_assets_value: float = Field(..., ge=0, example=3000000)
    bank_asset_value: float = Field(..., ge=0, example=4000000)


class PredictionResponse(BaseModel):
    prediction_label: int
    status: str
    approval_probability: float


def build_feature_row(app_in: LoanApplication, feature_columns: list) -> pd.DataFrame:
    """Build the exact same feature set used during training, including the
    engineered total_asset_value column, in the same column order."""
    education_bin = 1 if app_in.education.strip().lower() == "graduate" else 0
    self_employed_bin = 1 if app_in.self_employed.strip().lower() == "yes" else 0
    total_asset_value = (
        app_in.residential_assets_value
        + app_in.commercial_assets_value
        + app_in.luxury_assets_value
        + app_in.bank_asset_value
    )

    row = {
        "no_of_dependents": app_in.no_of_dependents,
        "education": education_bin,
        "self_employed": self_employed_bin,
        "income_annum": app_in.income_annum,
        "loan_amount": app_in.loan_amount,
        "loan_term": app_in.loan_term,
        "cibil_score": app_in.cibil_score,
        "residential_assets_value": app_in.residential_assets_value,
        "commercial_assets_value": app_in.commercial_assets_value,
        "luxury_assets_value": app_in.luxury_assets_value,
        "bank_asset_value": app_in.bank_asset_value,
        "total_asset_value": total_asset_value,
    }
    return pd.DataFrame([row])[feature_columns]


@app.get("/")
def root():
    return {"message": "Bank Loan Approval Predictor API. POST to /predict."}


@app.post("/predict", response_model=PredictionResponse)
def predict(application: LoanApplication):
    artifact = get_artifact()
    model = artifact["model"]
    scaler = artifact["scaler"]
    feature_columns = artifact["feature_columns"]

    X = build_feature_row(application, feature_columns)

    # Apply the SAME scaler used at training time, only if the winning
    # model actually needed one (Logistic Regression / SVM). Tree-based
    # models (Random Forest) don't require scaling.
    X_model_input = scaler.transform(X) if scaler is not None else X

    pred = int(model.predict(X_model_input)[0])
    proba = float(model.predict_proba(X_model_input)[0][1])

    return PredictionResponse(
        prediction_label=pred,
        status="Approved" if pred == 1 else "Rejected",
        approval_probability=round(proba, 4),
    )
