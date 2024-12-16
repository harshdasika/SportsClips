import base64
import json
import sys
import time
from pathlib import Path
from typing import Dict, List, Tuple

import requests

OLLAMA_API_URL: str = "http://localhost:11434"


class HighlightInspector:
    def __init__(self, debug=True):
        self.api_url = OLLAMA_API_URL
        self.model = "llava"
        self.debug = debug

    def get_prompt(self) -> str:
        """Returns prompt requesting only probability distribution."""
        return """You are an expert sports video analyst with decades of experience creating highlight reels for major sports networks.
        You understand that being too lenient with what constitutes a highlight diminishes the impact of truly special moments.

        Categories to consider:

        'short_clip':
        - Successful scoring plays (dunks, difficult shots going in)
        - Game-changing defensive plays (blocks, crucial steals)
        - Clear athletic feats in progress (player in air for dunk, acrobatic moves)
        - Visible emotional reactions after big plays
        - Crucial game moments (game-winners in progress, clutch shots)

        'long_clip':
        - Complex plays developing with clear purpose
        - Fast breaks in progress
        - Clear defensive sequences leading to turnovers
        - Visible tactical plays unfolding
        - Clear lead-up to scoring opportunities

        'unimportant':
        - Basic game setups
        - Players just standing around
        - Regular dribbling or passing
        - No clear action visible
        - Ball not visible in frame
        - Standard court positioning

        Examine this frame and assign probabilities for each category based on what you actually see in the frame.
        Consider ONLY what is visible, not what might happen next.
        
        Respond ONLY with probabilities in exactly this format:
        PROBABILITIES:
        short_clip: <probability>
        long_clip: <probability>
        unimportant: <probability>"""

    def debug_print(self, message: str):
        """Print debug messages if debug mode is on."""
        if self.debug:
            print(f"DEBUG: {message}")

    def encode_image(self, image_path: str) -> str:
        """Convert image to base64 string with error handling."""
        try:
            path = Path(image_path)
            if not path.exists():
                raise FileNotFoundError(f"Image file not found: {image_path}")

            self.debug_print(f"Reading image from: {image_path}")
            with open(image_path, "rb") as image_file:
                return base64.b64encode(image_file.read()).decode("utf-8")
        except Exception as e:
            self.debug_print(f"Error encoding image {image_path}: {str(e)}")
            raise

    def parse_model_response(
        self, text_response: str
    ) -> Tuple[str, Dict[str, float], Dict]:
        """Parse model response with strict probability handling."""
        probabilities = {"short_clip": 0.0, "long_clip": 0.0, "unimportant": 0.0}

        # Extract probabilities with strict parsing
        try:
            lines = [line.strip() for line in text_response.lower().split("\n")]
            for line in lines:
                if ":" not in line:
                    continue
                category, value = line.split(":", 1)
                category = category.strip()
                if category in probabilities:
                    # Extract first number and convert to float
                    try:
                        prob = float(value.split()[0].strip())
                        probabilities[category] = prob
                    except (ValueError, IndexError):
                        self.debug_print(f"Failed to parse probability for {category}")

            # Validate and normalize probabilities
            total = sum(probabilities.values())
            if abs(total - 1.0) > 0.1:  # Allow small deviation from 1.0
                self.debug_print(f"Probabilities sum to {total}, normalizing")
                if total > 0:
                    probabilities = {k: v / total for k, v in probabilities.items()}
                else:
                    probabilities = {
                        "short_clip": 0.0,
                        "long_clip": 0.0,
                        "unimportant": 1.0,
                    }

            # Classification thresholds
            # Must have both high absolute probability AND significant margin over others
            max_prob = max(probabilities.values())
            max_category = max(probabilities.items(), key=lambda x: x[1])[0]
            second_highest = sorted(probabilities.values())[-2]
            margin = max_prob - second_highest

            # Strict classification rules
            if max_category == "short_clip":
                if max_prob >= 0.6 and margin >= 0.2:
                    prediction = "short_clip"
                else:
                    prediction = "unimportant"
            elif max_category == "long_clip":
                if max_prob >= 0.5 and margin >= 0.15:
                    prediction = "long_clip"
                else:
                    prediction = "unimportant"
            else:
                prediction = "unimportant"

            analysis_details = {
                "action_detected": max_prob > 0.3,
                "key_moment": probabilities["short_clip"] > 0.4,
                "confidence": max_prob,
                "margin": margin,
                "normalized": abs(total - 1.0) > 0.1,
            }

            return prediction, probabilities, analysis_details

        except Exception as e:
            self.debug_print(f"Error parsing probabilities: {str(e)}")
            return (
                "unimportant",
                {"short_clip": 0.0, "long_clip": 0.0, "unimportant": 1.0},
                {
                    "action_detected": False,
                    "key_moment": False,
                    "confidence": 0.0,
                    "margin": 0.0,
                    "normalized": False,
                    "error": str(e),
                },
            )

    def analyze_frame(self, image_path: str, max_retries: int = 3) -> Dict:
        """Analyze a single frame with retries and enhanced error handling."""
        for attempt in range(max_retries):
            try:
                self.debug_print(
                    f"\nStarting analysis of frame: {image_path} (attempt {attempt + 1}/{max_retries})"
                )

                encoded_image = self.encode_image(image_path)
                self.debug_print("Successfully encoded image")

                payload = {
                    "model": self.model,
                    "prompt": self.get_prompt(),
                    "images": [encoded_image],
                    "stream": False,
                    "temperature": 0.1,
                }
                self.debug_print("Prepared API payload")

                self.debug_print(
                    f"Sending request to Ollama API (attempt {attempt + 1})..."
                )
                response = requests.post(
                    f"{self.api_url}/api/generate", json=payload, timeout=90
                )
                response.raise_for_status()

                try:
                    response_json = response.json()
                    self.debug_print(f"Response JSON: {str(response_json)[:200]}...")

                    text_response = response_json.get("response", "")
                    if not text_response.strip():
                        raise ValueError("Empty response received")

                except json.JSONDecodeError as e:
                    self.debug_print(f"Failed to decode JSON: {str(e)}")
                    raise ValueError(f"Invalid JSON response: {str(e)}")

                self.debug_print(f"Raw response: {text_response[:100]}...")

                prediction, probabilities, analysis_details = self.parse_model_response(
                    text_response
                )

                return {
                    "highlight_type": prediction,
                    "probabilities": probabilities,
                    "analysis_details": analysis_details,
                    "raw_response": text_response,
                    "status": "success",
                }

            except (requests.exceptions.RequestException, ValueError) as e:
                self.debug_print(f"Attempt {attempt + 1} failed: {str(e)}")
                if attempt < max_retries - 1:
                    wait_time = (2**attempt) * 2
                    self.debug_print(f"Waiting {wait_time} seconds before retry...")
                    time.sleep(wait_time)
                else:
                    return self.error_response(
                        "max_retries_exceeded",
                        f"Failed after {max_retries} attempts: {str(e)}",
                    )

            except Exception as e:
                self.debug_print(f"Unexpected error: {str(e)}")
                return self.error_response("error", str(e))

    def error_response(self, error_type: str, message: str) -> Dict:
        """Create a standardized error response."""
        error_response = {
            "highlight_type": "error",
            "probabilities": {"short_clip": 0.0, "long_clip": 0.0, "unimportant": 0.0},
            "analysis_details": {},
            "raw_response": "",
            "status": error_type,
            "error_message": message,
        }
        self.debug_print(f"Generated error response: {error_type} - {message}")
        return error_response

    def analyze_sequence(self, input_json: str, output_json: str):
        """Process a sequence of frames with enhanced error handling."""
        try:
            if not Path(input_json).exists():
                raise FileNotFoundError(f"Input JSON not found: {input_json}")

            with open(input_json, "r") as f:
                data = json.load(f)

            self.debug_print(f"Loaded {len(data)} frames from {input_json}")

            results = []
            errors = []

            for i, entry in enumerate(data, 1):
                timestamp = entry["timestamp"]
                image_path = entry["image_path"]

                print(f"\nAnalyzing frame {i}/{len(data)} at {timestamp}...")

                if i > 1:
                    time.sleep(2)  # 2 second delay between frames

                analysis = self.analyze_frame(image_path)

                if analysis["status"] == "success":
                    print(f"Success - Type: {analysis['highlight_type']}")
                    print(
                        "Probabilities:",
                        ", ".join(
                            f"{k}: {v:.2%}"
                            for k, v in analysis["probabilities"].items()
                        ),
                    )
                else:
                    error_msg = (
                        f"Error analyzing frame {i}: {analysis['error_message']}"
                    )
                    print(error_msg)
                    errors.append(error_msg)

                results.append(
                    {"timestamp": timestamp, "image_path": image_path, **analysis}
                )

            output = {
                "metadata": {
                    "total_frames": len(results),
                    "successful_analyses": sum(
                        1 for r in results if r["status"] == "success"
                    ),
                    "errors": len(errors),
                    "error_messages": errors,
                    "highlight_stats": {
                        "short_clips": sum(
                            1 for r in results if r["highlight_type"] == "short_clip"
                        ),
                        "long_clips": sum(
                            1 for r in results if r["highlight_type"] == "long_clip"
                        ),
                        "unimportant": sum(
                            1 for r in results if r["highlight_type"] == "unimportant"
                        ),
                    },
                },
                "frames": results,
            }

            self.debug_print(f"Analysis complete. Writing results to {output_json}")
            output_path = Path(output_json)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            with open(output_json, "w") as f:
                json.dump(output, f, indent=2)

            return results, errors

        except Exception as e:
            self.debug_print(f"Error in sequence analysis: {str(e)}")
            raise


def main():
    inspector = HighlightInspector(debug=True)

    input_json = "local_storage/frames.json"
    output_json = "local_storage/highlight_analysis.json"

    try:
        results, errors = inspector.analyze_sequence(input_json, output_json)

        print(f"\nAnalysis Complete - {len(results)} frames processed")
        print(
            f"Successful analyses: {sum(1 for r in results if r['status'] == 'success')}"
        )
        if errors:
            print(f"Errors encountered: {len(errors)}")
            for error in errors:
                print(f"- {error}")

    except Exception as e:
        print(f"Fatal error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
