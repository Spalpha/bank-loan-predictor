"""
preprocess.py
-------------
Loads the raw loan approval dataset, cleans it, encodes categorical
columns, and produces train/test splits ready for model training.
"""

import os
import pandas as pd
from sklearn.model_selection import train_test_split

RAW_PATH = os.path.join(os.path.dirname(__file__), "..", "dataset", "loan_approval_dataset.csv")
CLEAN_PATH = os.path.join(os.path.dirname(__file__), "..", "dataset", "clean_loan_dataset.csv")

FEATURE_COLUMNS = [
    "no_of_dependents",
    "education",
    "self_employed",
    "income_annum",
    "loan_amount",
    "loan_term",
    "cibil_score",
    "residential_assets_value",
    "commercial_assets_value",
    "luxury_assets_value",
    "bank_asset_value",
    "total_asset_value",
]
ASSET_COLUMNS = [
    "residential_assets_value",
    "commercial_assets_value",
    "luxury_assets_value",
    "bank_asset_value",
]
TARGET_COLUMN = "loan_status"


def load_raw(path: str = RAW_PATH) -> pd.DataFrame:
    df = pd.read_csv(path)
    df.columns = [c.strip() for c in df.columns]
    return df


def clean(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # Strip whitespace from string/object columns (common issue in this dataset)
    obj_cols = df.select_dtypes(include="object").columns
    for c in obj_cols:
        df[c] = df[c].astype(str).str.strip()

    # Drop identifier column if present
    if "loan_id" in df.columns:
        df = df.drop(columns=["loan_id"])

    # Drop rows missing the target
    df = df.dropna(subset=[TARGET_COLUMN])

   
    if all(c in df.columns for c in ASSET_COLUMNS):
        df["total_asset_value"] = df[ASSET_COLUMNS].sum(axis=1)

    # Fill any missing numeric values with the column median
    numeric_cols = [c for c in FEATURE_COLUMNS if c in df.columns and pd.api.types.is_numeric_dtype(df[c])]
    for c in numeric_cols:
        df[c] = df[c].fillna(df[c].median())

    # Encode categoricals: education, self_employed -> 0/1
    df["education"] = df["education"].map({"Graduate": 1, "Not Graduate": 0})
    df["self_employed"] = df["self_employed"].map({"Yes": 1, "No": 0})

    # Encode target: Approved -> 1, Rejected -> 0
    df[TARGET_COLUMN] = df[TARGET_COLUMN].map({"Approved": 1, "Rejected": 0})

    df = df.dropna(subset=["education", "self_employed", TARGET_COLUMN])
    return df


def get_train_test_split(test_size: float = 0.2, random_state: int = 42):
    df = clean(load_raw())
    X = df[FEATURE_COLUMNS]
    y = df[TARGET_COLUMN]
    return train_test_split(X, y, test_size=test_size, random_state=random_state, stratify=y)


if __name__ == "__main__":
    df = clean(load_raw())
    df.to_csv(CLEAN_PATH, index=False)
    print(f"Clean dataset saved to {CLEAN_PATH}")
    print(df.head())
    print("\nClass balance:")
    print(df[TARGET_COLUMN].value_counts(normalize=True))
