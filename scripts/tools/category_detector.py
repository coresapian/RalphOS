#!/usr/bin/env python3
"""
Category Detector for Vehicle Modifications

Automatically detects the category for a modification name using the
Vehicle_Components.json schema. Uses fuzzy matching for flexible lookups.

Usage:
 # As module
 from category_detector import detect_category
 category = detect_category("Control Arm") # Returns "Suspension"
 
 # Command line
 python category_detector.py "Control Arm"
 python category_detector.py "Input Shaft Repair Sleeve"
 python category_detector.py --batch mods.txt
 python category_detector.py --test
"""

import json
import re
import sys
from pathlib import Path
from typing import Optional, Tuple, Dict, List
from difflib import SequenceMatcher

# Load the component schema
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
COMPONENTS_FILE = PROJECT_ROOT / "schema" / "Vehicle_Componets.json"

# Global lookup tables (initialized on first use)
_component_to_category: Dict[str, str] = {}
_category_keywords: Dict[str, List[str]] = {}
_keyword_trie: Optional['CategoryTrie'] = None
_initialized = False


class TrieNode:
 """Node in the keyword trie."""
 __slots__ = ['children', 'category', 'keyword', 'is_end']
 
 def __init__(self):
 self.children: Dict[str, 'TrieNode'] = {}
 self.category: Optional[str] = None # Category if this is end of keyword
 self.keyword: Optional[str] = None # Original keyword
 self.is_end: bool = False


class CategoryTrie:
 """
 Trie data structure for fast keyword matching.
 
 Provides O(k) lookup where k = length of query, instead of O(n*k) 
 where n = number of keywords.
 """
 
 def __init__(self):
 self.root = TrieNode()
 self._keyword_count = 0
 
 def insert(self, keyword: str, category: str):
 """Insert a keyword-category mapping into the trie."""
 node = self.root
 keyword_lower = keyword.lower()
 
 for char in keyword_lower:
 if char not in node.children:
 node.children[char] = TrieNode()
 node = node.children[char]
 
 node.is_end = True
 node.category = category
 node.keyword = keyword
 self._keyword_count += 1
 
 def search_exact(self, query: str) -> Optional[Tuple[str, str]]:
 """
 Search for exact keyword match.
 
 Returns:
 Tuple of (category, matched_keyword) or None
 """
 node = self.root
 query_lower = query.lower()
 
 for char in query_lower:
 if char not in node.children:
 return None
 node = node.children[char]
 
 if node.is_end:
 return (node.category, node.keyword)
 return None
 
 def search_prefix(self, query: str) -> List[Tuple[str, str, int]]:
 """
 Find all keywords that are prefixes of the query.
 
 Returns:
 List of (category, keyword, end_position) tuples
 """
 results = []
 node = self.root
 query_lower = query.lower()
 
 for i, char in enumerate(query_lower):
 if char not in node.children:
 break
 node = node.children[char]
 
 if node.is_end:
 results.append((node.category, node.keyword, i + 1))
 
 return results
 
 def search_all_in_text(self, text: str, min_keyword_len: int = 5) -> List[Tuple[str, str, int, int]]:
 """
 Find all keywords that appear anywhere in the text.
 
 This is the key optimization - instead of checking every keyword against
 the text O(n*k), we scan the text once and check each position O(m*k)
 where m = text length, k = average keyword length.
 
 Args:
 text: Text to search in
 min_keyword_len: Minimum keyword length to match (avoid false positives)
 
 Returns:
 List of (category, keyword, start_pos, end_pos) tuples
 """
 results = []
 text_lower = text.lower()
 text_len = len(text_lower)
 
 # Try starting from each position in the text
 for start in range(text_len):
 node = self.root
 
 for i in range(start, text_len):
 char = text_lower[i]
 
 if char not in node.children:
 break
 
 node = node.children[char]
 
 if node.is_end:
 keyword_len = i - start + 1
 if keyword_len >= min_keyword_len:
 # Check word boundaries for better accuracy
 is_word_start = start == 0 or not text_lower[start - 1].isalnum()
 is_word_end = i == text_len - 1 or not text_lower[i + 1].isalnum()
 
 # Prefer whole word matches but accept substrings for long keywords
 if is_word_start and is_word_end:
 results.append((node.category, node.keyword, start, i + 1))
 elif keyword_len >= 8: # Accept substring for long keywords
 results.append((node.category, node.keyword, start, i + 1))
 
 return results
 
 def find_best_match(self, text: str, min_keyword_len: int = 5) -> Optional[Tuple[str, str, float]]:
 """
 Find the best keyword match in text with confidence score.
 
 Returns:
 Tuple of (category, keyword, confidence) or None
 """
 matches = self.search_all_in_text(text, min_keyword_len)
 
 if not matches:
 return None
 
 # Score matches by length and position
 best_match = None
 best_score = 0.0
 
 for category, keyword, start, end in matches:
 keyword_len = end - start
 text_len = len(text)
 
 # Score based on keyword length relative to text
 length_score = keyword_len / text_len
 
 # Bonus for longer matches
 length_bonus = min(keyword_len / 10, 0.3)
 
 score = length_score + length_bonus + 0.3 # Base score for finding a match
 score = min(score, 1.0)
 
 if score > best_score:
 best_score = score
 best_match = (category, keyword, score)
 
 return best_match
 
 @property
 def keyword_count(self) -> int:
 return self._keyword_count


def _build_keyword_trie() -> CategoryTrie:
 """Build trie from category keywords."""
 trie = CategoryTrie()
 
 for category, keywords in _category_keywords.items():
 for keyword in keywords:
 trie.insert(keyword, category)
 
 return trie


def _initialize():
 """Load and index the components file."""
 global _component_to_category, _category_keywords, _keyword_trie, _initialized
 
 if _initialized:
 return
 
 if not COMPONENTS_FILE.exists():
 raise FileNotFoundError(f"Components file not found: {COMPONENTS_FILE}")
 
 with open(COMPONENTS_FILE, "r") as f:
 data = json.load(f)
 
 # Build inverted index: component name → category
 for category, components in data.items():
 for component in components:
 # Store lowercase for matching
 _component_to_category[component.lower()] = category
 
 # Build category keywords for fallback matching
 # Priority order matters - more specific categories first
 # Each entry is (category, keywords, priority_boost)
 _category_keywords = {
 # HIGH PRIORITY - Very specific categories that should win
 "Forced Induction": [
 "turbo", "turbocharger", "supercharger", "supercharged", "boost controller",
 "wastegate", "blow off valve", "bov", "diverter valve", "charge pipe",
 "turbine", "garrett turbo", "precision turbo", "borgwarner turbo", 
 "borg warner turbo", "hks turbo", "greddy turbo", "trust turbo",
 "gt28", "gt30", "gt35", "gt40", "gtx turbo", "t3 turbo", "t4 turbo", "t04",
 "twin turbo", "single turbo", "procharger", "vortech", "whipple supercharger",
 "intercooler", "fmic", "tmic"
 ],
 "Oil": [
 "oil pan", "oil pump", "oil filter", "catch can", "breather",
 "pcv", "oil line", "dipstick", "motor oil", "engine oil",
 "synthetic oil", "motul", "amsoil", "royal purple", "redline oil",
 "300v", "5w30", "10w40", "oil change"
 ],
 "Wheel": [
 "wheels", "rims", "tires", "tpms sensor", "lug nut", "lug nuts",
 "wheel spacer", "wheel adapter", "center cap", "hub ring", "valve stem",
 "work wheels", "volk wheels", "rays wheels", "enkei wheels", "ssr wheels", 
 "bbs wheels", "hre wheels", "rotiform wheels", "fifteen52 wheels", 
 "method wheels", "fuel wheels", "american racing wheels"
 ],
 "Safety": [
 "racing harness", "safety harness", "5-point harness", "6-point harness",
 "fire extinguisher", "kill switch", "window net", "arm restraint",
 "roll cage", "halo bar", "hans device", "neck brace",
 "sparco harness", "schroth harness", "takata harness", "sabelt harness"
 ],
 "Lighting": [
 "light bar", "led bar", "pod light", "cube light", "driving light", 
 "spot light", "flood light", "auxiliary light", "aux light", 
 "rock light", "ditch light", "rigid", "baja designs", "kc hilites",
 "vision x", "diode dynamics"
 ],
 "Storage": [
 "roof rack", "bed rack", "cargo rack", "drawer system", "cargo box",
 "awning", "rooftop tent", "rtt", "camper shell", "truck cap",
 "prinsu rack", "frontrunner rack", "gobi rack", "yakima rack"
 ],
 "Recovery": [
 "winch", "recovery gear", "shackle", "d-ring", "tow strap", 
 "snatch strap", "hi-lift", "hilift", "farm jack", "traction board", 
 "maxtrax", "recovery board", "warn winch", "smittybilt winch"
 ],
 "Armor/Protection": [
 "skid plate", "rock slider", "armor", "bash plate", "diff guard",
 "diff skid", "transfer case guard", "nerf bar", "rock rail",
 "cbi offroad", "relentless", "rci offroad"
 ],
 # MEDIUM PRIORITY
 "Suspension": [
 "coilover", "coilovers", "coil over", "springs", "shocks", "struts", 
 "control arm", "sway bar", "stabilizer bar", "bushing", "ball joint", 
 "camber", "caster", "alignment", "lowering", "lift kit", "leveling kit", 
 "airbag suspension", "air ride", "trailing arm", "subframe", 
 "knuckle", "bump stop", "ride height", "suspension",
 # Specific brands
 "tein coilover", "bc racing coilover", "bc coilover", "kw coilover", 
 "bilstein shock", "icon suspension", "king shocks", "fox shocks", 
 "eibach spring", "eibach springs", "h&r springs", "cusco sway", 
 "whiteline sway", "ohlins coilover", "fortune auto", "stance coilover", 
 "megan racing coilover", "bc racing br", "bc br series"
 ],
 "Fuel & Air": [
 "intake", "air filter", "cold air intake", "cai", "short ram intake",
 "throttle body", "fuel injector", "fuel pump", "fuel rail", 
 "fuel regulator", "carburetor", "mass air flow", "maf sensor",
 "air box", "intake system",
 # Specific brands
 "injen intake", "injen cold air", "aem intake", "k&n filter", 
 "k&n intake", "spectre intake", "afe intake", "mishimoto intake",
 "holley carb", "edelbrock carb", "weber carb"
 ],
 "Brake & Wheel Hub": [
 "brake", "caliper", "rotor", "brake pad", "disc brake", "drum brake", 
 "abs module", "master cylinder", "brake booster", "brake line", 
 "brake hose", "wheel bearing", "wheel hub", "bbk", "big brake kit", 
 "slotted rotor", "drilled rotor", "cross drilled",
 # Specific brands
 "brembo brake", "brembo caliper", "wilwood brake", "wilwood caliper",
 "stoptech brake", "stoptech big brake", "ebc brake", "hawk brake pad",
 "ap racing brake", "baer brake"
 ],
 "Engine": [
 "engine", "motor", "block", "head", "cam", "camshaft", "piston",
 "connecting rod", "crank", "crankshaft", "valve", "intake manifold", 
 "gasket", "timing", "chain", "engine mount", "swap", "rebuild", 
 "bore", "stroke", "tomei", "kelford", "brian crower"
 ],
 "Exhaust & Emission": [
 "exhaust", "header", "exhaust manifold", "downpipe", "cat", 
 "catalytic converter", "muffler", "resonator", "exhaust tip", 
 "exhaust pipe", "catback", "cat-back", "turbo back", "axle back", 
 "o2 sensor", "oxygen sensor", "egr", "borla", "magnaflow", 
 "flowmaster", "invidia", "tomei exhaust"
 ],
 "Interior": [
 "seat", "racing seat", "steering wheel", "shift knob", "pedal",
 "carpet", "floor mat", "console", "dash", "gauge pod", "roll bar",
 "roll cage", "door panel", "headliner", "audio", "stereo",
 "speaker", "subwoofer", "amplifier", "radio", "navigation",
 "recaro", "bride", "sparco seat", "nrg"
 ],
 "Drivetrain": [
 "differential", "diff", "lsd", "limited slip", "axle", "cv axle",
 "driveshaft", "u-joint", "pinion", "gear set", "gear ratio", 
 "locker", "posi", "ring and pinion"
 ],
 "Transmission-Manual": [
 "clutch", "clutch kit", "flywheel", "pressure plate", "throw out bearing", 
 "slave cylinder", "clutch master", "shifter", "shift knob", 
 "short throw shifter", "trans mount", "manual transmission",
 # Specific brands
 "act clutch", "exedy clutch", "competition clutch", "spec clutch",
 "south bend clutch", "mcleod clutch", "centerforce clutch"
 ],
 "Transmission-Automatic": [
 "torque converter", "trans cooler", "shift kit", "valve body",
 "auto trans", "automatic transmission", "trans pan", "trans filter"
 ],
 "Electrical": [
 "battery", "alternator", "starter", "wire", "wiring", "harness",
 "relay", "fuse box", "ecu", "tune", "tuner", "programmer", "chip",
 "module", "controller", "volt", "optima battery"
 ],
 "Cooling System": [
 "radiator", "coolant", "thermostat", "water pump", "cooling fan",
 "heat exchanger", "overflow tank", "mishimoto radiator", 
 "koyo radiator", "csf radiator"
 ],
 "Body & Lamp Assembly": [
 "headlight", "taillight", "fog light", "led bulb", "hid headlight",
 "bumper", "front bumper", "rear bumper", "fender", "hood", "grille", 
 "splitter", "diffuser", "spoiler", "wing", "body kit", "widebody", 
 "fender flare", "lip kit", "side skirt", "mirror", "door", "trunk", "hatch",
 # Specific brands
 "arb bumper", "arb front", "arb rear", "go industries", "fab fours",
 "iron cross", "westin bumper", "smittybilt bumper", "poison spyder"
 ],
 "Steering": [
 "steering rack", "power steering", "steering pump", "steering line",
 "steering column", "quick release hub", "tie rod"
 ],
 "Heat & Air Conditioning": [
 "a/c compressor", "ac compressor", "air conditioning", "condenser",
 "evaporator", "heater core", "hvac", "climate control", "blower motor"
 ],
 "Ignition": [
 "spark plug", "ignition coil", "distributor", "distributor cap",
 "rotor", "plug wire", "coil pack", "cdi", "msd ignition"
 ],
 "Belt Drive": [
 "serpentine belt", "drive belt", "tensioner", "idler pulley", 
 "v-belt", "belt"
 ],
 "Wiper & Washer": [
 "wiper", "wiper blade", "washer", "washer nozzle", "washer reservoir"
 ],
 "Aero": [
 "splitter", "front splitter", "diffuser", "rear diffuser", "canard",
 "aero", "undertray", "air dam", "vortex generator", "apr aero", 
 "voltex", "seibon"
 ]
 }
 
 # Build the keyword trie for O(k) lookups
 _keyword_trie = _build_keyword_trie()
 
 _initialized = True


def _normalize(text: str) -> str:
 """Normalize text for matching."""
 # Lowercase
 text = text.lower()
 # Remove common brand prefixes/suffixes
 text = re.sub(r'^(hks|trust|greddy|apexi|cusco|tein|bc racing|kw|bilstein|eibach|h&r|borla|magnaflow|flowmaster|msd|edelbrock|holley|k&n|aem|injen|mishimoto|brembo|wilwood|apr|stoptech|hawk)\s+', '', text)
 # Remove size/spec info
 text = re.sub(r'\d+(\.\d+)?\s*(mm|inch|"|\')?\s*', '', text)
 # Remove common words
 text = re.sub(r'\b(kit|set|assembly|system|upgrade|performance|racing|sport|pro|series|v\d|mk\d|gen\d)\b', '', text)
 # Clean up whitespace
 text = re.sub(r'\s+', ' ', text).strip()
 return text


def _fuzzy_match(query: str, target: str) -> float:
 """Calculate fuzzy match score between query and target."""
 return SequenceMatcher(None, query.lower(), target.lower()).ratio()


def _word_match(query: str, targets: List[str]) -> Tuple[Optional[str], float]:
 """Check if any word in query matches any target keyword."""
 query_words = set(query.lower().split())
 best_match = None
 best_score = 0.0
 
 for target in targets:
 target_lower = target.lower()
 target_words = set(target_lower.split())
 
 # Check if full target phrase exists in query
 if target_lower in query.lower():
 score = len(target) / len(query) + 0.5
 if score > best_score:
 best_score = min(score, 1.0)
 best_match = target
 continue
 
 # Check exact word overlap (no substrings)
 overlap = query_words & target_words
 if overlap:
 # Only count if words are meaningful (4+ chars)
 meaningful_overlap = [w for w in overlap if len(w) >= 4]
 if meaningful_overlap:
 score = len(meaningful_overlap) / max(len(query_words), len(target_words))
 if score > best_score:
 best_score = score
 best_match = target
 
 return best_match, best_score


def detect_category(mod_name: str, return_confidence: bool = False) -> str | Tuple[str, float]:
 """
 Detect the category for a modification name.
 
 Args:
 mod_name: The name of the modification (e.g., "Control Arm", "KW Coilovers")
 return_confidence: If True, also return confidence score (0.0-1.0)
 
 Returns:
 Category name (e.g., "Suspension")
 Or tuple of (category, confidence) if return_confidence=True
 """
 _initialize()
 
 if not mod_name or not mod_name.strip():
 result = ("Other", 0.0)
 return result if return_confidence else result[0]
 
 # Normalize the input
 normalized = _normalize(mod_name)
 original_lower = mod_name.lower()
 
 # 1. Exact match in component list (highest priority)
 if original_lower in _component_to_category:
 category = _component_to_category[original_lower]
 return (category, 1.0) if return_confidence else category
 
 if normalized in _component_to_category:
 category = _component_to_category[normalized]
 return (category, 0.95) if return_confidence else category
 
 # 2. Use TRIE for fast keyword matching - O(k) instead of O(n*k)
 # This catches aftermarket brands and specific terms efficiently
 best_keyword_category = None
 best_keyword_score = 0.0
 
 # Use trie to find all keyword matches in the text
 trie_match = _keyword_trie.find_best_match(original_lower, min_keyword_len=5)
 if trie_match:
 best_keyword_category, matched_keyword, best_keyword_score = trie_match
 
 # Also check normalized text
 trie_match_norm = _keyword_trie.find_best_match(normalized, min_keyword_len=5)
 if trie_match_norm and trie_match_norm[2] > best_keyword_score:
 best_keyword_category, matched_keyword, best_keyword_score = trie_match_norm
 
 # If we found a high-confidence keyword match, use it
 if best_keyword_score >= 0.5 and best_keyword_category:
 return (best_keyword_category, best_keyword_score) if return_confidence else best_keyword_category
 
 # 3. Fuzzy match against component names
 best_component_match = None
 best_component_score = 0.0
 best_component_category = None
 
 for component, category in _component_to_category.items():
 score = _fuzzy_match(normalized, component)
 if score > best_component_score:
 best_component_score = score
 best_component_match = component
 best_component_category = category
 
 # High confidence fuzzy match from component list
 if best_component_score >= 0.8:
 return (best_component_category, best_component_score) if return_confidence else best_component_category
 
 # 4. Trie already searched all keywords, but do word matching as fallback
 # for multi-word phrases that might not be exact substring matches
 if best_keyword_score < 0.4:
 for category, keywords in _category_keywords.items():
 match, score = _word_match(normalized, keywords)
 if score > best_keyword_score:
 best_keyword_score = score
 best_keyword_category = category
 match, score = _word_match(original_lower, keywords)
 if score > best_keyword_score:
 best_keyword_score = score
 best_keyword_category = category
 
 # 5. Choose best result - prefer keyword matches for aftermarket parts
 if best_keyword_score >= 0.4:
 category = best_keyword_category
 confidence = best_keyword_score
 elif best_component_score >= 0.5:
 category = best_component_category
 confidence = best_component_score
 elif best_keyword_score >= 0.25:
 category = best_keyword_category
 confidence = best_keyword_score
 else:
 category = "Other"
 confidence = 0.0
 
 return (category, confidence) if return_confidence else category


def detect_categories_batch(mods: List[str]) -> List[Tuple[str, str, float]]:
 """
 Detect categories for a batch of modifications.
 
 Args:
 mods: List of modification names
 
 Returns:
 List of (mod_name, category, confidence) tuples
 """
 results = []
 for mod in mods:
 category, confidence = detect_category(mod, return_confidence=True)
 results.append((mod, category, confidence))
 return results


def get_all_categories() -> List[str]:
 """Get all available categories."""
 _initialize()
 categories = set(_component_to_category.values())
 categories.update(_category_keywords.keys())
 return sorted(categories)


def get_components_for_category(category: str) -> List[str]:
 """Get all known components for a category."""
 _initialize()
 with open(COMPONENTS_FILE, "r") as f:
 data = json.load(f)
 return data.get(category, [])


def _run_tests():
 """Run test cases."""
 test_cases = [
 # Exact matches
 ("Control Arm", "Suspension"),
 ("Input Shaft Repair Sleeve", "Transmission-Manual"),
 ("Window Regulator", "Interior"),
 ("Brake Pad", "Brake & Wheel Hub"),
 ("Radiator", "Cooling System"),
 
 # Fuzzy matches (aftermarket parts)
 ("KW Coilovers", "Suspension"),
 ("Bilstein Shocks", "Suspension"),
 ("Eibach Springs", "Suspension"),
 ("Brembo Calipers", "Brake & Wheel Hub"),
 ("Borla Exhaust", "Exhaust & Emission"),
 ("K&N Air Filter", "Fuel & Air"),
 ("HKS Turbo Kit", "Forced Induction"),
 ("Garrett GT3076R Turbo", "Forced Induction"),
 ("ACT Clutch Kit", "Transmission-Manual"),
 ("Mishimoto Radiator", "Cooling System"),
 ("Work Wheels", "Wheel"),
 ("Recaro Seats", "Interior"),
 ("Sparco Harness", "Safety"),
 
 # Brand-specific JDM
 ("Trust/GReddy Intercooler", "Forced Induction"),
 ("Tomei Cams", "Engine"),
 ("Cusco Sway Bar", "Suspension"),
 ("Tein Coilovers", "Suspension"),
 
 # Overland/Truck
 ("ARB Front Bumper", "Body & Lamp Assembly"),
 ("Icon Stage 7 Suspension", "Suspension"),
 ("Rigid Light Bar", "Lighting"),
 ("Warn Winch", "Recovery"),
 ("CBI Rock Sliders", "Armor/Protection"),
 ("Prinsu Roof Rack", "Storage"),
 
 # Complex names
 ("BC Racing BR Series Coilovers", "Suspension"),
 ("Injen Cold Air Intake System", "Fuel & Air"),
 ("StopTech Big Brake Kit", "Brake & Wheel Hub"),
 ("Motul 300V Racing Oil", "Oil"),
 ]
 
 print("=" * 70)
 print("Category Detector Test Results")
 print("=" * 70)
 
 passed = 0
 failed = 0
 
 for mod_name, expected in test_cases:
 result, confidence = detect_category(mod_name, return_confidence=True)
 status = ""if result == expected else ""if result == expected:
 passed += 1
 print(f"{status} '{mod_name}' → {result} ({confidence:.2f})")
 else:
 failed += 1
 print(f"{status} '{mod_name}' → {result} ({confidence:.2f}) [expected: {expected}]")
 
 print("=" * 70)
 print(f"Results: {passed}/{passed+failed} passed ({100*passed/(passed+failed):.1f}%)")
 print("=" * 70)
 
 return failed == 0


if __name__ == "__main__":
 if len(sys.argv) < 2:
 print(__doc__)
 sys.exit(1)
 
 if sys.argv[1] == "--test":
 success = _run_tests()
 sys.exit(0 if success else 1)
 
 elif sys.argv[1] == "--batch":
 if len(sys.argv) < 3:
 print("Usage: python category_detector.py --batch <file>")
 sys.exit(1)
 
 with open(sys.argv[2], "r") as f:
 mods = [line.strip() for line in f if line.strip()]
 
 results = detect_categories_batch(mods)
 for mod, category, confidence in results:
 print(f"{category}\t{confidence:.2f}\t{mod}")
 
 elif sys.argv[1] == "--list-categories":
 categories = get_all_categories()
 for cat in categories:
 print(cat)
 
 elif sys.argv[1] == "--json":
 # Output as JSON for piping to other tools
 mod_name = " ".join(sys.argv[2:])
 category, confidence = detect_category(mod_name, return_confidence=True)
 print(json.dumps({
 "input": mod_name,
 "category": category,
 "confidence": round(confidence, 3)
 }))
 
 else:
 # Single modification lookup
 mod_name = " ".join(sys.argv[1:])
 category, confidence = detect_category(mod_name, return_confidence=True)
 print(f"Input: {mod_name}")
 print(f"Category: {category}")
 print(f"Confidence: {confidence:.1%}")

