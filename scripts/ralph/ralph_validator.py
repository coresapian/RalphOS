#!/usr/bin/env python3
"""
Ralph's Visual Validator (Final Gatekeeper)
===========================================
Uses Moondream 3 as a visual validation gate for Factory Ralph loops.

The validator provides a structured Pass/Fail result based on visual criteria,
ensuring Ralph doesn't "hallucinate" task completion.

Architecture:
    Code Phase → Screenshot → Validator → Pass? → Success / Retry

Features:
- Binary Pass/Fail validation
- OCR-based text verification
- UI layout validation
- Visual regression detection
- Structured reasoning output

Usage:
    from ralph_validator import RalphValidator

    validator = RalphValidator()

    # Simple validation
    result = validator.validate("screenshot.png", "The submit button is blue and visible")
    if result['passed']:
        create_success_file()
    else:
        print(f"Fix needed: {result['reasoning']}")

    # OCR validation
    result = validator.check_ocr("page.png", "Welcome, User")

    # Layout validation
    result = validator.check_ui_layout("dashboard.png", "Three columns with sidebar")
"""

import re
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime

# Try to import ralph_vlm
try:
    from ralph_vlm import MoondreamClient
except ImportError:
    MoondreamClient = None

# Try to import ralph_utils logger
try:
    from ralph_utils import logger as ralph_logger
except ImportError:
    ralph_logger = logging.getLogger(__name__)
    logging.basicConfig(level=logging.INFO)


class RalphValidator:
    """
    Visual validation gate using Moondream 3 VLM.

    The validator provides structured Pass/Fail results for visual verification,
    acting as a "second opinion" separate from the main LLM.
    """

    def __init__(self, provider: str = "ollama", log_dir: str = "tools/logs"):
        """
        Initialize the validator.

        Args:
            provider: VLM provider ('ollama' or 'huggingface')
            log_dir: Directory for validation logs
        """
        self.provider = provider
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.vlm = None

        self._init_vlm()

    def _init_vlm(self):
        """Initialize the VLM client."""
        if MoondreamClient is None:
            self._log("ERROR", "ralph_vlm not available. Install dependencies.")
            return

        try:
            self.vlm = MoondreamClient(provider=self.provider)
            self._log("INFO", f"Validator initialized with {self.provider}")
        except Exception as e:
            self._log("ERROR", f"Failed to initialize VLM: {e}")
            self.vlm = None

    def _log(self, level: str, message: str, data: Dict = None):
        """Log with ralph_utils or standard logging."""
        if hasattr(ralph_logger, 'log'):
            ralph_logger.log(level, f"[Validator] {message}", data)
        else:
            getattr(ralph_logger, level.lower(), ralph_logger.info)(f"[Validator] {message} {data or ''}")

    def _log_validation(self, image_path: str, criteria: str, result: Dict):
        """Log validation result to file."""
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "image": str(image_path),
            "criteria": criteria,
            "passed": result.get("passed", False),
            "reasoning": result.get("reasoning", ""),
            "raw_response": result.get("raw_response", "")
        }

        # Append to validation log
        log_file = self.log_dir / "validation_log.jsonl"
        import json
        with open(log_file, "a") as f:
            f.write(json.dumps(log_entry) + "\n")

    # ==========================================
    # CORE VALIDATION
    # ==========================================

    def validate(self, image_path: str, criteria: str) -> Dict[str, Any]:
        """
        Main validation function.
        Returns a structured Pass/Fail result.

        Args:
            image_path: Path to the screenshot
            criteria: The success criteria to validate

        Returns:
            Dict: {
                'passed': bool,
                'reasoning': str,
                'raw_response': str,
                'confidence': float (0-1)
            }

        Example:
            result = validator.validate("screenshot.png", "The login button is green and visible")
        """
        if not self.vlm:
            return {
                "passed": False,
                "reasoning": "VLM not available",
                "raw_response": "",
                "confidence": 0.0
            }

        if not Path(image_path).exists():
            return {
                "passed": False,
                "reasoning": f"Image not found: {image_path}",
                "raw_response": "",
                "confidence": 0.0
            }

        self._log("INFO", f"Validating", {"image": image_path, "criteria": criteria[:50]})

        # Construct strict validation prompt
        prompt = (
            "You are a strict visual validator. Your job is to verify if specific criteria are met.\n\n"
            f"CRITERIA TO CHECK: {criteria}\n\n"
            "INSTRUCTIONS:\n"
            "1. Carefully examine the image\n"
            "2. Check if the criteria are FULLY met\n"
            "3. Be strict - partial matches are FAIL\n\n"
            "RESPOND WITH EXACTLY ONE OF:\n"
            "- 'PASS' if criteria are fully met\n"
            "- 'FAIL: [specific reason why]' if criteria are not met\n\n"
            "Your response:"
        )

        try:
            response = self.vlm.analyze_image(image_path, prompt)
            result = self._parse_validation_response(response)

            self._log_validation(image_path, criteria, result)

            if result['passed']:
                self._log("SUCCESS", f"Validation PASSED", {"criteria": criteria[:30]})
            else:
                self._log("WARNING", f"Validation FAILED", {"reason": result['reasoning'][:50]})

            return result

        except Exception as e:
            self._log("ERROR", f"Validation error: {e}")
            return {
                "passed": False,
                "reasoning": f"Validation error: {str(e)}",
                "raw_response": "",
                "confidence": 0.0
            }

    def _parse_validation_response(self, response: str) -> Dict[str, Any]:
        """Parse VLM response into structured result."""
        clean_response = response.strip()

        # Check for PASS
        if clean_response.upper().startswith("PASS"):
            return {
                "passed": True,
                "reasoning": "Visual check successful",
                "raw_response": response,
                "confidence": 0.9
            }

        # Check for FAIL
        fail_match = re.search(r"FAIL[:\s]*(.*)", clean_response, re.IGNORECASE | re.DOTALL)
        if fail_match:
            reason = fail_match.group(1).strip() or "Criteria not met"
            return {
                "passed": False,
                "reasoning": reason,
                "raw_response": response,
                "confidence": 0.8
            }

        # Ambiguous response - try to interpret
        negative_indicators = ['no', 'not', 'cannot', 'don\'t', 'doesn\'t', 'missing', 'absent', 'fail']
        positive_indicators = ['yes', 'visible', 'present', 'found', 'correct', 'matches']

        response_lower = clean_response.lower()
        neg_count = sum(1 for indicator in negative_indicators if indicator in response_lower)
        pos_count = sum(1 for indicator in positive_indicators if indicator in response_lower)

        if pos_count > neg_count:
            return {
                "passed": True,
                "reasoning": "Inferred pass from response",
                "raw_response": response,
                "confidence": 0.6
            }
        else:
            return {
                "passed": False,
                "reasoning": response,
                "raw_response": response,
                "confidence": 0.5
            }

    # ==========================================
    # SPECIALIZED VALIDATORS
    # ==========================================

    def check_ocr(self, image_path: str, expected_text: str,
                  exact_match: bool = False) -> Dict[str, Any]:
        """
        Validate that specific text is visible in the image.

        Args:
            image_path: Path to image
            expected_text: Text that should be visible
            exact_match: Whether to require exact match

        Returns:
            Validation result dict
        """
        if exact_match:
            prompt = (
                f'Is the EXACT text "{expected_text}" visible in this image?\n'
                "Answer 'PASS' if the exact text is visible, 'FAIL: [reason]' if not."
            )
        else:
            prompt = (
                f'Is text containing "{expected_text}" visible anywhere in this image?\n'
                "Answer 'PASS' if found, 'FAIL: [reason]' if not visible."
            )

        try:
            response = self.vlm.analyze_image(image_path, prompt)
            result = self._parse_validation_response(response)

            self._log_validation(image_path, f"OCR: {expected_text}", result)
            return result

        except Exception as e:
            return {
                "passed": False,
                "reasoning": f"OCR check error: {str(e)}",
                "raw_response": "",
                "confidence": 0.0
            }

    def check_ui_layout(self, image_path: str, layout_description: str) -> Dict[str, Any]:
        """
        Validate that UI matches a layout description.

        Args:
            image_path: Path to UI screenshot
            layout_description: Expected layout (e.g., "Three columns with dark sidebar")

        Returns:
            Validation result dict
        """
        prompt = (
            f'Does this UI match the following layout description?\n\n'
            f'EXPECTED LAYOUT: {layout_description}\n\n'
            "Check:\n"
            "1. Overall structure matches\n"
            "2. Key elements are in correct positions\n"
            "3. General appearance aligns with description\n\n"
            "Answer 'PASS' if layout matches, 'FAIL: [specific differences]' if not."
        )

        try:
            response = self.vlm.analyze_image(image_path, prompt)
            result = self._parse_validation_response(response)

            self._log_validation(image_path, f"Layout: {layout_description}", result)
            return result

        except Exception as e:
            return {
                "passed": False,
                "reasoning": f"Layout check error: {str(e)}",
                "raw_response": "",
                "confidence": 0.0
            }

    def check_element_visible(self, image_path: str, element: str) -> Dict[str, Any]:
        """
        Check if a specific UI element is visible.

        Args:
            image_path: Path to screenshot
            element: Element description (e.g., "blue submit button", "navigation menu")

        Returns:
            Validation result dict
        """
        prompt = (
            f'Is the following UI element visible in this image?\n\n'
            f'ELEMENT: {element}\n\n'
            "Answer 'PASS' if the element is clearly visible, 'FAIL: [reason]' if not."
        )

        try:
            response = self.vlm.analyze_image(image_path, prompt)
            result = self._parse_validation_response(response)

            self._log_validation(image_path, f"Element: {element}", result)
            return result

        except Exception as e:
            return {
                "passed": False,
                "reasoning": f"Element check error: {str(e)}",
                "raw_response": "",
                "confidence": 0.0
            }

    def check_color(self, image_path: str, element: str, expected_color: str) -> Dict[str, Any]:
        """
        Validate the color of a UI element.

        Args:
            image_path: Path to screenshot
            element: Element to check
            expected_color: Expected color (e.g., "blue", "red", "#ff0000")

        Returns:
            Validation result dict
        """
        prompt = (
            f'Check the color of this UI element: {element}\n\n'
            f'EXPECTED COLOR: {expected_color}\n\n'
            "Answer 'PASS' if the color matches (approximately), 'FAIL: [actual color]' if different."
        )

        try:
            response = self.vlm.analyze_image(image_path, prompt)
            result = self._parse_validation_response(response)

            self._log_validation(image_path, f"Color: {element}={expected_color}", result)
            return result

        except Exception as e:
            return {
                "passed": False,
                "reasoning": f"Color check error: {str(e)}",
                "raw_response": "",
                "confidence": 0.0
            }

    def check_state(self, image_path: str, element: str, expected_state: str) -> Dict[str, Any]:
        """
        Validate the state of a UI element.

        Args:
            image_path: Path to screenshot
            element: Element to check
            expected_state: Expected state (e.g., "enabled", "disabled", "selected", "loading")

        Returns:
            Validation result dict
        """
        prompt = (
            f'Check the state of this UI element: {element}\n\n'
            f'EXPECTED STATE: {expected_state}\n\n'
            "Look for visual cues like:\n"
            "- Grayed out = disabled\n"
            "- Highlighted/checked = selected\n"
            "- Spinner/skeleton = loading\n"
            "- Normal appearance = enabled\n\n"
            "Answer 'PASS' if state matches, 'FAIL: [actual state]' if different."
        )

        try:
            response = self.vlm.analyze_image(image_path, prompt)
            result = self._parse_validation_response(response)

            self._log_validation(image_path, f"State: {element}={expected_state}", result)
            return result

        except Exception as e:
            return {
                "passed": False,
                "reasoning": f"State check error: {str(e)}",
                "raw_response": "",
                "confidence": 0.0
            }

    # ==========================================
    # MULTI-CRITERIA VALIDATION
    # ==========================================

    def validate_all(self, image_path: str, criteria_list: List[str]) -> Dict[str, Any]:
        """
        Validate multiple criteria against a single image.
        All criteria must pass for overall pass.

        Args:
            image_path: Path to screenshot
            criteria_list: List of criteria to check

        Returns:
            Dict with overall result and individual results
        """
        results = []
        all_passed = True

        for criteria in criteria_list:
            result = self.validate(image_path, criteria)
            results.append({
                "criteria": criteria,
                "passed": result['passed'],
                "reasoning": result['reasoning']
            })
            if not result['passed']:
                all_passed = False

        return {
            "passed": all_passed,
            "total_criteria": len(criteria_list),
            "passed_count": sum(1 for r in results if r['passed']),
            "results": results,
            "reasoning": "All criteria passed" if all_passed else "One or more criteria failed"
        }

    # ==========================================
    # UTILITY METHODS
    # ==========================================

    def is_available(self) -> bool:
        """Check if validator is ready for use."""
        return self.vlm is not None and self.vlm.is_available()

    def get_validation_history(self, limit: int = 10) -> List[Dict]:
        """Get recent validation results from log."""
        import json

        log_file = self.log_dir / "validation_log.jsonl"
        if not log_file.exists():
            return []

        entries = []
        with open(log_file, 'r') as f:
            for line in f:
                try:
                    entries.append(json.loads(line))
                except:
                    pass

        return entries[-limit:]

    def get_pass_rate(self) -> float:
        """Calculate validation pass rate from history."""
        history = self.get_validation_history(100)
        if not history:
            return 0.0

        passed = sum(1 for h in history if h.get('passed', False))
        return passed / len(history)


# ==========================================
# CLI INTERFACE
# ==========================================

def cli_validate(image_path: str, criteria: str) -> bool:
    """
    CLI validation function.
    Returns True if passed, False otherwise.
    """
    validator = RalphValidator()
    result = validator.validate(image_path, criteria)

    print(f"Result: {'PASS' if result['passed'] else 'FAIL'}")
    print(f"Reasoning: {result['reasoning']}")

    return result['passed']


# ==========================================
# MAIN
# ==========================================

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 3:
        print("Usage: python ralph_validator.py <image_path> <criteria>")
        print("Example: python ralph_validator.py screenshot.png 'The submit button is blue'")
        sys.exit(1)

    image_path = sys.argv[1]
    criteria = ' '.join(sys.argv[2:])

    print(f"Image: {image_path}")
    print(f"Criteria: {criteria}")
    print("-" * 50)

    success = cli_validate(image_path, criteria)
    sys.exit(0 if success else 1)
