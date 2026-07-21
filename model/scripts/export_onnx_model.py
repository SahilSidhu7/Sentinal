"""One-time export of sentence-transformers/all-MiniLM-L6-v2 to ONNX + tokenizer.json.

Run this once per machine before using embedder.py. Needs network access and
`optimum[onnxruntime]` (dev-only dependency, not required at pipeline runtime).

Usage: python scripts/export_onnx_model.py [output_dir]
"""
import sys
from pathlib import Path

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"


def main() -> None:
    out_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent.parent / "artifacts" / "all-MiniLM-L6-v2"
    out_dir.mkdir(parents=True, exist_ok=True)

    from optimum.onnxruntime import ORTModelForFeatureExtraction
    from transformers import AutoTokenizer

    print(f"exporting {MODEL_NAME} -> {out_dir}")
    model = ORTModelForFeatureExtraction.from_pretrained(MODEL_NAME, export=True)
    model.save_pretrained(out_dir)

    exported = out_dir / "model.onnx"
    if not exported.exists():
        candidates = list(out_dir.glob("*.onnx"))
        if candidates:
            candidates[0].rename(exported)

    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    tokenizer.save_pretrained(out_dir)
    tokenizer_json = out_dir / "tokenizer.json"
    if not tokenizer_json.exists():
        tokenizer.backend_tokenizer.save(str(tokenizer_json))

    print(f"done. artifacts in {out_dir}")


if __name__ == "__main__":
    main()
