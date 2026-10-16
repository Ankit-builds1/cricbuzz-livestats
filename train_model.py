# © 2026 Ankit Dash (github.com/Ankit-builds1) - Cricbuzz LiveStats. All rights reserved.
"""Train the match win predictor and save it to models/win_model.pkl."""
import joblib
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, roc_auc_score

from utils.db_connection import run_query
from pathlib import Path

from utils.features import FEATURES, build_training_set, load_history, mirror


MODEL_PATH = Path(__file__).resolve().parent / "models" / "win_model.pkl"


def train(verbose=True):
    """Train both models, keep the best, refit on all data. Returns the saved bundle."""
    hist = load_history(run_query)
    X, y = build_training_set(hist)

    # Time-based split: train on the oldest 80%, test on the newest 20%
    cut = int(len(X) * 0.8)
    X_tr, y_tr = mirror(X[:cut], y[:cut])
    X_te, y_te = mirror(X[cut:], y[cut:])

    models = {
        "Logistic Regression": LogisticRegression(max_iter=1000),
        "Gradient Boosting": GradientBoostingClassifier(n_estimators=150, max_depth=2,
                                                        learning_rate=0.05, random_state=42),
    }
    best_name, best_auc, results = None, -1, {}
    for name, model in models.items():
        model.fit(X_tr, y_tr)
        prob = model.predict_proba(X_te)[:, 1]
        acc, auc = accuracy_score(y_te, prob > 0.5), roc_auc_score(y_te, prob)
        results[name] = {"accuracy": round(acc, 3), "roc_auc": round(auc, 3)}
        if verbose:
            print(f"{name:20s} accuracy={acc:.3f}  ROC-AUC={auc:.3f}")
        if auc > best_auc:
            best_name, best_auc = name, auc

    best = models[best_name].fit(*mirror(X, y))  # refit on all data (mirrored)
    bundle = {"model": best, "name": best_name, "features": FEATURES,
              "metrics": results, "n_matches": len(X)}
    MODEL_PATH.parent.mkdir(exist_ok=True)
    joblib.dump(bundle, MODEL_PATH)
    if verbose:
        print(f"\nSaved best model: {best_name} (trained on {len(X)} matches)")
    return bundle


def main():
    train()


if __name__ == "__main__":
    main()
