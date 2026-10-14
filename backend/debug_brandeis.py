"""Debug Brandeis wein.jpg through full validator with prints."""
import sys
import os
from pathlib import Path

backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

os.environ.setdefault("SCHOLARZONE_DATABASE_URL", "sqlite:///scholarzone.db")
os.environ.setdefault("SCHOLARZONE_ENVIRONMENT", "test")

from app.services.image_validator import ImageValidator
from app.services.image_discovery import ImageCandidate

url = "https://www.brandeis.edu/isso/images/programs/wien/wein.jpg"
page = "https://www.brandeis.edu/isso/images/programs/wien/"

candidate = ImageCandidate(
    image_url=url,
    page_url=page,
    discovery_method="manual",
    alt_text=None,
    html_context=None,
)

validator = ImageValidator(seen_images={}, timeout=30.0)

# Monkey-patch to add debug prints
original_check_reachability = validator._check_reachability
original_check_dimensions = validator._check_image_dimensions

def debug_reachability(result):
    print(f"  [DEBUG _check_reachability] Before: is_reachable={result.is_reachable}, http_status={result.http_status}, content_type={result.content_type}")
    res = original_check_reachability(result)
    print(f"  [DEBUG _check_reachability] After: is_reachable={res.is_reachable}, http_status={res.http_status}, content_type={res.content_type}")
    return res

def debug_dimensions(result):
    print(f"  [DEBUG _check_image_dimensions] Entering: is_reachable={result.is_reachable}, content_type={result.content_type}, is_svg={result.is_svg}")
    res = original_check_dimensions(result)
    print(f"  [DEBUG _check_image_dimensions] Exiting: is_valid_image={res.is_valid_image}, width={res.width}, height={res.height}, rejection_reasons={res.rejection_reasons}")
    return res

validator._check_reachability = debug_reachability
validator._check_image_dimensions = debug_dimensions

result = validator.validate_candidate(candidate)
print(f"\nFinal: status={result.status.value}, confidence={result.confidence}")
print(f"  rejection_reasons={result.rejection_reasons}")
print(f"  relevance_score={result.relevance_score}")
