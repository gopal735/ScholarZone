import re

# Read the master file
with open('frontend/src/pages/HomePage.jsx.master', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Remove HERO_HEADLINE_WORDS (we'll add it back in a different place)
content = re.sub(r'const HERO_HEADLINE_WORDS = .*?\n', '', content)

# 2. Remove FLAGSHIP_PROGRAMMES block
pattern = r'const FLAGSHIP_PROGRAMMES = \[.*?\]\n\nconst FUNDING_MATRIX = \['
replacement = '// FLAGSHIP_PROGRAMMES removed - using dynamic data from snapshot instead\n\nconst FUNDING_MATRIX = ['
content = re.sub(pattern, replacement, content, flags=re.DOTALL)
print("Removed FLAGSHIP_PROGRAMMES block")

# 3. Replace hero section (h1 and hero-learning)
# First, fix the h1 to use HERO_HEADLINE_WORDS
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
old_hero_learning = '''            <aside className="hero-learning" aria-labelledby="hero-learning-title">
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
            </aside>'''

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
            </aside>'''

if old_hero_learning in content:
    content = content.replace(old_hero_learning, new_hero_guide)
    print("Replaced hero-learning with hero-guide")
else:
    print("Could not find exact hero-learning block")
    # Try to find with more flexible matching
    idx = content.find('hero-learning" aria-labelledby="hero-learning-title">')
    if idx != -1:
        print("Found hero-learning at:", idx)
        # Extract the actual block
        end = content.find('</aside>', idx)
        if end != -1:
            actual = content[idx:end+8]
            print("Actual block:")
            print(actual[:500])

# 5. Replace allScholarships block
old_all_scholarships = '''  // Combine flagship scholarships with directory for maximum data richness
  const allScholarships = useMemo(() => {
    const flagTitles = new Set(FLAGSHIP_PROGRAMMES.map((f) => f.title.toLowerCase()))
    const extra = (directoryScholarships || [])
      .filter((s) => !flagTitles.has((s.title || '').toLowerCase()))
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
    return [...FLAGSHIP_PROGRAMMES, ...extra]
  }, [directoryScholarships])'''

new_all_scholarships = '''  // Use directory scholarships directly (no hardcoded flagship programmes)
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

if old_all_scholarships in content:
    content = content.replace(old_all_scholarships, new_all_scholarships)
    print("Replaced allScholarships block")
else:
    print("Could not find exact allScholarships block")
    # Find the actual block
    idx = content.find('// Combine flagship scholarships with directory for maximum data richness')
    if idx != -1:
        print("Found at:", idx)
        # Extract more context
        end = content.find('}, [directoryScholarships])', idx)
        if end != -1:
            actual = content[idx:end+30]
            print("Actual block:")
            print(actual[:800])

# 6. Remove 3D tilt handlers
content = re.sub(r'// 3D Tilt for Hero Stack\s*const \[stackTilt, setStackTilt\] = useState\(\{ rx: 0, ry: 0 \}\)\s*', '', content)

# 7. Add HERO_HEADLINE_WORDS after imports
hero_words = "const HERO_HEADLINE_WORDS = 'Scholarships you can actually apply for.'.split(' ')\n\n"
content = content.replace(
    "const EUROPE_COUNTRIES = ['Germany'",
    "const HERO_HEADLINE_WORDS = 'Scholarships you can actually apply for.'.split(' ')\n\nconst EUROPE_COUNTRIES = ['Germany'"
)

# Write the result
with open('frontend/src/pages/HomePage.jsx', 'w', encoding='utf-8') as f:
    f.write(content)

print("Done!")