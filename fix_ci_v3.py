import re

with open('.github/workflows/ci.yml', 'r') as f:
    content = f.read()

# Read the replacement from a file to avoid quoting issues
with open('schema_compat_job.yml', 'r') as f:
    replacement = f.read()

pattern = r'(  schema-compat:.*?)(?=\n  build-and-smoke:)'

new_content = re.sub(pattern, replacement, content, flags=re.DOTALL)

with open('.github/workflows/ci.yml', 'w') as f:
    f.write(new_content)

print('Fixed')