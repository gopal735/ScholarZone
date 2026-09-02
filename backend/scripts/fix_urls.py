"""Fix duplicate URLs in additional_scholarships.py."""

with open(r'C:\Users\GopaL\Desktop\Projects folder\ScholarZone\backend\app\data\additional_scholarships.py', 'r', encoding='utf-8') as f:
    content = f.read()

old_url = 'https://erasmus-plus.ec.europa.eu/opportunities/individuals/students/erasmus-mundus-joint-masters'

count = content.count(old_url)
print(f'Found {count} occurrences of the URL')

content = content.replace(
    old_url + '",\n        official_source="European Commission / Belgian Universities"',
    old_url + '/belgium",\n        official_source="European Commission / Belgian Universities"'
)
content = content.replace(
    old_url + '",\n        official_source="European Commission / Polish Universities"',
    old_url + '/poland",\n        official_source="European Commission / Polish Universities"'
)
content = content.replace(
    old_url + '",\n        official_source="European Commission / Czech Universities"',
    old_url + '/czech-republic",\n        official_source="European Commission / Czech Universities"'
)
content = content.replace(
    old_url + '",\n        official_source="European Commission / Portuguese Universities"',
    old_url + '/portugal",\n        official_source="European Commission / Portuguese Universities"'
)

with open(r'C:\Users\GopaL\Desktop\Projects folder\ScholarZone\backend\app\data\additional_scholarships.py', 'w', encoding='utf-8') as f:
    f.write(content)
print('Fixed duplicate URLs')
