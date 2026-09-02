import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import get_session_factory, init_database
from app.services.scholarship_verifier import verify_scholarship
import json

def run_verification(run_number):
    print("=" * 70)
    print(f"VERIFICATION RUN #{run_number} -- Stipendium Hungaricum (ID: 285)")
    print("=" * 70)

    init_database()
    SessionFactory = get_session_factory()

    with SessionFactory() as session:
        result = verify_scholarship(session, 285)

        if result is None:
            print("ERROR: Scholarship not found or URL invalid")
            return None

        print(f"\n1. Verification started: YES")
        print(f"2. Fetch status: {result.fetch_status}")
        print(f"3. Changed fields: {json.dumps(result.changed_fields, indent=4, default=str)}")
        print(f"4. Unchanged fields: {result.unchanged_fields}")
        print(f"5. Uncertain fields: {result.uncertain_fields}")
        print(f"6. Automatic update candidates: {result.automatic_update_candidates}")
        print(f"7. Verification status: {result.verification_status}")
        print(f"8. Warnings: {result.warnings}")

        if result.extraction_result:
            ext = result.extraction_result
            print(f"\n--- Extracted Fields ---")
            if isinstance(ext, dict):
                for field, value in ext.get('fields', ext).items():
                    print(f"  {field}: {str(value)[:100]}")
            else:
                for field, value in ext.fields.items():
                    conf = ext.field_confidence.get(field, "unknown")
                    print(f"  {field}: {str(value)[:100]} (confidence: {conf})")

        if result.changeset:
            print(f"\n--- Changeset ---")
            for change in result.changeset.changes:
                print(f"  {change.field}: {change.change_type.value}")
                print(f"    old: {str(change.old_value)[:80]}")
                print(f"    new: {str(change.new_value)[:80]}")
                print(f"    confidence: {change.confidence}, is_update_candidate: {change.is_update_candidate}")

        print(f"\n--- Evidence Summary ---")
        if result.evidence_collection:
            ec = result.evidence_collection
            print(f"  Evidence items: {len(ec.items)}")
            print(f"  High confidence: {len(ec.high_confidence_items)}")
            print(f"  Low confidence: {len(ec.low_confidence_items)}")
            for ev in ec.items:
                print(f"  {ev.field_name}: status={ev.status}, source_type={ev.source_type}, confidence={ev.confidence}")

        print(f"\n--- Confidence Assessment ---")
        if result.confidence_assessment:
            ca = result.confidence_assessment
            print(f"  Assessed at: {ca.assessed_at}")
            print(f"  Total field results: {len(ca.field_results)}")
            print(f"  Update candidates: {len(ca.update_candidates)}")
            print(f"  Has conflicts: {ca.has_conflicts}")
            for fc in ca.field_results:
                print(f"  {fc.field_name}: confidence={fc.confidence}, state={fc.verification_state}, update_candidate={fc.is_update_candidate}, authority={fc.authority_score}, quality={fc.quality_score}")

        return result

if __name__ == "__main__":
    run = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    run_verification(run)
