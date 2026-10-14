import sys
from pathlib import Path

backend_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(backend_dir))

from app.services.scholarship_image_verifier import is_official_domain, extract_domain

tests = [
    "www2.daad.de",
    "aefe.gouv.fr",
    "www.humboldt-foundation.de",
    "marie-sklodowska-curie-actions.ec.europa.eu",
    "erasmus-plus.ec.europa.eu",
    "campusfrance.org",
    "jasso.go.jp",
]

for domain in tests:
    result = is_official_domain(domain)
    print(f"is_official_domain('{domain}') = {result}")
