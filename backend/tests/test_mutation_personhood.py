"""Mutation testing for the personhood gate.

This script verifies that the personhood gate is robust against various
mutations that could weaken it. Each mutation should be caught (rejected)
by the gate.
"""

import subprocess
import sys
import tempfile
import os

# Mutation tests - each mutation should be caught (rejected) by the gate
MUTATIONS = [
    # 1. Weaken word count to 2-6
    {
        "name": "weaken_word_count",
        "description": "Weaken word count check from 2-4 to 2-6",
        "code": """
def _looks_like_a_person_name_mutated(text):
    words = text.split()
    if not 2 <= len(words) <= 6:  # MUTATION: 2-6 instead of 2-4
        return False
    if any(any(c.isdigit() for c in w) for w in words):
        return False
    lowered = text.lower().strip(".,")
    if lowered in _PERSON_NAME_DENYLIST:
        return False
    if any(w in _NOT_A_NAME_WORDS for w in lowered.split()):
        return False
    return all(w[:1].isupper() or w.lower() in ("van","von","de","der","el","bin","da","la","del","di","du","dos","das") for w in words)
""",
    },

    # 2. Remove denylist check
    {
        "name": "remove_denylist",
        "description": "Remove the _PERSON_NAME_DENYLIST check",
        "code": """
def _looks_like_a_person_name_mutated(text):
    words = text.split()
    if not 2 <= len(words) <= 4:
        return False
    if any(any(c.isdigit() for c in w) for w in words):
        return False
    # MUTATION: Removed denylist check
    lowered = text.lower().strip(".,")
    if any(w in _NOT_A_NAME_WORDS for w in lowered.split()):
        return False
    return all(w[:1].isupper() or w.lower() in ("van","von","de","der","el","bin","da","la","del","di","du","dos","das") for w in words)
""",
    },

    # 3. Remove NOT_A_NAME_WORDS check
    {
        "name": "remove_not_a_name_words",
        "description": "Remove the _NOT_A_NAME_WORDS check",
        "code": """
def _looks_like_a_person_name_mutated(text):
    words = text.split()
    if not 2 <= len(words) <= 4:
        return False
    if any(any(c.isdigit() for c in w) for w in words):
        return False
    lowered = text.lower().strip(".,")
    if lowered in _PERSON_NAME_DENYLIST:
        return False
    # MUTATION: Removed _NOT_A_NAME_WORDS check
    return all(w[:1].isupper() or w.lower() in ("van","von","de","der","el","bin","da","la","del","di","du","dos","das") for w in words)
""",
    },

    # 4. Allow lowercase names
    {
        "name": "allow_lowercase",
        "description": "Allow lowercase names",
        "code": """
def _looks_like_a_person_name_mutated(text):
    words = text.split()
    if not 2 <= len(words) <= 4:
        return False
    if any(any(c.isdigit() for c in w) for w in words):
        return False
    lowered = text.lower().strip(".,")
    if lowered in _PERSON_NAME_DENYLIST:
        return False
    if any(w in _NOT_A_NAME_WORDS for w in lowered.split()):
        return False
    # MUTATION: Allow lowercase
    return all(w[:1].isupper() or w.lower() in ("van","von","de","der","el","bin","da","la","del","di","du","dos","das") or w.islower() for w in words)
""",
    },

    # 5. Allow digits in names
    {
        "name": "allow_digits",
        "description": "Allow digits in names",
        "code": """
def _looks_like_a_person_name_mutated(text):
    words = text.split()
    if not 2 <= len(words) <= 4:
        return False
    # MUTATION: Allow digits
    lowered = text.lower().strip(".,")
    if lowered in _PERSON_NAME_DENYLIST:
        return False
    if any(w in _NOT_A_NAME_WORDS for w in lowered.split()):
        return False
    return all(w[:1].isupper() or w.lower() in ("van","von","de","der","el","bin","da","la","del","di","du","dos","das") for w in words)
""",
    },
]


def run_mutation_test(mutation):
    """Run a single mutation test by creating a temporary module."""
    test_code = f'''
import sys
sys.path.insert(0, r"C:\\\\Users\\\\GopaL\\\\Desktop\\\\Projects folder\\\\ScholarZone\\\\backend")
import os
os.environ["SCHOLARZONE_ENVIRONMENT"] = "test"

from app.services.supervisor_discovery import (
    _looks_like_a_person_name,
    _PERSON_NAME_DENYLIST,
    _NOT_A_NAME_WORDS,
)

# Apply mutation
{mutation["code"]}

# Test cases that should be REJECTED by the original but might pass with mutation
test_cases = [
    ("read more", False),
    ("view more", False),
    ("apply now", False),
    ("click here", False),
    ("Academic Staff", False),
    ("Research Track", False),
    ("Teaching Track", False),
    ("Educational Development", False),
    ("Annual Review", False),
    ("Read More", False),
    ("View More", False),
    ("Apply Now", False),
    ("John2 Smith", False),
    ("John Smi2th", False),
    ("J0hn Smith", False),
    ("john smith", False),
    ("john Smith", False),
    ("John smith", False),
    ("John2 Smith", False),
    ("john smith", False),
    ("John Smith Williams Jones Brown", False),  # 5 words - should be rejected by original
    ("John Smith Williams Jones Brown Black", False),  # 6 words
    ("john smith", False),
    ("john Smith", False),
    ("John smith", False),
    ("john2 smith", False),
]

print(f"Testing mutation: {{mutation['name']}}")
print(f"Description: {{mutation['description']}}")
print()

all_caught = True
for text, should_accept in test_cases:
    result = _looks_like_a_person_name_mutated(text)
    if result != False:  # Should be False (rejected)
        print(f"  MUTATION CAUGHT: {{text!r}} -> {{result}} (expected False)")
        all_caught = False
    else:
        print(f"  OK: {{text!r}} -> {{result}}")

print()
if all_caught:
    print("RESULT: MUTATION SURVIVED (not caught) - FAIL")
    sys.exit(1)
else:
    print("RESULT: MUTATION CAUGHT - PASS")
    sys.exit(0)
'''

    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(test_code)
        temp_file = f.name

    try:
        result = subprocess.run([sys.executable, temp_file], capture_output=True, text=True, timeout=60)
        print(f"Mutation: {{mutation['name']}}")
        print(f"Description: {{mutation['description']}}")
        print(result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)
        return result.returncode == 0
    finally:
        os.unlink(temp_file)