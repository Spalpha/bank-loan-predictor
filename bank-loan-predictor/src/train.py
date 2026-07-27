"""
train.py
--------
Trains three classifiers (Logistic Regression, Random Forest, SVM) on the
loan approval dataset, evaluates each with Accuracy / Precision / Recall /
F1-Score, and saves the best-performing model (by F1-Score) as a pickle
file for use by the FastAPI service.
"""

import os
import pickle

import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC

from preprocess import get_train_test_split

MODEL_DIR = os.path.join(os.path.dirname(__file__), "..", "models")
MODEL_PATH = os.path.join(MODEL_DIR, "best_loan_model.pkl")


def evaluate(name, model, X_test, y_test):
    preds = model.predict(X_test)
    acc = accuracy_score(y_test, preds)
    prec = precision_score(y_test, preds, zero_division=0)
    rec = recall_score(y_test, preds, zero_division=0)
    f1 = f1_score(y_test, preds, zero_division=0)
    cm = confusion_matrix(y_test, preds)

    print(f"\n=== {name} ===")
    print(f"Accuracy : {acc:.4f}")
    print(f"Precision: {prec:.4f}")
    print(f"Recall   : {rec:.4f}")
    print(f"F1-Score : {f1:.4f}")
    print("Confusion Matrix:")
    print(cm)

    return {"name": name, "model": model, "accuracy": acc, "precision": prec,
            "recall": rec, "f1": f1}


def main():
    X_train, X_test, y_train, y_test = get_train_test_split()

    # Scale features (helps Logistic Regression and SVM converge / perform well)
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    results = []

    # 1. Logistic Regression
    log_reg = LogisticRegression(max_iter=1000, random_state=42)
    log_reg.fit(X_train_scaled, y_train)
    results.append(evaluate("Logistic Regression", log_reg, X_test_scaled, y_test))

    # 2. Random Forest (doesn't need scaling, but we reuse the scaled data for consistency)
    rf = RandomForestClassifier(n_estimators=200, random_state=42)
    rf.fit(X_train, y_train)
    results.append(evaluate("Random Forest", rf, X_test, y_test))

    # 3. Support Vector Machine
    svm = SVC(kernel="rbf", probability=True, random_state=42)
    svm.fit(X_train_scaled, y_train)
    results.append(evaluate("SVM", svm, X_test_scaled, y_test))

    # Pick best model by F1-score
    best = max(results, key=lambda r: r["f1"])
    print(f"\n>>> Best model: {best['name']} (F1-Score = {best['f1']:.4f}) <<<")

    os.makedirs(MODEL_DIR, exist_ok=True)
    payload = {
        "model": best["model"],
        "model_name": best["name"],
        "scaler": scaler if best["name"] in ("Logistic Regression", "SVM") else None,
        "feature_columns": list(X_train.columns),
        "metrics": {k: v for k, v in best.items() if k not in ("name", "model")},
    }
    with open(MODEL_PATH, "wb") as f:
        pickle.dump(payload, f)
    print(f"Saved best model to {MODEL_PATH}")

    # Summary table
    summary = pd.DataFrame(
        [{"Model": r["name"], "Accuracy": r["accuracy"], "Precision": r["precision"],
          "Recall": r["recall"], "F1-Score": r["f1"]} for r in results]
    )
    print("\n=== Comparison Summary ===")
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
