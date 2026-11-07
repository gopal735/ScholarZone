with open('frontend/src/pages/HomePage.jsx', 'r', encoding='utf-8') as f:
    content = f.read()

# Check for marquee (should be removed)
if 'marqueeText' in content or 'className="mq"' in content:
    print('Marquee still present')
else:
    print('Marquee removed')

# Check for 3D tilt (should be removed)
if 'stackTilt' in content or 'handleStackPointerMove' in content:
    print('3D tilt still present')
else:
    print('3D tilt removed')