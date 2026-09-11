"""CLI entry point for the Section D pipeline."""

import argparse
import json
import sys
from pathlib import Path

from src.contracts.nlp_input import NLPOutputContract
from src.pipeline.orchestrator import SectionDPipeline


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Section D Real-Time Topic Clustering & Trend Scoring Pipeline"
    )
    parser.add_argument(
        "input",
        help="Path to JSON file with NLP Output Contract payloads (list or single object)",
    )
    parser.add_argument(
        "-o", "--output",
        help="Output path for Section D JSON (writes all topics)",
        default="output/section_d.json",
    )
    parser.add_argument(
        "--flush-buffer",
        action="store_true",
        help="Run HDBSCAN on unclustered buffer after ingestion",
    )
    parser.add_argument(
        "--embeddings",
        help="Path to embeddings JSON (embedding_ref -> vector)",
    )
    parser.add_argument(
        "--network",
        help="Path to Component E author interaction network JSON",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    raw = json.loads(input_path.read_text(encoding="utf-8"))
    if isinstance(raw, dict):
        payloads = [NLPOutputContract.model_validate(raw)]
    else:
        payloads = [NLPOutputContract.model_validate(p) for p in raw]

    pipeline = SectionDPipeline()
    if args.embeddings:
        pipeline.embedding_store.load_from_json(args.embeddings)
    if args.network:
        pipeline.network.load_from_file(args.network)

    pipeline.connect_external_stores()
    pipeline.ingest_batch(payloads)

    if args.flush_buffer:
        pipeline.flush_buffer()

    results = pipeline.build_all_section_d()
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    output_data = [r.to_json_dict() for r in results]
    if len(output_data) == 1:
        output_path.write_text(
            json.dumps(output_data[0], indent=2, default=str), encoding="utf-8"
        )
    else:
        output_path.write_text(
            json.dumps(output_data, indent=2, default=str), encoding="utf-8"
        )

    print(f"Generated {len(results)} Section D payload(s) -> {output_path}")
    pipeline.close()


if __name__ == "__main__":
    main()
