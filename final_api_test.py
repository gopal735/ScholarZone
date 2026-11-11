import requests
import json

print("=== FINAL COMPREHENSIVE API TEST ===")
print()

# Test all verified_supervisors scholarships
for sid, name in [(14, "ETH Zurich"), (15, "EPFL"), (70, "Imperial College London")]:
    url = "http://localhost:8000/api/scholarships/{}/supervisors".format(sid)
    try:
        response = requests.get(url)
        print("Scholarship {} ({}): Status {}".format(sid, name, response.status_code))
        if response.status_code == 200:
            data = response.json()
            print("  Coverage: {}, Supervisors: {}, Official Contacts: {}".format(
                data['coverage']['coverage_status'], len(data['supervisors']), len(data.get('official_contacts', []))))
            if data.get('official_contacts'):
                for contact in data['official_contacts']:
                    print("  Contact: {} - {} - {}".format(
                        contact['institution_name'], contact['contact_type'], contact['official_email']))
        else:
            print("  Error: {}".format(response.text))
    except Exception as e:
        print("  Error: {}".format(e))
    print()

# Test search_pending scholarship
url = "http://localhost:8000/api/scholarships/1/supervisors"
try:
    response = requests.get(url)
    print("Scholarship 1 (Erasmus Mundus): Status {}".format(response.status_code))
    if response.status_code == 200:
        data = response.json()
        print("  Coverage: {}, Discovery pending: {}".format(
            data['coverage']['coverage_status'], data['coverage']['discovery_pending']))
except Exception as e:
    print("  Error: {}".format(e))
print()

# Test not_applicable scholarship
url = "http://localhost:8000/api/scholarships/100/supervisors"
try:
    response = requests.get(url)
    print("Scholarship 100: Status {}".format(response.status_code))
    if response.status_code == 200:
        data = response.json()
        print("  Coverage: {}".format(data['coverage']['coverage_status']))
except Exception as e:
    print("  Error: {}".format(e))
print()

# Test 404 for non-existent
url = "http://localhost:8000/api/scholarships/9999/supervisors"
try:
    response = requests.get(url)
    print("Scholarship 9999: Status {}".format(response.status_code))
except Exception as e:
    print("Scholarship 9999: Error {}".format(e))
print()

# Test research interest matching
print("=== RESEARCH INTEREST MATCHING ===")
url = "http://localhost:8000/api/scholarships/70/supervisors?interests=machine%20learning&interests=robotics"
try:
    response = requests.get(url)
    print("Imperial with ML/Robotics: Status {}".format(response.status_code))
    if response.status_code == 200:
        data = response.json()
        strong = [p for p in data['supervisors'] if p['research_alignment']['band'] == 'strong_research_alignment']
        print("  Strong matches: {}".format(len(strong)))
        for p in strong[:3]:
            print("    - {}: {}".format(p['name'], p['research_alignment']['explanation'][:80]))
except Exception as e:
    print("  Error: {}".format(e))
print()

# Test summary endpoint
print("=== SUMMARY ENDPOINT ===")
for sid, name in [(14, "ETH"), (15, "EPFL"), (70, "Imperial"), (1, "Erasmus")]:
    url = "http://localhost:8000/api/scholarships/{}/supervisor-summary".format(sid)
    try:
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            print("  {}: {} (verified: {})".format(name, data['coverage_status'], data['verified_supervisor_count']))
    except Exception as e:
        print("  {}: Error {}".format(name, e))

print()
print("=== ALL API TESTS COMPLETE ===")