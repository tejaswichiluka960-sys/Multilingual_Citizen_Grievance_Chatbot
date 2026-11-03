"""Lazy Hugging Face embedding classifier used by the application."""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class ModelPrediction:
    """Prediction returned by the saved department and priority models."""

    department: str
    department_confidence: float
    priority: str
    priority_confidence: float
    model_name: str


class HuggingFaceClassifier:
    """Load a saved classifier and its embedding model only when first used."""

    def __init__(self, model_path: str | Path, embedding_model: str | None = None) -> None:
        self.model_path = Path(model_path)
        self.embedding_model_override = embedding_model
        self._bundle: dict[str, Any] | None = None
        self._embedder: Any = None

    def _load(self) -> None:
        """Load the joblib bundle and Hugging Face sentence encoder."""

        if self._bundle is not None and self._embedder is not None:
            return
        if not self.model_path.exists():
            raise FileNotFoundError(f"Classifier model not found: {self.model_path}")

        import joblib

        # Complaint intake must remain available when deployment has no
        # internet access. The model is still used when its files are cached;
        # otherwise classification falls back immediately to keyword rules.
        os.environ.setdefault("HF_HUB_OFFLINE", "1")
        os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
        from sentence_transformers import SentenceTransformer

        bundle = joblib.load(self.model_path)
        embedding_model = self.embedding_model_override or bundle["embedding_model"]
        self._bundle = bundle
        # Do not block complaint intake while trying to reach Hugging Face.
        # When the model is cached locally it is used; otherwise the caller
        # falls back to the deterministic multilingual keyword classifier.
        local_model = Path(embedding_model)
        if not local_model.exists() and "/" in embedding_model:
            cache_root = Path.home() / ".cache" / "huggingface" / "hub"
            repo_cache = cache_root / f"models--{embedding_model.replace('/', '--')}" / "snapshots"
            snapshots = sorted(repo_cache.glob("*")) if repo_cache.exists() else []
            if snapshots:
                local_model = snapshots[-1]
        if not local_model.exists():
            raise FileNotFoundError(f"Embedding model is not cached locally: {embedding_model}")
        self._embedder = SentenceTransformer(str(local_model), local_files_only=True)

    def predict(self, text: str) -> ModelPrediction:
        """Return department and priority predictions for one complaint."""

        self._load()
        assert self._bundle is not None
        encoded = self._embedder.encode(
            [f"query: {text}"],
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        department_model = self._bundle["department_model"]
        priority_model = self._bundle["priority_model"]
        department_probabilities = department_model.predict_proba(encoded)[0]
        priority_probabilities = priority_model.predict_proba(encoded)[0]
        department_index = int(department_probabilities.argmax())
        priority_index = int(priority_probabilities.argmax())
        return ModelPrediction(
            department=str(department_model.classes_[department_index]),
            department_confidence=float(department_probabilities[department_index]),
            priority=str(priority_model.classes_[priority_index]),
            priority_confidence=float(priority_probabilities[priority_index]),
            model_name=str(self._bundle.get("model_name", "huggingface-e5-logreg")),
        )
