import base64
import concurrent.futures
import json
import os
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

import requests


class HighlightSequenceAnalyzer:
    def __init__(self, images_dir: str, debug: bool = True, max_workers: int = 4):
        self.api_url = "http://localhost:11434"
        self.model = "llava"
        self.images_dir = Path(images_dir)
        self.debug = debug
        self.max_workers = max_workers
        self.print_lock = threading.Lock()

    def safe_print(self, message: str):
        """Thread-safe printing."""
        with self.print_lock:
            print(message)

    def encode_image(self, image_path: str) -> str:
        """Encode image with minimal logging."""
        try:
            with open(image_path, "rb") as image_file:
                image_data = image_file.read()
                if len(image_data) == 0:
                    raise ValueError(f"Empty image file: {image_path}")
                return base64.b64encode(image_data).decode("utf-8")
        except Exception as e:
            raise ValueError(f"Failed to encode image {image_path}: {str(e)}")

    def parse_response(self, raw_response: str) -> Tuple[float, str, str]:
        """Parse three-part response with sequence description."""
        sequence = ""
        probability = 0.0
        explanation = ""

        # Split response into lines and clean
        lines = [line.strip() for line in raw_response.split("\n") if line.strip()]

        if not lines:
            return 0.0, "No response received", "No explanation provided"

        # Parse the three parts
        for line in lines:
            if line.startswith("SEQUENCE:"):
                sequence = line.split(":", 1)[1].strip()
            elif line.startswith("HIGHLIGHT_SCORE:"):
                try:
                    probability = float(line.split(":", 1)[1].strip())
                    probability = max(0.0, min(1.0, probability))
                except (ValueError, IndexError):
                    probability = 0.0
            elif line.startswith("EXPLANATION:"):
                explanation = line.split(":", 1)[1].strip()

        return probability, sequence, explanation

    def analyze_sequence(self, data: tuple[str, List[str]]) -> Dict:
        """Analyze a single sequence of images."""
        timestamp, image_files = data
        try:
            # Sort image files by frame number
            image_files = sorted(
                image_files, key=lambda x: int(x.split("_")[1].split("s")[0])
            )

            # Extract highlight number
            highlight_num = int(image_files[0].split("_")[1])

            if self.debug:
                self.safe_print(
                    f"\nAnalyzing highlight #{highlight_num} at {timestamp} ({len(image_files)} frames)"
                )

            # Encode images
            encoded_images = []
            for image_file in image_files:
                full_path = self.images_dir / image_file
                if not full_path.exists():
                    raise FileNotFoundError(f"Image not found: {full_path}")
                encoded = self.encode_image(str(full_path))
                encoded_images.append(encoded)

            sequence_prompt = f"""You are an expert NBA video analyst with 20+ years experience creating highlight reels. You know most plays are routine - only truly special sequences make the cut.

You're analyzing {len(image_files)} sequential frames. Be precise and only describe what you actually see across ALL the frames..

Example analyses:

"Steal at half court, drives full length, finishes with dunk"
SEQUENCE: Defender gets steal, takes ball coast-to-coast for powerful dunk over help defender.
HIGHLIGHT_SCORE: 0.9
EXPLANATION: Complete exceptional sequence with clear defensive play and strong finish.

"Player crosses over defender, pulls up for jumper"
SEQUENCE: Guard performs crossover, creates space, shoots jumper but outcome not visible.
HIGHLIGHT_SCORE: 0.4
EXPLANATION: Good individual move but cannot confirm result.

"Standard half-court possession"
SEQUENCE: Team passes ball around perimeter in regular offensive set.
HIGHLIGHT_SCORE: 0.1
EXPLANATION: Routine basketball action without exceptional elements.

For this sequence:
1. Describe exactly what you see happen
2. Score based on what's visible, not assumptions
3. Justify score in one sentence

Scoring guide:
0.9-1.0: Exceptional complete play (e.g. steal→score, poster dunk, etc.)
0.6-0.8: Very good clear play (e.g. impressive score, impressive defensive play, etc.)
0.3-0.5: Good play but incomplete (e.g. good score but not visible)
0.0-0.2: Regular action (most plays)

Respond EXACTLY like examples above:
SEQUENCE: <one clear sentence describing what happens>
HIGHLIGHT_SCORE: <0.0-1.0>
EXPLANATION: <one sentence justification>"""

            payload = {
                "model": self.model,
                "prompt": sequence_prompt,
                "images": encoded_images,
                "stream": False,
                "temperature": 0.1,
            }

            # Make API request with retries
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    response = requests.post(
                        f"{self.api_url}/api/generate", json=payload, timeout=180
                    )
                    response.raise_for_status()
                    break
                except requests.RequestException as e:
                    if attempt == max_retries - 1:
                        raise
                    time.sleep(2**attempt)

            response_json = response.json()
            raw_response = response_json.get("response", "")

            # Parse response with sequence description
            probability, sequence, explanation = self.parse_response(raw_response)

            if self.debug:
                self.safe_print(f"Highlight #{highlight_num}:")
                self.safe_print(f"Sequence: {sequence}")
                self.safe_print(f"Score: {probability:.2f}")
                self.safe_print(f"Reason: {explanation}\n")

            return {
                "timestamp": timestamp,
                "highlight_num": highlight_num,
                "sequence": sequence,
                "highlight_probability": probability,
                "explanation": explanation,
                "raw_response": raw_response,
                "num_frames": len(image_files),
                "status": "success",
            }

        except Exception as e:
            if self.debug:
                self.safe_print(f"Error processing sequence {timestamp}: {str(e)}")
            return {
                "timestamp": timestamp,
                "highlight_num": highlight_num if "highlight_num" in locals() else 0,
                "sequence": "",
                "highlight_probability": 0.0,
                "explanation": str(e),
                "raw_response": "",
                "num_frames": len(image_files) if "image_files" in locals() else 0,
                "status": "error",
                "error": str(e),
            }

    def process_dataset(self, input_json: str, output_json: str):
        """Process entire dataset of sequences in parallel."""
        try:
            with open(input_json, "r") as f:
                sequences = json.load(f)

            sequence_list = list(sequences.items())
            results = []
            start_time = time.time()

            with concurrent.futures.ThreadPoolExecutor(
                max_workers=self.max_workers
            ) as executor:
                future_to_sequence = {
                    executor.submit(self.analyze_sequence, seq): seq[0]
                    for seq in sequence_list
                }

                for future in concurrent.futures.as_completed(future_to_sequence):
                    timestamp = future_to_sequence[future]
                    try:
                        result = future.result()
                        results.append(result)
                    except Exception as e:
                        self.safe_print(
                            f"Error processing sequence {timestamp}: {str(e)}"
                        )
                        results.append(
                            {
                                "timestamp": timestamp,
                                "highlight_num": 0,
                                "sequence": "",
                                "highlight_probability": 0.0,
                                "explanation": str(e),
                                "raw_response": "",
                                "num_frames": 0,
                                "status": "error",
                                "error": str(e),
                            }
                        )

            processing_time = time.time() - start_time

            # Sort results by highlight number
            results.sort(key=lambda x: x.get("highlight_num", float("inf")))

            # Post-process results
            highlight_summary = {}
            for result in results:
                if result["status"] == "success":
                    highlight_summary[result["highlight_num"]] = {
                        "score": result["highlight_probability"],
                        "sequence": result["sequence"],
                        "frames": result["num_frames"],
                    }

            output = {
                "metadata": {
                    "total_sequences": len(results),
                    "successful_analyses": sum(
                        1 for r in results if r["status"] == "success"
                    ),
                    "processing_time_seconds": processing_time,
                    "average_probability": sum(
                        r["highlight_probability"] for r in results
                    )
                    / len(results),
                    "high_probability_sequences": sum(
                        1 for r in results if r["highlight_probability"] > 0.7
                    ),
                    "timestamp": datetime.now().isoformat(),
                },
                "highlight_summary": highlight_summary,
                "sequences": results,
            }

            # Save results
            output_path = Path(output_json)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_json, "w") as f:
                json.dump(output, f, indent=2)

            if self.debug:
                self.safe_print(f"\nAnalysis Complete ({processing_time:.1f}s):")
                self.safe_print("\nHighlight Summary:")
                for num, details in highlight_summary.items():
                    self.safe_print(
                        f"#{num:2d} ({details['frames']:2d} frames) - {details['score']:.2f}: {details['sequence']}"
                    )

            return output

        except Exception as e:
            self.safe_print(f"Fatal error in process_dataset: {str(e)}")
            raise


def main():
    images_dir = "app/data/images"
    input_json = "app/data/json/image_metadata.json"
    output_json = "app/data/json/highlight_analysis.json"
    max_workers = 2

    analyzer = HighlightSequenceAnalyzer(
        images_dir=images_dir, debug=True, max_workers=max_workers
    )

    try:
        results = analyzer.process_dataset(input_json, output_json)
    except Exception as e:
        print(f"Fatal error: {str(e)}")
        exit(1)


if __name__ == "__main__":
    main()
