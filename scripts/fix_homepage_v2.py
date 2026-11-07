import re

# Read the current file
with open('frontend/src/pages/HomePage.jsx', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace hero-learning with hero-guide (my version)
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
            </aside>'''

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
            </aside>'''

if old_hero in content:
    content = content.replace(old_hero, new_hero)
    print("Replaced hero-learning with hero-guide")
else:
    print("Could not find exact hero-learning block")

# Also fix the hero headline to use the split version
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

if old_h1 in content:
    content = content.replace(old_h1, new_h1)
    print("Replaced simple h1 with split version")
else:
    print("Could not find exact h1 block")

# Add HERO_HEADLINE_WORDS back at the top
# Find the imports section and add after imports
hero_words = "const HERO_HEADLINE_WORDS = 'Scholarships you can actually apply for.'.split(' ')\n\n"
if 'HERO_HEADLINE_WORDS' not in content:
    # Add after imports, before EUROPE_COUNTRIES
    content = content.replace(
        "const EUROPE_COUNTRIES = ['Germany'",
        hero_words + "const EUROPE_COUNTRIES = ['Germany'"
    )
    print("Added HERO_HEADLINE_WORDS")

# Write back
with open('frontend/src/pages/HomePage.jsx', 'w', encoding='utf-8') as f:
    f.write(content)
print("Done")