import re

# Read the fresh master file
with open('frontend/src/pages/HomePage.jsx.master3', 'r', encoding='utf-8') as f:
    content = f.read()

print("Applying fixes...")

# 1. Remove FLAGSHIP_PROGRAMMES block
pattern = r'const FLAGSHIP_PROGRAMMES = \[.*?\]\n\nconst FUNDING_MATRIX = \['
replacement = '// FLAGSHIP_PROGRAMMES removed - using dynamic data from snapshot instead\n\nconst FUNDING_MATRIX = ['
content = re.sub(pattern, replacement, content, flags=re.DOTALL)
print("Removed FLAGSHIP_PROGRAMMES block")

# 2. Remove HERO_HEADLINE_WORDS if defined (it's not in master, but just in case)
content = re.sub(r'const HERO_HEADLINE_WORDS = .*?\n', '', content)

# 3. Add HERO_HEADLINE_WORDS after imports
hero_words = "const HERO_HEADLINE_WORDS = 'Scholarships you can actually apply for.'.split(' ')\n\n"
content = content.replace(
    "const EUROPE_COUNTRIES = ['Germany'",
    "const HERO_HEADLINE_WORDS = 'Scholarships you can actually apply for.'.split(' ')\n\nconst EUROPE_COUNTRIES = ['Germany'"
)
print("Added HERO_HEADLINE_WORDS")

# 3. Replace h1 to use HERO_HEADLINE_WORDS
old_h1 = '<h1>Scholarships you can actually apply for.</h1>'
new_h1 = '''<h1>
                {HERO_HEADLINE_WORDS.map((word, i) => (
                  <Fragment key={`${word}-${i}`}>
                    <span
                      className={`w ${word.toLowerCase() === 'actually' ? 'it' : ''}`}
                      style={{ '--i': i }}
                    >
                      {word}
                    </span>
                    {i < HERO_HEADLINE_WORDS.length - 1 ? ' ' : null}
                  </Fragment>
                ))}
              </h1>
              <p className="bn-copy hero-bengali" lang="bn">
                আপনার যোগ্যতা, লক্ষ্য ও সময়সীমার সঙ্গে মানানসই বৃত্তি খুঁজুন।
              </p>'''
content = content.replace(old_h1, new_h1)
print("Replaced h1")

# 4. Replace hero-learning with hero-guide
old_hero = '''            <aside className="hero-learning" aria-labelledby="hero-learning-title">
              <p className="hero-learning__eyebrow">A simple way to shortlist</p>
              <h2 id="hero-learning-title">Read every opportunity with confidence.</h2>
              <p className="hero-learning__intro">
                Before you save a programme, check these three things on its official page.
              </p>
              <ol className="hero-learning__steps">
                <li>
                  <span aria-hidden="true">01</span>
                  <div>
                    <strong>Who can apply?</strong>
                    <p>Check citizenship, degree level and academic requirements.</p>
                  </div>
                </li>
                <li>
                  <span aria-hidden="true">02</span>
                  <div>
                    <strong>What does funding cover?</strong>
                    <p>Separate tuition, living costs, travel and insurance.</p>
                  </div>
                </li>
                <li>
                  <span aria-hidden="true">03</span>
                  <div>
                    <strong>When is the real deadline?</strong>
                    <p>A month-only date is not an exact day. Confirm it before planning.</p>
                  </div>
                </li>
              </ol>
              <a className="hero-learning__link" href="#learn">
                Learn how to compare awards <span aria-hidden="true">?</span>
              </a>
            </aside'''

new_hero = '''            <aside className="gl hero-guide" aria-labelledby="hero-guide-title">
              <div className="hero-guide__topline">
                <span>THE APPLICANT'S FIELD GUIDE</span>
                <span lang="bn">আবেদনের পথনির্দেশ</span>
              </div>
              <h2 id="hero-guide-title">A stronger application starts with three checks.</h2>
              <p className="bn-copy" lang="bn">
                ভালো আবেদনের শুরু—তিনটি বিষয় নিশ্চিত করা।
              </p>

              <ol className="hero-guide__steps">
                <li>
                  <span className="hero-guide__number">01</span>
                  <div>
                    <strong>Check your fit</strong>
                    <span lang="bn">যোগ্যতা ও পড়াশোনার স্তর মিলিয়ে নিন</span>
                  </div>
                  <span className="hero-guide__mark" aria-hidden="true">↗</span>
                </li>
                <li>
                  <span className="hero-guide__number">02</span>
                  <div>
                    <strong>Read the funding</strong>
                    <span lang="bn">টিউশন, থাকা ও যাতায়াত আলাদা করে দেখুন</span>
                  </div>
                  <span className="hero-guide__mark" aria-hidden="true">↗</span>
                </li>
                <li>
                  <span className="hero-guide__number">03</span>
                  <div>
                    <strong>Verify the deadline</strong>
                    <span lang="bn">আবেদনের আগে মূল ওয়েবসাইটে যাচাই করুন</span>
                  </div>
                  <span className="hero-guide__mark" aria-hidden="true">↗</span>
                </li>
              </ol>

              <div className="hero-guide__field-note">
                <span>FIELD NOTE <span lang="bn">/ মনে রাখুন</span></span>
                <p>“Fully funded” may not include flights or insurance.</p>
                <p className="bn-copy" lang="bn">“সম্পূর্ণ অর্থায়ন”-এ বিমানভাড়া বা বিমা নাও থাকতে পারে।</p>
              </div>
              <Link to="/scholarships" className="hero-guide__link">
                <span>Explore verified opportunities <small lang="bn">যাচাইকৃত সুযোগ দেখুন</small></span>
                <span aria-hidden="true">→</span>
              </Link>
            </aside'''

# Use regex with DOTALL for flexible whitespace
old_hero_flexible = r'''<aside className="hero-learning" aria-labelledby="hero-learning-title">\s*<p className="hero-learning__eyebrow">A simple way to shortlist</p>\s*<h2 id="hero-learning-title">Read every opportunity with confidence\.</h2>\s*<p className="hero-learning__intro">\s*Before you save a programme, check these three things on its official page\.\s*</p>\s*<ol className="hero-learning__steps">\s*<li>\s*<span aria-hidden="true">01</span>\s*<div>\s*<strong>Who can apply\?</strong>\s*<p>Check citizenship, degree level and academic requirements\.</p>\s*</div>\s*</li>\s*<li>\s*<span aria-hidden="true">02</span>\s*<div>\s*<strong>What does funding cover\?</strong>\s*<p>Separate tuition, living costs, travel and insurance\.</p>\s*</div>\s*</li>\s*<li>\s*<span aria-hidden="true">03</span>\s*<div>\s*<strong>When is the real deadline\?</strong>\s*<p>A month-only date is not an exact day\. Confirm it before planning\.</p>\s*</div>\s*</li>\s*</ol>\s*<a className="hero-learning__link" href="#learn">\s*Learn how to compare awards <span aria-hidden="true">\?</span>\s*</a>\s*</aside>'''

new_hero_guide = '''            <aside className="gl hero-guide" aria-labelledby="hero-guide-title">
              <div className="hero-guide__topline">
                <span>THE APPLICANT'S FIELD GUIDE</span>
                <span lang="bn">আবেদনের পথনির্দেশ</span>
              </div>
              <h2 id="hero-guide-title">A stronger application starts with three checks.</h2>
              <p className="bn-copy" lang="bn">
                ভালো আবেদনের শুরু—তিনটি বিষয় নিশ্চিত করা।
              </p>

              <ol className="hero-guide__steps">
                <li>
                  <span className="hero-guide__number">01</span>
                  <div>
                    <strong>Check your fit</strong>
                    <span lang="bn">যোগ্যতা ও পড়াশোনার স্তর মিলিয়ে নিন</span>
                  </div>
                  <span className="hero-guide__mark" aria-hidden="true">↗</span>
                </li>
                <li>
                  <span className="hero-guide__number">02</span>
                  <div>
                    <strong>Read the funding</strong>
                    <span lang="bn">টিউশন, থাকা ও যাতায়াত আলাদা করে দেখুন</span>
                  </div>
                  <span className="hero-guide__mark" aria-hidden="true">↗</span>
                </li>
                <li>
                  <span className="hero-guide__number">03</span>
                  <div>
                    <strong>Verify the deadline</strong>
                    <span lang="bn">আবেদনের আগে মূল ওয়েবসাইটে যাচাই করুন</span>
                  </div>
                  <span className="hero-guide__mark" aria-hidden="true">↗</span>
                </li>
              </ol>

              <div className="hero-guide__field-note">
                <span>FIELD NOTE <span lang="bn">/ মনে রাখুন</span></span>
                <p>“Fully funded” may not include flights or insurance.</p>
                <p className="bn-copy" lang="bn">“সম্পূর্ণ অর্থায়ন”-এ বিমানভাড়া বা বিমা নাও থাকতে পারে।</p>
              </div>
              <Link to="/scholarships" className="hero-guide__link">
                <span>Explore verified opportunities <small lang="bn">যাচাইকৃত সুযোগ দেখুন</small></span>
                <span aria-hidden="true">→</span>
              </Link>
            </aside'''

import re
content = re.sub(
    r'<aside className="hero-learning" aria-labelledby="hero-learning-title">\s*<p className="hero-learning__eyebrow">A simple way to shortlist</p>\s*<h2 id="hero-learning-title">Read every opportunity with confidence\.</h2>\s*<p className="hero-learning__intro">\s*Before you save a programme, check these three things on its official page\.\s*</p>\s*<ol className="hero-learning__steps">\s*<li>\s*<span aria-hidden="true">01</span>\s*<div>\s*<strong>Who can apply\?</strong>\s*<p>Check citizenship, degree level and academic requirements\.</p>\s*</div>\s*</li>\s*<li>\s*<span aria-hidden="true">02</span>\s*<div>\s*<strong>What does funding cover\?</strong>\s*<p>Separate tuition, living costs, travel and insurance\.</p>\s*</div>\s*</li>\s*<li>\s*<span aria-hidden="true">03</span>\s*<div>\s*<strong>When is the real deadline\?</strong>\s*<p>A month-only date is not an exact day\. Confirm it before planning\.</p>\s*</div>\s*</li>\s*</ol>\s*<a className="hero-learning__link" href="#learn">\s*Learn how to compare awards <span aria-hidden="true">\?</span>\s*</a>\s*</aside>',
    new_hero_guide,
    content,
    flags=re.DOTALL
)
print("Replaced hero-learning with hero-guide")

# 5. Replace allScholarships block
old_all = r'''// Combine flagship scholarships with directory for maximum data richness\s*const allScholarships = useMemo\(\(\) => \{\s*const flagTitles = new Set\(FLAGSHIP_PROGRAMMES\.map\(\(f\) => f\.title\.toLowerCase\(\)\)\)\s*const extra = \(directoryScholarships \|\| \[\]\)\s*\.filter\(\(s\) => !flagTitles\.has\(\(s\.title \|\| ''\)\.toLowerCase\(\)\)\)\s*\.slice\(0, 48\) // Rich batch from the 725\+ catalogue\s*\.map\(\(s\) => \(\{\s*id: s\.id,\s*title: s\.title,\s*country: s\.country,\s*degree: s\.degree \|\| "Master's, PhD",\s*funding: s\.funding \|\| \(s\.fully_funded \? 'Fully Funded' : 'Partial'\),\s*levels: s\.degree \? \[s\.degree\] : \["Master's"\],\s*isFull: s\.funding === 'Fully Funded' \|\| !!s\.fully_funded,\s*coverage: s\.description \|\| s\.benefits \|\| `Study opportunity in \$\{s\.country\}\. Check official website for detailed eligibility\.`,\s*officialUrl: s\.official_source_url \|\| s\.application_link,\s*provider: s\.provider \|\| `\$\{s\.country\} Education Board`,\s*verified: s\.verification_status === 'active',\s*image_url: s\.image_url,\s*image_source_url: s\.image_source_url,\s*image_source_type: s\.image_source_type,\s*image_kind: s\.image_kind,\s*image_verified_at: s\.image_verified_at,\s*image_alt_text: s\.image_alt_text,\s*\}\)\s*return \[\.\.\.FLAGSHIP_PROGRAMMES, \.\.\.extra\]\s*\}, \[directoryScholarships\]\)'''

new_all = '''  // Use directory scholarships directly (no hardcoded flagship programmes)
  const allScholarships = useMemo(() => {
    const extra = (directoryScholarships || [])
      .slice(0, 48) // Rich batch from the 725+ catalogue
      .map((s) => ({
        id: s.id,
        title: s.title,
        country: s.country,
        degree: s.degree || "Master's, PhD",
        funding: s.funding || (s.fully_funded ? 'Fully Funded' : 'Partial'),
        levels: s.degree ? [s.degree] : ["Master's"],
        isFull: s.funding === 'Fully Funded' || !!s.fully_funded,
        coverage: s.description || s.benefits || `Study opportunity in ${s.country}. Check official website for detailed eligibility.`,
        officialUrl: s.official_source_url || s.application_link,
        provider: s.provider || `${s.country} Education Board`,
        verified: s.verification_status === 'active',
        image_url: s.image_url,
        image_source_url: s.image_source_url,
        image_source_type: s.image_source_type,
        image_kind: s.image_kind,
        image_verified_at: s.image_verified_at,
        image_alt_text: s.image_alt_text,
      }))
    return extra
  }, [directoryScholarships])'''

content = re.sub(
    r'// Combine flagship scholarships with directory for maximum data richness\s*const allScholarships = useMemo\(\(\) => \{\s*const flagTitles = new Set\(FLAGSHIP_PROGRAMMES\.map\(\(f\) => f\.title\.toLowerCase\(\)\)\)\s*const extra = \(directoryScholarships \|\| \[\]\)\s*\.filter\(\(s\) => !flagTitles\.has\(\(s\.title \|\| ''\)\.toLowerCase\(\)\)\)\s*\.slice\(0, 48\) // Rich batch from the 725\+ catalogue\s*\.map\(\(s\) => \(\{\s*id: s\.id,\s*title: s\.title,\s*country: s\.country,\s*degree: s\.degree \|\| "Master\'s, PhD",\s*funding: s\.funding \|\| \(s\.fully_funded \? \'Fully Funded\' : \'Partial\'\),\s*levels: s\.degree \? \[s\.degree\] : \["Master\'s"\],\s*isFull: s\.funding === \'Fully Funded\' \|\| !!s\.fully_funded,\s*coverage: s\.description \|\| s\.benefits \|\| `Study opportunity in \$\{s\.country\}\. Check official website for detailed eligibility\.`,\s*officialUrl: s\.official_source_url \|\| s\.application_link,\s*provider: s\.provider \|\| `\$\{s\.country\} Education Board`,\s*verified: s\.verification_status === \'active\',\s*image_url: s\.image_url,\s*image_source_url: s\.image_source_url,\s*image_source_type: s\.image_source_type,\s*image_kind: s\.image_kind,\s*image_verified_at: s\.image_verified_at,\s*image_alt_text: s\.image_alt_text,\s*\}\)\s*return \[\.\.\.FLAGSHIP_PROGRAMMES, \.\.\.extra\]\s*\}, \[directoryScholarships\]\)',
    new_all,
    content,
    flags=re.DOTALL
)
print("Replaced allScholarships block")

# Remove 3D tilt handlers
content = re.sub(r'// 3D Tilt for Hero Stack\s*const \[stackTilt, setStackTilt\] = useState\(\{ rx: 0, ry: 0 \}\)\s*', '', content)

# Remove marquee
content = re.sub(r'// Marquee Ticker\s*<div className="mq" aria-hidden="true">\s*<div>\s*<span>\{marqueeText\} \· </span>\s*<span>\{marqueeText\} \· </span>\s*</div>\s*</div>', '', content, flags=re.DOTALL)

# Remove marqueeText
content = re.sub(r'// Marquee string\s*const marqueeText = useMemo\(\(\) => \{\s*return allScholarships\.slice\(0, 10\)\.map\(\(s\) => s\.title\)\.join\(\' \· \'\)\s*\}, \[allScholarships\]\)\s*', '', content)

# Remove 3D tilt state
content = re.sub(r'// 3D Tilt for Hero Stack\s*const \[stackTilt, setStackTilt\] = useState\(\{ rx: 0, ry: 0 \}\)\s*', '', content)

# Remove 3D tilt handlers
content = re.sub(r'// 3D Tilt on hero stack\s*const handleStackPointerMove = \(e\) => \{\s*.*?\s*const handleStackPointerLeave = \(\) => \{\s*.*?\s*setStackTilt\(\{ rx: 0, ry: 0 \}\)\s*\}', '', content, flags=re.DOTALL)

# Remove marquee
content = re.sub(r'// Marquee Ticker\s*<div className="mq" aria-hidden="true">\s*<div>\s*<span>\{marqueeText\} \· </span>\s*<span>\{marqueeText\} \· </span>\s*</div>\s*</div>', '', content, flags=re.DOTALL)

# Remove marqueeText definition
content = re.sub(r'// Marquee string\s*const marqueeText = useMemo\(\(\) => \{\s*return allScholarships\.slice\(0, 10\)\.map\(\(s\) => s\.title\)\.join\(\' \· \'\)\s*\}, \[allScholarships\]\)\s*', '', content, flags=re.DOTALL)

# Write the result
with open('frontend/src/pages/HomePage.jsx', 'w', encoding='utf-8') as f:
    f.write(content)

print("Done!")