with open('.github/workflows/ci.yml', 'r') as f:
    content = f.read()
content = content.replace("os.environ['SCHOLARZONE_ENVIRONMENT'] = 'test'\nfrom app.database", "os.environ['SCHOLARZONE_ENVIRONMENT'] = 'test'\nfrom app.database")
with open('.github/workflows/ci.yml', 'w') as f:
    f.write(content)
print('Fixed')