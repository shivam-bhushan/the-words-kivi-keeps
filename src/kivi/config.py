import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT_DIR = Path(__file__).resolve().parents[2]
DB_PATH = os.environ.get("KIVI_DB_PATH", str(ROOT_DIR / "kivi.db"))
LLM_MODEL = os.environ.get("KIVI_LLM_MODEL", "claude-sonnet-5")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")

# Promotion / confidence thresholds. Tuned against seed corpus in eval/.
CANDIDATE_CONFIDENCE = 0.2
PROMOTION_REPETITION_COUNT = 3          # consistent repeats needed to promote candidate -> active
PROMOTION_CONFIDENCE = 0.75
CORRECTION_CONFIDENCE = 0.95            # explicit correction confidence
APPLY_CONFIDENCE_THRESHOLD = 0.7        # minimum confidence to auto-apply at inference time
PHONETIC_MAX_EDIT_DISTANCE = 2          # surface-form edit distance allowed within a phonetic cluster
COMMON_WORD_ZIPF_THRESHOLD = 3.2        # wordfreq zipf score above which a token is "common English" -> needs correction signal, not just phonetic proximity.
                                        # 3.2 splits real words (kiwi 3.33, mango 3.56, restart 3.68) from names (arjun 3.03, aditya 2.98, priya 2.92).
CATEGORY_PROMOTION_COUNT = 2            # consistent LLM-inferred category guesses needed before trusting it (never overrides an explicit --category)
