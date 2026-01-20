#!/usr/bin/env python3
"""
Ralph's Vision Language Model (VLM) Helper
==========================================
Supports Moondream 3 via Hugging Face (Local) and Ollama (API).

Moondream 3 is a lightweight VLM (~2B parameters) that runs efficiently
on consumer hardware while providing excellent visual understanding.

Features:
- Visual Question Answering (VQA)
- OCR / Text Extraction
- UI Element Detection
- Chart/Graph Analysis
- Spatial Understanding
- React/Vue State Inspection (via screenshots)

Usage:
    from ralph_vlm import MoondreamClient

    # Using Ollama (faster startup, OpenAI-compatible)
    vlm = MoondreamClient(provider="ollama")

    # Using Hugging Face (newest features, local)
    vlm = MoondreamClient(provider="huggingface")

    # Analyze an image
    result = vlm.analyze_image("screenshot.png", "What color is the submit button?")
"""

import os
import base64
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List, Union

# Try to import ralph_utils logger
try:
    from ralph_utils import logger as ralph_logger
except ImportError:
    ralph_logger = logging.getLogger(__name__)
    logging.basicConfig(level=logging.INFO)


class MoondreamClient:
    """
    Wrapper for Moondream VLM.

    Modes:
    - 'ollama': Uses a local Ollama API endpoint (Fast, OpenAI compatible).
    - 'huggingface': Loads the raw model weights from Hugging Face (Newest features).

    Moondream 3 Capabilities:
    - Visual Question Answering
    - OCR / Text Recognition
    - Object Detection & Spatial Understanding
    - UI Element Analysis
    - Chart/Graph Interpretation
    - Code Screenshot Analysis
    """

    # Model identifiers
    MODELS = {
        "huggingface": "vikhyatk/moondream2",  # moondream2 is the latest stable
        "ollama": "moondream"
    }

    def __init__(self,
                 provider: str = "ollama",
                 model_id: str = None,
                 ollama_url: str = "http://localhost:11434"):
        """
        Initialize the VLM client.

        Args:
            provider: 'ollama' or 'huggingface'
            model_id: Model identifier (uses default if None)
            ollama_url: Ollama API base URL
        """
        self.provider = provider.lower()
        self.model_id = model_id or self.MODELS.get(self.provider, "moondream")
        self.ollama_url = ollama_url
        self.model = None
        self.tokenizer = None

        self._log("INFO", f"Initializing VLM", {"provider": self.provider, "model": self.model_id})

        if self.provider == "huggingface":
            self._load_huggingface_model()
        elif self.provider == "ollama":
            self._setup_ollama()
        else:
            raise ValueError(f"Unknown provider: {provider}. Use 'ollama' or 'huggingface'")

    def _log(self, level: str, message: str, data: Dict = None):
        """Log with ralph_utils or standard logging."""
        if hasattr(ralph_logger, 'log'):
            ralph_logger.log(level, message, data)
        else:
            getattr(ralph_logger, level.lower(), ralph_logger.info)(f"{message} {data or ''}")

    # ==========================================
    # PROVIDER SETUP
    # ==========================================

    def _load_huggingface_model(self):
        """Load Moondream from Hugging Face Transformers."""
        try:
            from transformers import AutoModelForCausalLM, AutoTokenizer
            import torch

            self._log("INFO", "Loading Moondream from Hugging Face...")

            # Determine device
            if torch.cuda.is_available():
                device = "cuda"
                dtype = torch.float16
            elif hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
                device = "mps"
                dtype = torch.float32
            else:
                device = "cpu"
                dtype = torch.float32

            self._log("INFO", f"Using device: {device}")

            # Load model
            self.model = AutoModelForCausalLM.from_pretrained(
                self.model_id,
                trust_remote_code=True,
                torch_dtype=dtype,
                device_map="auto" if device != "cpu" else None
            )

            self.tokenizer = AutoTokenizer.from_pretrained(
                self.model_id,
                trust_remote_code=True
            )

            if device == "cpu":
                self.model = self.model.to(device)

            self._log("SUCCESS", "Moondream loaded successfully", {"device": device})

        except ImportError as e:
            self._log("ERROR", f"Missing dependencies: {e}")
            raise ImportError(
                "Required packages not found. Run:\n"
                "pip install transformers torch accelerate pillow"
            )
        except Exception as e:
            self._log("ERROR", f"Failed to load HF model: {e}")
            raise

    def _setup_ollama(self):
        """Setup Ollama client configuration."""
        try:
            import requests

            # Health check
            try:
                r = requests.get(f"{self.ollama_url}/api/tags", timeout=5)
                r.raise_for_status()

                # Check if moondream model is available
                models = r.json().get('models', [])
                model_names = [m.get('name', '').split(':')[0] for m in models]

                if 'moondream' not in model_names:
                    self._log("WARNING", "Moondream not found in Ollama. Run: ollama pull moondream")
                else:
                    self._log("SUCCESS", "Connected to Ollama API")

            except requests.exceptions.RequestException as e:
                self._log("ERROR", f"Could not connect to Ollama at {self.ollama_url}")
                raise ConnectionError(
                    f"Ollama not running at {self.ollama_url}. "
                    "Start it with: ollama serve"
                )

        except ImportError:
            raise ImportError("requests library required. Run: pip install requests")

    # ==========================================
    # IMAGE HANDLING
    # ==========================================

    def _load_image(self, image_path: str):
        """Load and prepare an image for analysis."""
        from PIL import Image

        path = Path(image_path)
        if not path.exists():
            raise FileNotFoundError(f"Image not found: {image_path}")

        image = Image.open(path)

        # Convert to RGB if necessary
        if image.mode != 'RGB':
            image = image.convert('RGB')

        return image

    def _image_to_base64(self, image_path: str) -> str:
        """Convert image to base64 for API calls."""
        with open(image_path, 'rb') as f:
            return base64.b64encode(f.read()).decode('utf-8')

    # ==========================================
    # CORE ANALYSIS
    # ==========================================

    def analyze_image(self, image_path: str, prompt: str) -> str:
        """
        Analyze an image with a specific question/prompt.

        Args:
            image_path: Path to the image file
            prompt: Question or instruction about the image

        Returns:
            Model's text response

        Example:
            result = vlm.analyze_image("screenshot.png", "What is the main color?")
        """
        self._log("INFO", f"Analyzing image", {"image": image_path, "prompt": prompt[:50]})

        if self.provider == "huggingface":
            return self._analyze_hf(image_path, prompt)
        else:
            return self._analyze_ollama(image_path, prompt)

    def _analyze_hf(self, image_path: str, prompt: str) -> str:
        """Analyze using Hugging Face model."""
        image = self._load_image(image_path)

        # Moondream uses a specific encoding method
        enc_image = self.model.encode_image(image)
        response = self.model.answer_question(enc_image, prompt, self.tokenizer)

        return response.strip()

    def _analyze_ollama(self, image_path: str, prompt: str) -> str:
        """Analyze using Ollama API."""
        import requests

        image_b64 = self._image_to_base64(image_path)

        payload = {
            "model": self.model_id,
            "prompt": prompt,
            "images": [image_b64],
            "stream": False
        }

        try:
            response = requests.post(
                f"{self.ollama_url}/api/generate",
                json=payload,
                timeout=60
            )
            response.raise_for_status()

            result = response.json()
            return result.get('response', '').strip()

        except requests.exceptions.RequestException as e:
            self._log("ERROR", f"Ollama API error: {e}")
            raise

    # ==========================================
    # SPECIALIZED ANALYSIS METHODS
    # ==========================================

    def extract_text(self, image_path: str, region: str = None) -> str:
        """
        Extract text from an image (OCR).

        Args:
            image_path: Path to image
            region: Optional region description (e.g., "top right corner")

        Returns:
            Extracted text
        """
        if region:
            prompt = f"Read and extract all text visible in the {region} of this image. Return only the text content."
        else:
            prompt = "Read and extract all visible text from this image. Return only the text content, preserving the layout where possible."

        return self.analyze_image(image_path, prompt)

    def describe_ui(self, image_path: str) -> str:
        """
        Get a description of a UI screenshot.

        Args:
            image_path: Path to UI screenshot

        Returns:
            UI description
        """
        prompt = """Describe this UI screenshot. Include:
1. Main layout structure
2. Key UI elements visible (buttons, forms, navigation)
3. Color scheme
4. Any text content
5. Current state (loading, error, success, etc.)"""

        return self.analyze_image(image_path, prompt)

    def find_element(self, image_path: str, element_description: str) -> Dict[str, Any]:
        """
        Find a UI element in a screenshot.

        Args:
            image_path: Path to screenshot
            element_description: Description of element to find

        Returns:
            Dict with found status and description
        """
        prompt = f"""Look for this UI element: "{element_description}"

If found, describe:
1. Where it is located (top/bottom, left/right)
2. Its approximate size (small/medium/large)
3. Its current state (enabled/disabled, selected/unselected)
4. Any text on or near it

If not found, say "NOT FOUND" and describe what similar elements exist."""

        response = self.analyze_image(image_path, prompt)

        return {
            "found": "NOT FOUND" not in response.upper(),
            "description": response
        }

    def check_text_presence(self, image_path: str, expected_text: str) -> Dict[str, Any]:
        """
        Check if specific text is visible in an image.

        Args:
            image_path: Path to image
            expected_text: Text to look for

        Returns:
            Dict with found status and context
        """
        prompt = f'Is the text "{expected_text}" visible in this image? Answer YES or NO, then describe where you see it or what similar text exists.'

        response = self.analyze_image(image_path, prompt)

        return {
            "found": response.upper().startswith("YES"),
            "response": response
        }

    def analyze_chart(self, image_path: str, question: str = None) -> str:
        """
        Analyze a chart or data visualization.

        Args:
            image_path: Path to chart image
            question: Optional specific question

        Returns:
            Chart analysis
        """
        if question:
            prompt = f"Analyze this chart/graph. {question}"
        else:
            prompt = """Analyze this chart or graph. Describe:
1. Type of chart (bar, line, pie, etc.)
2. What data it represents
3. Key trends or patterns
4. Notable values or outliers
5. Overall insight"""

        return self.analyze_image(image_path, prompt)

    def compare_images(self, image1_path: str, image2_path: str,
                       aspect: str = "visual differences") -> str:
        """
        Compare two images (note: processes sequentially).

        Args:
            image1_path: Path to first image
            image2_path: Path to second image
            aspect: What to compare

        Returns:
            Comparison result
        """
        # Analyze first image
        desc1 = self.analyze_image(image1_path, "Describe this image in detail.")

        # Analyze second image
        desc2 = self.analyze_image(image2_path, "Describe this image in detail.")

        # Compare (using text comparison since Moondream is single-image)
        prompt = f"""Compare these two image descriptions and identify {aspect}:

Image 1: {desc1}

Image 2: {desc2}

List the key differences."""

        # Use a text-based analysis for comparison
        return f"Image 1: {desc1}\n\nImage 2: {desc2}\n\nNote: Manual comparison needed for precise visual diff."

    def get_color_info(self, image_path: str, element: str = None) -> str:
        """
        Get color information from an image.

        Args:
            image_path: Path to image
            element: Optional specific element to check

        Returns:
            Color description
        """
        if element:
            prompt = f"What is the color of the {element} in this image? Be specific about the color (e.g., 'dark blue #1a2b3c' or 'bright red')."
        else:
            prompt = "What are the main colors in this image? List the dominant colors and where they appear."

        return self.analyze_image(image_path, prompt)

    # ==========================================
    # BATCH PROCESSING
    # ==========================================

    def batch_analyze(self, image_paths: List[str], prompt: str,
                      progress_callback=None) -> List[Dict[str, Any]]:
        """
        Analyze multiple images with the same prompt.

        Args:
            image_paths: List of image paths
            prompt: Question to ask about each image
            progress_callback: Optional callback(current, total)

        Returns:
            List of results with image path and response
        """
        results = []
        total = len(image_paths)

        for i, path in enumerate(image_paths):
            try:
                response = self.analyze_image(path, prompt)
                results.append({
                    "image": path,
                    "response": response,
                    "success": True
                })
            except Exception as e:
                results.append({
                    "image": path,
                    "response": str(e),
                    "success": False
                })

            if progress_callback:
                progress_callback(i + 1, total)

        return results

    # ==========================================
    # UTILITIES
    # ==========================================

    def is_available(self) -> bool:
        """Check if the VLM is ready for use."""
        if self.provider == "huggingface":
            return self.model is not None and self.tokenizer is not None
        else:
            try:
                import requests
                r = requests.get(f"{self.ollama_url}/api/tags", timeout=2)
                return r.status_code == 200
            except:
                return False

    def get_info(self) -> Dict[str, Any]:
        """Get information about the current VLM setup."""
        return {
            "provider": self.provider,
            "model_id": self.model_id,
            "available": self.is_available(),
            "ollama_url": self.ollama_url if self.provider == "ollama" else None
        }


# ==========================================
# CONVENIENCE FUNCTIONS
# ==========================================

def get_vlm(provider: str = "ollama") -> MoondreamClient:
    """
    Get a MoondreamClient instance.
    Convenience function for quick access.

    Args:
        provider: 'ollama' or 'huggingface'

    Returns:
        MoondreamClient instance
    """
    return MoondreamClient(provider=provider)


def quick_analyze(image_path: str, prompt: str, provider: str = "ollama") -> str:
    """
    Quick one-off image analysis.

    Args:
        image_path: Path to image
        prompt: Question about the image
        provider: VLM provider to use

    Returns:
        Analysis result
    """
    vlm = MoondreamClient(provider=provider)
    return vlm.analyze_image(image_path, prompt)


# ==========================================
# CLI
# ==========================================

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 3:
        print("Usage: python ralph_vlm.py <image_path> <prompt>")
        print("Example: python ralph_vlm.py screenshot.png 'What color is the button?'")
        sys.exit(1)

    image_path = sys.argv[1]
    prompt = ' '.join(sys.argv[2:])

    print(f"Analyzing: {image_path}")
    print(f"Prompt: {prompt}")
    print("-" * 50)

    try:
        vlm = MoondreamClient(provider="ollama")
        result = vlm.analyze_image(image_path, prompt)
        print(f"Result: {result}")
    except Exception as e:
        print(f"Error: {e}")
        print("\nTrying Hugging Face provider...")
        try:
            vlm = MoondreamClient(provider="huggingface")
            result = vlm.analyze_image(image_path, prompt)
            print(f"Result: {result}")
        except Exception as e2:
            print(f"Hugging Face also failed: {e2}")
            sys.exit(1)
