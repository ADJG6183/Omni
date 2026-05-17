"""
evaluate.py

Re-evaluates a trained model on the time-based hold-out test set and produces
a full diagnostic report: metrics table, confusion matrix, ROC curve, PR curve,
calibration curve, and SHAP global feature importance (XGBoost).

Why a separate evaluate script?
--------------------------------
train.py reports quick metrics at the end of training, but you may want to
re-evaluate a model after collecting more data, or compare two model versions
without retraining. This script reproduces the exact same test split as
train.py and runs a richer evaluation.

Calibration curve: checks whether the model's probabilities are meaningful.
If the model says "70% chance of a drop," roughly 70% of those observations
should actually drop. Uncalibrated models produce overconfident or underconfident
probabilities, which breaks the recommendation thresholds that depend on them.

SHAP global importance (XGBoost): shows which features the model relies on
most across all test examples — not just one prediction, but the average
absolute contribution of each feature. This is more reliable than standard
feature importance, which can be biased by feature scale and cardinality.

Usage:
    cd /path/to/PriceDropOS
    python ml/src/evaluate.py                   # evaluates LR, RF, and XGBoost
    python ml/src/evaluate.py --model rf        # random_forest only
    python ml/src/evaluate.py --model xgb       # xgboost only
    python ml/src/evaluate.py --no-plots        # skip matplotlib output
"""
import argparse
import json
import logging
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.calibration import calibration_curve
from sklearn.metrics import (
    ConfusionMatrixDisplay,
    PrecisionRecallDisplay,
    RocCurveDisplay,
    accuracy_score,
    average_precision_score,
    classification_report,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.train import FEATURE_COLS, NAN_FILL, TRAIN_SPLIT, VERSION, load_and_merge, prepare_xy

logger = logging.getLogger(__name__)

MODEL_NAMES = {
    "lr":  "logistic_regression",
    "rf":  "random_forest",
    "xgb": "xgboost",
}


def time_split_test_only(df: pd.DataFrame) -> pd.DataFrame:
    """Return the test portion only, using the same split as train.py."""
    df_sorted = df.sort_values("observed_at").reset_index(drop=True)
    cutoff_idx = int(len(df_sorted) * TRAIN_SPLIT)
    df_test = df_sorted.iloc[cutoff_idx:].copy()
    logger.info("Test set: %d rows | positive rate %.1f%%", len(df_test), df_test["label_drop_7d"].mean() * 100)
    return df_test


def evaluate_model(model, X_test: np.ndarray, y_test: np.ndarray, model_name: str, show_plots: bool) -> dict:
    y_pred  = model.predict(X_test)
    y_proba = model.predict_proba(X_test)[:, 1]

    print(f"\n{'='*60}")
    print(f"  {model_name}")
    print(f"{'='*60}")
    print(f"\nTest set: {len(y_test)} examples | {y_test.sum()} positive ({y_test.mean():.1%})\n")
    print(classification_report(y_test, y_pred, target_names=["No drop (0)", "Drop ≥5% (1)"], zero_division=0))

    roc = roc_auc_score(y_test, y_proba) if len(set(y_test)) > 1 else 0.0
    pr  = average_precision_score(y_test, y_proba) if len(set(y_test)) > 1 else 0.0

    print(f"  ROC-AUC : {roc:.4f}")
    print(f"  PR-AUC  : {pr:.4f}")

    if show_plots:
        try:
            import matplotlib.pyplot as plt

            fig, axes = plt.subplots(1, 3, figsize=(16, 5))
            fig.suptitle(model_name, fontsize=13)

            # Confusion matrix
            ConfusionMatrixDisplay.from_predictions(
                y_test, y_pred,
                display_labels=["No drop", "Drop ≥5%"],
                ax=axes[0],
            )
            axes[0].set_title("Confusion matrix")

            # ROC curve
            if len(set(y_test)) > 1:
                RocCurveDisplay.from_predictions(y_test, y_proba, ax=axes[1])
                axes[1].set_title(f"ROC curve (AUC={roc:.3f})")

            # Calibration curve
            if len(set(y_test)) > 1:
                fraction_pos, mean_pred = calibration_curve(y_test, y_proba, n_bins=5)
                axes[2].plot(mean_pred, fraction_pos, "s-", label=model_name)
                axes[2].plot([0, 1], [0, 1], "k--", label="Perfect calibration")
                axes[2].set_xlabel("Mean predicted probability")
                axes[2].set_ylabel("Fraction of positives")
                axes[2].set_title("Calibration curve")
                axes[2].legend()

            plt.tight_layout()
            plt.show()

        except ImportError:
            logger.warning("matplotlib not available — skipping plots")

    return {
        "accuracy":  round(accuracy_score(y_test, y_pred),   4),
        "precision": round(precision_score(y_test, y_pred,   zero_division=0), 4),
        "recall":    round(recall_score(y_test, y_pred,      zero_division=0), 4),
        "f1":        round(f1_score(y_test, y_pred,          zero_division=0), 4),
        "roc_auc":   round(roc,  4),
        "pr_auc":    round(pr,   4),
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def _print_shap_importance(X_test: pd.DataFrame, base_model_path: Path) -> None:
    """
    Print global SHAP feature importance for XGBoost.

    Global importance = mean(|SHAP value|) across all test examples.
    This tells you which features matter most on average, not just for one prediction.
    Unlike XGBoost's built-in importance (based on how often a feature is split),
    SHAP-based importance accounts for the actual magnitude of each feature's contribution.
    """
    if not base_model_path.exists():
        logger.warning("XGBoost base model not found at %s — skipping SHAP analysis", base_model_path)
        return

    try:
        import shap
        base_model = joblib.load(base_model_path)
        explainer  = shap.TreeExplainer(base_model, feature_perturbation="tree_path_dependent")
        shap_vals  = explainer.shap_values(X_test)

        mean_abs_shap = pd.Series(
            np.abs(shap_vals).mean(axis=0),
            index=X_test.columns,
        ).sort_values(ascending=False)

        print("\nXGBoost global SHAP importance (mean |SHAP| across test set):")
        for feat, val in mean_abs_shap.head(10).items():
            bar = "█" * int(val * 300)
            print(f"  {feat:<35} {val:.4f}  {bar}")
    except Exception:
        logger.exception("SHAP global importance failed")


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    parser = argparse.ArgumentParser(description="Evaluate trained price-drop models")
    parser.add_argument("--model", choices=["lr", "rf", "xgb", "all"], default="all")
    parser.add_argument("--features",  default="ml/data/features.csv")
    parser.add_argument("--labels",    default="ml/data/labels.csv")
    parser.add_argument("--artifacts", default="ml/artifacts")
    parser.add_argument("--no-plots",  action="store_true", help="Suppress matplotlib output")
    args = parser.parse_args()

    artifacts_dir = Path(args.artifacts)
    features_path = Path(args.features)
    labels_path   = Path(args.labels)

    if not features_path.exists() or not labels_path.exists():
        logger.error("Run build_features.py and create_labels.py first.")
        sys.exit(1)

    df       = load_and_merge(features_path, labels_path)
    df_test  = time_split_test_only(df)
    X_test, y_test = prepare_xy(df_test)

    keys = list(MODEL_NAMES.keys()) if args.model == "all" else [args.model]
    results: dict[str, dict] = {}

    for key in keys:
        name = MODEL_NAMES[key]
        path = artifacts_dir / f"price_drop_{name}_{VERSION}.pkl"

        if not path.exists():
            logger.warning("Model artifact not found: %s — skipping", path)
            continue

        model = joblib.load(path)
        metrics = evaluate_model(model, X_test, y_test, name, show_plots=not args.no_plots)
        results[name] = metrics

    if not results:
        print("\nNo model artifacts found. Run: python ml/src/train.py")
        sys.exit(1)

    print(f"\n{'='*60}")
    print("  Summary comparison")
    print(f"{'='*60}")
    print(f"{'Model':<25} {'Acc':>6} {'Prec':>6} {'Rec':>6} {'F1':>6} {'ROC-AUC':>8} {'PR-AUC':>7}")
    print("-" * 65)
    for name, m in results.items():
        print(
            f"{name:<25} {m['accuracy']:>6.3f} {m['precision']:>6.3f} {m['recall']:>6.3f} "
            f"{m['f1']:>6.3f} {m['roc_auc']:>8.3f} {m['pr_auc']:>7.3f}"
        )

    # Feature importance: RF (built-in), XGBoost (SHAP-based)
    rf_path = artifacts_dir / f"price_drop_random_forest_{VERSION}.pkl"
    if rf_path.exists() and args.model in ("rf", "all"):
        rf = joblib.load(rf_path)
        if hasattr(rf, "feature_importances_"):
            importances = pd.Series(rf.feature_importances_, index=FEATURE_COLS).sort_values(ascending=False)
            print("\nRandom Forest feature importance (top 10):")
            for feat, imp in importances.head(10).items():
                bar = "█" * int(imp * 200)
                print(f"  {feat:<35} {imp:.4f}  {bar}")

    if args.model in ("xgb", "all"):
        _print_shap_importance(X_test, artifacts_dir / f"price_drop_xgboost_base_{VERSION}.pkl")


if __name__ == "__main__":
    main()
