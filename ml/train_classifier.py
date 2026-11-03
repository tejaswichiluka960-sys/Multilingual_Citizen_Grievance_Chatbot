"""Train and evaluate Hugging Face embedding classifiers."""

import argparse
import csv
from collections import defaultdict
from pathlib import Path
from typing import Any


def read_rows(path: Path) -> list[dict[str, str]]:
    """Read labeled complaint rows from a UTF-8 CSV file."""

    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def encode_rows(embedder: Any, rows: list[dict[str, str]]) -> Any:
    """Encode complaint text using the E5 query prefix."""

    texts = [f"query: {row['text']}" for row in rows]
    return embedder.encode(texts, normalize_embeddings=True, show_progress_bar=True)


def train_models(
    rows: list[dict[str, str]],
    embedding_model: str,
    output_dir: Path,
) -> dict[str, Any]:
    """Train department and priority Logistic Regression models."""

    try:
        import joblib
        from sentence_transformers import SentenceTransformer
        from sklearn.linear_model import LogisticRegression
    except ImportError as exc:
        raise RuntimeError(
            "Task 12 training requires sentence-transformers, scikit-learn and joblib. "
            "Install requirements.txt first."
        ) from exc

    embedder = SentenceTransformer(embedding_model)
    features = encode_rows(embedder, rows)
    department_model = LogisticRegression(max_iter=1000, class_weight="balanced")
    priority_model = LogisticRegression(max_iter=1000, class_weight="balanced")
    department_model.fit(features, [row["department"] for row in rows])
    priority_model.fit(features, [row["priority"] for row in rows])

    output_dir.mkdir(parents=True, exist_ok=True)
    bundle = {
        "model_name": "huggingface-e5-logreg",
        "embedding_model": embedding_model,
        "department_model": department_model,
        "priority_model": priority_model,
    }
    model_path = output_dir / "classifier.joblib"
    joblib.dump(bundle, model_path)
    return {"bundle": bundle, "model_path": model_path, "embedder": embedder}


def evaluate_models(
    trained: dict[str, Any],
    rows: list[dict[str, str]],
) -> dict[str, Any]:
    """Evaluate both classifiers and return aggregate and per-language metrics."""

    from sklearn.metrics import accuracy_score, f1_score

    features = encode_rows(trained["embedder"], rows)
    department_model = trained["bundle"]["department_model"]
    priority_model = trained["bundle"]["priority_model"]
    department_predictions = department_model.predict(features)
    priority_predictions = priority_model.predict(features)
    department_actual = [row["department"] for row in rows]
    priority_actual = [row["priority"] for row in rows]
    per_language: dict[str, dict[str, float]] = {}
    grouped: dict[str, list[int]] = defaultdict(list)
    for index, row in enumerate(rows):
        grouped[row["lang"]].append(index)
    for language, indexes in sorted(grouped.items()):
        per_language[language] = {
            "department_macro_f1": f1_score(
                [department_actual[index] for index in indexes],
                [department_predictions[index] for index in indexes],
                average="macro",
                zero_division=0,
            ),
            "priority_accuracy": accuracy_score(
                [priority_actual[index] for index in indexes],
                [priority_predictions[index] for index in indexes],
            ),
        }
    return {
        "department_macro_f1": f1_score(
            department_actual,
            department_predictions,
            average="macro",
            zero_division=0,
        ),
        "department_accuracy": accuracy_score(department_actual, department_predictions),
        "priority_macro_f1": f1_score(
            priority_actual,
            priority_predictions,
            average="macro",
            zero_division=0,
        ),
        "priority_accuracy": accuracy_score(priority_actual, priority_predictions),
        "per_language": per_language,
    }


def main() -> None:
    """Train the classifier bundle from the generated training data."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--train", type=Path, default=Path("ml/data/train.csv"))
    parser.add_argument("--test", type=Path, default=Path("ml/data/test.csv"))
    parser.add_argument("--handwritten-test", type=Path, default=Path("ml/data/handwritten_test.csv"))
    parser.add_argument("--model-dir", type=Path, default=Path("ml/models"))
    parser.add_argument("--embedding-model", default="intfloat/multilingual-e5-small")
    args = parser.parse_args()

    training_rows = read_rows(args.train)
    test_rows = read_rows(args.test)
    trained = train_models(training_rows, args.embedding_model, args.model_dir)
    metrics = evaluate_models(trained, test_rows)
    print(f"Saved model bundle: {trained['model_path']}")
    print(f"Department macro-F1: {metrics['department_macro_f1']:.3f}")
    print(f"Department accuracy: {metrics['department_accuracy']:.3f}")
    print(f"Priority macro-F1: {metrics['priority_macro_f1']:.3f}")
    print(f"Priority accuracy: {metrics['priority_accuracy']:.3f}")
    print("Per-language metrics:")
    for language, language_metrics in metrics["per_language"].items():
        print(f"  {language}: {language_metrics}")

    if args.handwritten_test.exists():
        handwritten_metrics = evaluate_models(trained, read_rows(args.handwritten_test))
        print(f"Handwritten department macro-F1: {handwritten_metrics['department_macro_f1']:.3f}")


if __name__ == "__main__":
    main()
