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

# 3. Replace hero section (h1 and hero-learning)
# First, fix the h1 to use HERO_HEADLINE_WORDS
old_h1 = '''              <h1>Scholarships you can actually apply for.</h1>'''

new_h1 = '''              <h1>
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
                <p className="bn-copy" lang="bn">“সম্পূর্ণ অর্থায়ন”-এ বিমানভাড়া বা বিমা নাও থাকতে পারে。</p>
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
    print("Could not find hero-learning")

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
    print("Could not find allScholarships block")

# 6. Remove 3D tilt handlers
content = re.sub(r'// 3D Tilt on hero stack\s*const handleStackPointerMove = \(e\) => \{\s*.*?\s*const handleStackPointerLeave = \(\) => \{\s*.*?\s*setStackTilt\(\{ rx: 0, ry: 0 \}\)\s*\}', '', content, flags=re.DOTALL)

# Remove stackTilt state
content = re.sub(r'// 3D Tilt for Hero Stack\s*const \[stackTilt, setStackTilt\] = useState\(\{ rx: 0, ry: 0 \}\)\s*', '', content)

# Remove stack tilt div in JSX
content = re.sub(r'// 3D Paper Stack Graphic\s*<div className="gl" aria-hidden="true">\s*<div\s*className="stack"\s*onPointerMove=\{handleStackPointerMove\}\s*onPointerLeave=\{handleStackPointerLeave\}\s*style=\{\{.*?\}\}\s*>.*?</div>\s*</div>', '', content, flags=re.DOTALL)

# Remove marquee
content = re.sub(r'// Marquee Ticker\s*<div className="mq" aria-hidden="true">\s*<div>\s*<span>\{marqueeText\} \· </span>\s*<span>\{marqueeText\} \· </span>\s*</div>\s*</div>', '', content, flags=re.DOTALL)

# Remove marqueeText definition
content = re.sub(r'// Marquee string\s*const marqueeText = useMemo\(\(\) => \{\s*return allScholarships\.slice\(0, 10\)\.map\(\(s\) => s\.title\)\.join\(\x27 \· \x27\)\s*\}, \[allScholarships\]\)\s*', '', content)

# Add HERO_HEADLINE_WORDS after imports
hero_words = "const HERO_HEADLINE_WORDS = 'Scholarships you can actually apply for.'.split(' ')\n\n"
content = content.replace(
    "const EUROPE_COUNTRIES = ['Germany'",
    hero_words + "const EUROPE_COUNTRIES = ['Germany'"
)

# Add Bengali copy to various sections
bn_additions = [
    # Hero guide field note
    ('<p>Typical patterns only. Every programme sets its own rules.</p>', 
     '<p>Typical patterns only. Every programme sets its own rules.</p>\n              <p className="bn-copy" lang="bn">\n                প্রতিটি প্রোগ্রামের অর্থায়নের শর্ত আলাদা—আবেদনের আগে সব খরচ ও সুবিধা যাচাই করুন।\n              </p>'),
    
    # Timeline items
    ('<li>\n                  <span className="mo">18 to 12 months</span>\n                  Research programmes, check eligibility and shortlist 3 to 5.\n                </li>',
     '<li>\n                  <span className="mo">18 to 12 months</span>\n                  Research programmes, check eligibility and shortlist 3 to 5.\n                  <span className="bn-copy" lang="bn">প্রোগ্রাম খুঁজুন, যোগ্যতা যাচাই করুন, ৩–৫টি বেছে নিন।</span>\n                </li>'),
    
    ('<li>\n                  <span className="mo">12 to 9 months</span>\n                  Book your language test (IELTS / TOEFL) and start your statement of purpose.\n                </li>',
     '<li>\n                  <span className="mo">12 to 9 months</span>\n                  Book your language test (IELTS / TOEFL) and start your statement of purpose.\n                  <span className="bn-copy" lang="bn">ভাষা পরীক্ষার তারিখ নিন, উদ্দেশ্যপত্রের খসড়া শুরু করুন।</span>\n                </li>'),
    
    ('<li>\n                  <span className="mo">9 to 6 months</span>\n                  Ask referees early. Collect transcripts, degree certificates and attestations.\n                </li>',
     '<li>\n                  <span className="mo">9 to 6 months</span>\n                  Ask referees early. Collect transcripts, degree certificates and attestations.\n                  <span className="bn-copy" lang="bn">সুপারিশকারীদের জানান, নম্বরপত্র ও সনদ সংগ্রহ করুন।</span>\n                </li>'),
    
    ('<li>\n                  <span className="mo">6 to 3 months</span>\n                  Finish application forms and submit a few days before each deadline.\n                </li>',
     '<li>\n                  <span className="mo">6 to 3 months</span>\n                  Finish application forms and submit a few days before each deadline.\n                  <span className="bn-copy" lang="bn">ফর্ম শেষ করে সময়সীমার কয়েক দিন আগেই জমা দিন।</span>\n                </li>'),
    
    ('<li>\n                  <span className="mo">3 to 0 months</span>\n                  Prepare for interviews, embassy visa processing and flight bookings.\n                </li>',
     '<li>\n                  <span className="mo">3 to 0 months</span>\n                  Prepare for interviews, embassy visa processing and flight bookings.\n                  <span className="bn-copy" lang="bn">সাক্ষাৎকার, ভিসা ও যাত্রার প্রস্তুতি নিন।</span>\n                </li>'),
    
    # Glossary
    ('<div className="gch">\n                 {GLOSSARY.map((\[term\], idx) => (\n                   <button',
     '<div className="gch">\n                 <p className="bn-copy" lang="bn">শব্দে চাপ দিন—সহজ ব্যাখ্যা দেখুন।</p>\n                 {GLOSSARY.map(([term], idx) => (\n                   <button'),
    
    # Statement guide
    ('<div className="sg">\n             <article className="pp sp">\n               <div className="ftabs" role="tablist">',
     '<div className="sg">\n             <p className="bn-copy" lang="bn">নিজের অভিজ্ঞতা, লক্ষ্য ও প্রাসঙ্গিক অর্জনগুলো সত্যভাবে তুলে ধরুন।</p>\n             <article className="pp sp">\n               <div className="ftabs" role="tablist">'),
    
    # Documents
    ('<p className="cn2">Lists differ by programme. Use this as a starting point, then follow the official checklist.</p>',
     '<p className="cn2">Lists differ by programme. Use this as a starting point, then follow the official checklist.</p>\n          <p className="bn-copy" lang="bn">প্রোগ্রামভেদে তালিকা বদলায়—এটি দিয়ে শুরু করুন, পরে অফিসিয়াল তালিকা মিলিয়ে নিন।</p>'),
    
    # Mistakes
    ('<h3 className="h3s mh">Mistakes that cost applicants</h3>',
     '<h3 className="h3s mh">Mistakes that cost applicants</h3>\n          <p className="bn-copy" lang="bn">এই সাধারণ ভুলগুলো এড়িয়ে আবেদন আরও শক্ত করুন।</p>'),
    
    # Quiz
    ('<article className="pp qz" id="qz">\n             {quizIdx < QUIZ_QUESTIONS.length ? (\n               <>',
     '<article className="pp qz" id="qz">\n             <p className="bn-copy" lang="bn">কুইজে উত্তর দিয়ে নিজের প্রস্তুতি যাচাই করুন।</p>\n             {quizIdx < QUIZ_QUESTIONS.length ? (\n               <>'),
    
    # Steps section
    ('<Link to="/scholarships" className="step on step--link">\n               <span className="step-num">01 / Explore</span>',
     '<Link to="/scholarships" className="step on step--link">\n               <span className="step-num">01 / Explore</span>\n               <p className="bn-copy" lang="bn">ডিগ্রি, দেশ ও অর্থায়ন দিয়ে খুঁজুন; যোগ্যতা ও সময়সীমা মূল সাইটে মিলিয়ে নিন।</p>'),
    
    ('<Link to="/match" className="step on step--link">\n               <span className="step-num">02 / Match</span>',
     '<Link to="/match" className="step on step--link">\n               <span className="step-num">02 / Match</span>\n               <p className="bn-copy" lang="bn">প্রকাশিত শর্তের সঙ্গে CGPA, IELTS, নাগরিকত্ব ও পরিকল্পনা মিলিয়ে দেখুন।</p>'),
    
    ('<Link to="/mentor" className="step on step--link">\n               <span className="step-num">03 / Prepare</span>',
     '<Link to="/mentor" className="step on step--link">\n               <span className="step-num">03 / Prepare</span>\n               <p className="bn-copy" lang="bn">উদ্দেশ্যপত্র লিখুন, সম্ভাব্য সুপারভাইজারকে পাঠানোর ইমেইল গুছিয়ে নিন।</p>'),
    
    ('<Link to="/applications" className="step on step--link">\n               <span className="step-num">04 / Track</span>',
     '<Link to="/applications" className="step on step--link">\n               <span className="step-num">04 / Track</span>\n               <p className="bn-copy" lang="bn">কাগজপত্র, কাজের সময়সীমা ও আবেদনের অবস্থা এক জায়গায় রাখুন।</p>'),
    
    # End section
    ('<h2>Start with your profile or browse open scholarships.</h2>',
     '<h2>Start with your profile or browse open scholarships.</h2>\n          <p className="bn-copy" lang="bn">আপনার প্রোফাইল দিয়ে মিল খুঁজুন, অথবা খোলা বৃত্তিগুলো দেখুন।</p>'),
    
    # Footer
    ('<p>\n             Scholarship search, planning and application support, designed for students and researchers.\n           </p>',
     '<p>\n             Scholarship search, planning and application support, designed for students and researchers.\n           </p>\n           <p className="bn-copy" lang="bn">শিক্ষার্থী ও গবেষকদের জন্য বৃত্তি খোঁজা, পরিকল্পনা ও আবেদনের সহায়তা।</p>'),
]

for old, new in bn_additions:
    if old in content:
        content = content.replace(old, new)
    else:
        print(f"Could not find: {old[:50]}...")

# Write the result
with open('frontend/src/pages/HomePage.jsx', 'w', encoding='utf-8') as f:
    f.write(content)

print("Done!")