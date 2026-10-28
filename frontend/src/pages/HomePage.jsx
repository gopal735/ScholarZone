import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { useScholarshipDirectory } from '../hooks/useScholarshipDirectory'
import { useSavedScholarships } from '../hooks/useSavedScholarships'
import { getConfirmedOfficialLogo, getMonogramInitial } from '../utils/scholarshipLogos'
import './HomePage.css'

const SAMPLE_GOAL = "I'm from Bangladesh and want a fully funded Master's in Computer Science in Europe. I have IELTS 7."

const EUROPE_COUNTRIES = ['Germany', 'Europe', 'UK', 'United Kingdom', 'France', 'Sweden', 'Netherlands', 'Norway', 'Denmark', 'Finland', 'Austria', 'Belgium', 'Poland', 'Hungary', 'Czech Republic', 'Portugal', 'Spain', 'Italy', 'Switzerland', 'Ireland']

const FLAGSHIP_PROGRAMMES = [
  {
    id: 1001,
    title: 'MEXT Scholarship',
    country: 'Japan',
    degree: "Bachelor's, Master's, PhD",
    funding: 'Fully Funded',
    levels: ["Bachelor's", "Master's", 'PhD'],
    isFull: true,
    coverage: 'Tuition, monthly allowance (¥144,000+) and round-trip airfare from the Japanese government.',
    officialUrl: 'https://www.studyinjapan.go.jp/en/planning/scholarship/mext-scholarship/',
    provider: 'Ministry of Education, Culture, Sports, Science and Technology Japan',
    verified: true,
  },
  {
    id: 1002,
    title: 'DAAD Scholarship',
    country: 'Germany',
    degree: "Master's, PhD",
    funding: 'Stipend',
    levels: ["Master's", 'PhD'],
    isFull: false,
    coverage: 'Monthly stipend (€934–€1,300), health insurance and travel allowance for postgraduate study in Germany.',
    officialUrl: 'https://www.daad.de/en/study-and-research-in-germany/scholarships/',
    provider: 'German Academic Exchange Service (DAAD)',
    verified: true,
  },
  {
    id: 1003,
    title: 'Chevening Scholarship',
    country: 'UK',
    degree: "Master's",
    funding: 'Fully Funded',
    levels: ["Master's"],
    isFull: true,
    coverage: "One-year master's at any UK university with 100% tuition, monthly living costs and return flights covered.",
    officialUrl: 'https://www.chevening.org/',
    provider: 'UK Foreign, Commonwealth & Development Office',
    verified: true,
  },
  {
    id: 1004,
    title: 'Commonwealth Scholarship',
    country: 'UK',
    degree: "Master's, PhD",
    funding: 'Fully Funded',
    levels: ["Master's", 'PhD'],
    isFull: true,
    coverage: 'Full tuition, warm clothing allowance, monthly living stipend and return flights for developing Commonwealth nations.',
    officialUrl: 'https://cscuk.fcdo.gov.uk/apply/',
    provider: 'Commonwealth Scholarship Commission in the UK',
    verified: true,
  },
  {
    id: 1005,
    title: 'Australia Awards',
    country: 'Australia',
    degree: "Master's, PhD",
    funding: 'Fully Funded',
    levels: ["Master's", 'PhD'],
    isFull: true,
    coverage: 'Full tuition fees, return air travel, establishment allowance, and contribution to living expenses (CLE).',
    officialUrl: 'https://www.dfat.gov.au/people-to-people/australia-awards',
    provider: 'Department of Foreign Affairs and Trade (DFAT) Australia',
    verified: true,
  },
  {
    id: 1006,
    title: 'Fulbright Program',
    country: 'USA',
    degree: "Master's, PhD",
    funding: 'Fully Funded',
    levels: ["Master's", 'PhD'],
    isFull: true,
    coverage: 'Full tuition, monthly stipend, health insurance, and international travel for graduate study in the United States.',
    officialUrl: 'https://bd.usembassy.gov/education-culture/student-exchange-programs/fulbright-foreign-student-program/',
    provider: 'U.S. Department of State / US Embassy Dhaka',
    verified: true,
  },
  {
    id: 1007,
    title: 'Türkiye Burslari',
    country: 'Türkiye',
    degree: "Bachelor's, Master's, PhD",
    funding: 'Fully Funded',
    levels: ["Bachelor's", "Master's", 'PhD'],
    isFull: true,
    coverage: 'Full university tuition, free accommodation, monthly allowance, 1-year Turkish course and airfare.',
    officialUrl: 'https://www.turkiyeburslari.gov.tr/',
    provider: 'Presidency for Turks Abroad and Related Communities (YTB)',
    verified: true,
  },
  {
    id: 1008,
    title: 'Erasmus Mundus',
    country: 'Europe',
    degree: "Master's",
    funding: 'Fully Funded',
    levels: ["Master's"],
    isFull: true,
    coverage: "Joint master's degree across 2+ European countries with tuition waiver and €1,400 monthly living allowance.",
    officialUrl: 'https://erasmus-plus.ec.europa.eu/opportunities/opportunities-for-individuals/students/erasmus-mundus-joint-masters',
    provider: 'European Commission',
    verified: true,
  },
]

const FUNDING_MATRIX = [
  {
    title: 'Fully funded',
    scores: ['y', 'y', 's', 's'],
    summary: 'Usually the strongest offer: tuition and a living allowance are covered. Check flights and insurance one by one.',
  },
  {
    title: 'Partial funding',
    scores: ['s', 's', 'n', 'n'],
    summary: 'Covers part of the cost. Plan how you will pay the rest before you accept.',
  },
  {
    title: 'Tuition waiver',
    scores: ['y', 'n', 'n', 'n'],
    summary: 'You pay no tuition fees, but you still need money for living costs.',
  },
  {
    title: 'Stipend',
    scores: ['n', 'y', 'n', 'n'],
    summary: 'A regular allowance for living costs. Tuition may be separate.',
  },
]

const GLOSSARY = [
  ['SOP', 'Statement of purpose: a short essay on why you want this course and what you will do after it.'],
  ['LOR', 'Letter of recommendation: a letter from a teacher or supervisor who knows your work.'],
  ['IELTS / TOEFL', 'English tests that many universities and scholarships ask for. Accepted scores differ by programme.'],
  ['CGPA', 'Your cumulative grade point average. Some programmes set a minimum.'],
  ['Stipend', 'A regular allowance for living costs such as rent and food.'],
  ['Tuition waiver', 'The university does not charge you tuition fees. Living costs are separate.'],
  ['Merit-based', 'Awarded for achievements such as grades, research or leadership.'],
  ['Need-based', 'Awarded based on your family’s financial situation.'],
  ['Research proposal', 'A plan for the research you want to do, usually asked for in PhD applications.'],
  ['Fully funded', 'Usually tuition plus a living allowance. Travel and insurance vary.'],
]

const STATEMENT_SECTIONS = [
  {
    title: 'Opening',
    percent: 10,
    whatToWrite: 'Start with a specific moment or question that pushed you towards this field. One or two sentences, then link it to the course.',
    askYourself: 'What moment or problem made you decide to study this?',
    tooGeneral: 'I have always been passionate about computer science.',
    stronger: 'When our department lost a week of data to a power cut, I taught myself to build an automatic backup system.',
  },
  {
    title: 'Academic background',
    percent: 25,
    whatToWrite: 'Name the courses, projects and results that prepared you. Be specific and brief.',
    askYourself: 'Which project shows best what you can do?',
    tooGeneral: 'I studied hard and got good grades.',
    stronger: 'My thesis on rainfall prediction used three years of local data and beat the baseline model.',
  },
  {
    title: 'Experience',
    percent: 25,
    whatToWrite: 'Pick two experiences. Say what you did, what changed, and what you learned.',
    askYourself: 'What did you change or build, and what happened next?',
    tooGeneral: 'I joined many activities and internships.',
    stronger: 'In my internship I automated the weekly report, which saved the team two hours every week.',
  },
  {
    title: 'Why this programme',
    percent: 25,
    whatToWrite: 'Show that you know the programme: a course, a lab or a supervisor that fits your goals. Do not copy the website.',
    askYourself: 'What exactly here can you not get anywhere else?',
    tooGeneral: 'Your university is famous all over the world.',
    stronger: 'The environmental data module and the open sensor lab fit directly with my thesis work.',
  },
  {
    title: 'Future goals',
    percent: 15,
    whatToWrite: 'Say what you will do after the degree and how this scholarship helps. Keep it realistic.',
    askYourself: 'What will you do in the first two years after graduating?',
    tooGeneral: 'I want to change the world.',
    stronger: 'After my master’s I plan to join a national agency and build open flood-data tools for local councils.',
  },
]

const REQUIRED_DOCUMENTS = [
  ['Passport', 'Proves your identity and nationality.', 'Check that it stays valid well beyond your start date.'],
  ['Transcripts and certificates', 'Show your grades and degrees.', 'Some programmes ask for attested or certified copies.'],
  ['English test result', 'IELTS, TOEFL or an accepted alternative.', 'Scores often expire after two years, so time your test.'],
  ['Recommendation letters', 'Usually two, from people who know your work.', 'Ask early and share your CV and goals.'],
  ['Statement of purpose', 'Your main essay.', 'Tailor it to every programme.'],
  ['CV or resume', 'One or two clear pages.', 'Lead with education, projects and results.'],
  ['Research proposal', 'Asked for in many PhD applications.', 'Keep to one question, a method and a timeline.'],
  ['Health and police certificates', 'Sometimes asked at the visa stage.', 'Check the embassy list well before travel.'],
]

const QUIZ_QUESTIONS = [
  {
    q: 'A “tuition waiver” means…',
    opts: ['All your costs are paid.', 'You pay no tuition fees, but living costs are separate.', 'You receive a monthly allowance.'],
    correct: 1,
    tip: 'A waiver removes tuition fees only. You still need money for rent, food and travel.',
  },
  {
    q: 'When should you ask referees for recommendation letters?',
    opts: ['A week before the deadline.', 'Months ahead, with your CV and goals.', 'After you submit.'],
    correct: 1,
    tip: 'Good letters take time. Early requests also let you fix problems before the deadline.',
  },
  {
    q: 'What is the best way to use your statement of purpose?',
    opts: ['Send the same one everywhere.', 'Tailor the opening and the “why this programme” part each time.', 'List every award you have won.'],
    correct: 1,
    tip: 'Committees can spot a generic statement quickly. Tailoring shows real interest.',
  },
  {
    q: 'You found a scholarship you like. What comes first?',
    opts: ['Write the essay.', 'Read the eligibility rules on the official page.', 'Email the committee for a guarantee.'],
    correct: 1,
    tip: 'Eligibility decides whether you can apply at all, so check it before you spend time on documents.',
  },
]

const PREPARATION_TASKS = [
  'English test result (IELTS, TOEFL or accepted alternative)',
  'Academic transcripts and certificates',
  'Two recommendation letters',
  'Statement of purpose',
  'CV or resume',
  'Passport copy',
  'Research proposal (PhD only)',
  'Eligibility checked on the official website',
]

function flagFor(country) {
  const c = (country || '').toLowerCase()
  if (c.includes('japan')) return '🇯🇵'
  if (c.includes('german')) return '🇩🇪'
  if (c.includes('uk') || c.includes('britain') || c.includes('united kingdom')) return '🇬🇧'
  if (c.includes('australia')) return '🇦🇺'
  if (c.includes('usa') || c.includes('america') || c.includes('united states')) return '🇺🇸'
  if (c.includes('türk') || c.includes('turk')) return '🇹🇷'
  if (c.includes('europe') || c.includes('eu')) return '🇪🇺'
  if (c.includes('canada')) return '🇨🇦'
  if (c.includes('france')) return '🇫🇷'
  if (c.includes('korea')) return '🇰🇷'
  if (c.includes('sweden')) return '🇸🇪'
  if (c.includes('china')) return '🇨🇳'
  return ''
}

export default function HomePage() {
  const { scholarships: directoryScholarships } = useScholarshipDirectory()
  const { savedIds, toggleSaved } = useSavedScholarships()

  // Natural Language Goal State
  const [goalText, setGoalText] = useState(() => {
    try {
      return localStorage.getItem('sz-goal') || SAMPLE_GOAL
    } catch {
      return SAMPLE_GOAL
    }
  })

  // Parse natural language input
  const parseGoal = (text) => {
    const t = text.toLowerCase()
    const p = {}

    // Level
    if (/ph\.?d|doctor/.test(t)) p.lv = 'PhD'
    else if (/master|msc/.test(t)) p.lv = "Master's"
    else if (/bachelor|undergrad/.test(t)) p.lv = "Bachelor's"
    else p.lv = null

    // Funding
    p.full = /fully funded|full funding|full scholarship|full tuition|100%/.test(t) ? 1 : null

    // Region / Country
    const regions = [
      ['Europe', /europe/],
      ['Germany', /german/],
      ['UK', /\buk\b|britain|england|united kingdom/],
      ['Japan', /japan/],
      ['Australia', /australia/],
      ['USA', /\busa\b|america|united states/],
      ['Türkiye', /t[uü]rk/],
      ['Canada', /canada/],
    ]
    p.rg = null
    for (const [rName, rRegex] of regions) {
      if (rRegex.test(t)) {
        p.rg = rName
        break
      }
    }

    // IELTS
    const m = t.match(/ielts\s*(\d(\.\d)?)/)
    p.ielts = m ? m[1] : null

    return p
  }

  // Manual Filter Overrides
  const [manualLevel, setManualLevel] = useState('Any')
  const [manualFunding, setManualFunding] = useState('Any')
  const [selectedCountry, setSelectedCountry] = useState('Any')
  const [sortOption, setSortOption] = useState('fit')

  // UI Interactive States
  const [planDrawerOpen, setPlanDrawerOpen] = useState(false)
  const [selectedSheetItem, setSelectedSheetItem] = useState(null)
  const [toast, setToast] = useState({ show: false, message: '', undo: null })
  const [userPlans, setUserPlans] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem('sz-plan') || '{}')
    } catch {
      return {}
    }
  })

  // Interactive Learn Section States
  const [fundingTab, setFundingTab] = useState(0)
  const [glossaryIdx, setGlossaryIdx] = useState(0)
  const [statementTab, setStatementTab] = useState(0)
  const [quizIdx, setQuizIdx] = useState(0)
  const [quizScore, setQuizScore] = useState(0)
  const [selectedQuizOption, setSelectedQuizOption] = useState(null)
  const [quizFeedback, setQuizFeedback] = useState('')

  // 3D Tilt for Hero Stack
  const [stackTilt, setStackTilt] = useState({ rx: 0, ry: 0 })

  const [removedCriteria, setRemovedCriteria] = useState({})

  // Derived Parsed Filter Criteria
  const parsedCriteria = useMemo(() => {
    const p = parseGoal(goalText)
    return {
      lv: removedCriteria.lv ? null : p.lv,
      full: removedCriteria.full ? null : p.full,
      rg: removedCriteria.rg ? null : p.rg,
      ielts: removedCriteria.ielts ? null : p.ielts,
    }
  }, [goalText, removedCriteria])

  // Sync to local storage
  useEffect(() => {
    try {
      localStorage.setItem('sz-goal', goalText)
    } catch (e) {
      void e
    }
  }, [goalText])

  // Combine flagship scholarships with directory for maximum data richness
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
      }))
    return [...FLAGSHIP_PROGRAMMES, ...extra]
  }, [directoryScholarships])

  // Unique Countries List
  const countryOptions = useMemo(() => {
    const list = ['Any', 'Europe']
    allScholarships.forEach((s) => {
      if (s.country && !list.includes(s.country) && s.country !== 'Europe') {
        list.push(s.country)
      }
    })
    return list
  }, [allScholarships])

  // Filtered & Scored Scholarships
  const matchedScholarships = useMemo(() => {
    const checkCriterion = (d, key, criteria) => {
      if (key === 'lv') {
        const activeLv = manualLevel !== 'Any' ? manualLevel : criteria.lv
        if (!activeLv) return true
        return d.levels ? d.levels.some((l) => l.toLowerCase().includes(activeLv.toLowerCase())) : false
      }
      if (key === 'full') {
        const activeFull = manualFunding !== 'Any' ? manualFunding === 'Fully funded' : criteria.full === 1
        if (activeFull === null) return true
        return activeFull ? d.isFull : true
      }
      if (key === 'rg') {
        const activeRg = selectedCountry !== 'Any' ? selectedCountry : criteria.rg
        if (!activeRg) return true
        if (activeRg === 'Europe') return EUROPE_COUNTRIES.includes(d.country)
        return (d.country || '').toLowerCase() === activeRg.toLowerCase()
      }
      return true
    }

    const activeKeys = []
    if (manualLevel !== 'Any' || parsedCriteria.lv) activeKeys.push('lv')
    if (manualFunding !== 'Any' || parsedCriteria.full) activeKeys.push('full')
    if (selectedCountry !== 'Any' || parsedCriteria.rg) activeKeys.push('rg')

    return allScholarships
      .map((d) => {
        const matches = activeKeys.filter((k) => checkCriterion(d, k, parsedCriteria)).length
        const total = activeKeys.length || 1
        const percent = Math.round((matches / total) * 100)
        return {
          ...d,
          matchScore: matches,
          totalCriteria: total,
          matchPercent: activeKeys.length ? percent : 100,
        }
      })
      .filter((x) => activeKeys.length === 0 || x.matchScore > 0)
      .sort((a, b) => {
        if (sortOption === 'az') return a.title.localeCompare(b.title)
        return b.matchScore - a.matchScore
      })
  }, [allScholarships, manualLevel, manualFunding, selectedCountry, parsedCriteria, sortOption])

  // Saved plan count
  const savedCount = useMemo(() => {
    return allScholarships.filter((s) => savedIds.includes(s.id) || savedIds.includes(String(s.id))).length
  }, [allScholarships, savedIds])

  // Trigger Toast
  const triggerToast = (msg, undoCallback) => {
    setToast({ show: true, message: msg, undo: undoCallback })
    setTimeout(() => {
      setToast((prev) => ({ ...prev, show: false }))
    }, 3500)
  }

  // Save/Unsave Handler
  const handleToggleSave = (scholarship) => {
    const isCurrentlySaved = savedIds.includes(scholarship.id) || savedIds.includes(String(scholarship.id))
    toggleSaved(scholarship.id)
    triggerToast(
      isCurrentlySaved ? `Removed: ${scholarship.title}` : `Added to plan: ${scholarship.title}`,
      () => toggleSaved(scholarship.id)
    )
  }

  // Update Plan Checklist & Deadline
  const updatePlan = (id, updates) => {
    setUserPlans((prev) => {
      const next = { ...prev, [id]: { ...(prev[id] || {}), ...updates } }
      try {
        localStorage.setItem('sz-plan', JSON.stringify(next))
      } catch (e) {
        void e
      }
      return next
    })
  }

  // Calculate Days Left for a target deadline
  const getDaysLeft = (targetDate) => {
    if (!targetDate) return null
    const diff = new Date(targetDate + 'T00:00:00') - new Date(new Date().toDateString())
    return Math.ceil(diff / (1000 * 60 * 60 * 24))
  }

  // Keyboard shortcut: Press "/" to focus search box
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === '/' && document.activeElement.tagName !== 'TEXTAREA' && document.activeElement.tagName !== 'INPUT') {
        e.preventDefault()
        const textarea = document.getElementById('goal')
        if (textarea) {
          textarea.focus()
          textarea.scrollIntoView({ behavior: 'smooth', block: 'center' })
        }
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [])

  // 3D Tilt on hero stack
  const handleStackPointerMove = (e) => {
    const stack = e.currentTarget.getBoundingClientRect()
    const x = (e.clientX - (stack.left + stack.width / 2)) / stack.width
    const y = (e.clientY - (stack.top + stack.height / 2)) / stack.height
    setStackTilt({ rx: -y * 10, ry: x * 12 })
  }

  const handleStackPointerLeave = () => {
    setStackTilt({ rx: 0, ry: 0 })
  }

  // Marquee string
  const marqueeText = useMemo(() => {
    return allScholarships.slice(0, 10).map((s) => s.title).join('  ·  ')
  }, [allScholarships])

  return (
    <div className="sz-home-editorial">
      {/* ── 01. HERO SECTION ────────────────────────────────────────── */}
      <section id="top">
        <div className="wrap">
          <div className="hero2">
            <div className="hl">
              <p className="eb">
                <b>01</b>Scholarship finder for Bangladesh
              </p>
              <h1>
                {'Scholarships you can actually apply for.'.split(' ').map((word, i) => (
                  <span
                    key={i}
                    className={`w ${word.toLowerCase() === 'actually' ? 'it' : ''}`}
                    style={{ '--i': i }}
                  >
                    {word}{' '}
                  </span>
                ))}
              </h1>
              <p className="lead">
                Write your goal in one sentence. ScholarZone checks it against the catalogue and shows what fits.
              </p>

              {/* Natural Language Goal Panel */}
              <div className="panel">
                <label htmlFor="goal">Describe your goal</label>
                <textarea
                  id="goal"
                  value={goalText}
                  onChange={(e) => setGoalText(e.target.value)}
                  placeholder="I'm from Bangladesh and want a fully funded Master's in Computer Science in Europe. I have IELTS 7."
                />

                <div className="prow">
                  <button
                    className="btn"
                    type="button"
                    onClick={() => setRemovedCriteria({})}
                  >
                    Read my profile
                  </button>
                  <button
                    className="btn ghost"
                    type="button"
                    onClick={() => {
                      setGoalText('')
                      setRemovedCriteria({ lv: true, full: true, rg: true, ielts: true })
                    }}
                  >
                    Clear
                  </button>

                  {/* Dynamic Extracted Filter Chips */}
                  {parsedCriteria.lv && (
                    <button
                      type="button"
                      className="chip"
                      onClick={() => setRemovedCriteria((prev) => ({ ...prev, lv: true }))}
                    >
                      <b>Level</b> {parsedCriteria.lv} ✕
                    </button>
                  )}
                  {parsedCriteria.full && (
                    <button
                      type="button"
                      className="chip"
                      onClick={() => setRemovedCriteria((prev) => ({ ...prev, full: true }))}
                    >
                      <b>Funding</b> Fully funded ✕
                    </button>
                  )}
                  {parsedCriteria.rg && (
                    <button
                      type="button"
                      className="chip"
                      onClick={() => setRemovedCriteria((prev) => ({ ...prev, rg: true }))}
                    >
                      <b>Country</b> {parsedCriteria.rg} ✕
                    </button>
                  )}
                  {parsedCriteria.ielts && (
                    <button
                      type="button"
                      className="chip"
                      onClick={() => setRemovedCriteria((prev) => ({ ...prev, ielts: true }))}
                    >
                      <b>English test</b> IELTS {parsedCriteria.ielts} ✕
                    </button>
                  )}
                </div>

                <div className="ex">
                  <span>Try</span>
                  <button
                    type="button"
                    onClick={() => setGoalText("I want a fully funded Master's in Europe.")}
                  >
                    Master's in Europe
                  </button>
                  <button
                    type="button"
                    onClick={() => setGoalText('I want a fully funded PhD in Japan.')}
                  >
                    PhD in Japan
                  </button>
                  <button
                    type="button"
                    onClick={() => setGoalText("I want a Bachelor's degree in Türkiye.")}
                  >
                    Bachelor's in Türkiye
                  </button>
                </div>

                <p className="hint" role="status">
                  Results update as you type. Press <kbd>/</kbd> to focus the box.
                </p>
              </div>
            </div>

            {/* 3D Paper Stack Graphic */}
            <div className="gl" aria-hidden="true">
              <div
                className="stack"
                onPointerMove={handleStackPointerMove}
                onPointerLeave={handleStackPointerLeave}
                style={{
                  '--rx': `${stackTilt.rx.toFixed(2)}deg`,
                  '--ry': `${stackTilt.ry.toFixed(2)}deg`,
                }}
              >
                <i className="pen" aria-hidden="true">
                  <s className="pe" />
                  <s className="pf" />
                  <s className="pb" />
                  <s className="pw" />
                  <s className="pg-tip" />
                </i>

                {/* Sheet A: Routes from Dhaka */}
                <div className="sh a">
                  <svg className="rt" viewBox="0 0 600 520" role="img" aria-label="Routes from Dhaka to destinations">
                    <defs>
                      <mask id="m0">
                        <path className="mk" style={{ '--i': 0 }} pathLength="1" d="M190 320Q165 195 235 100" />
                      </mask>
                      <mask id="m1">
                        <path className="mk" style={{ '--i': 1 }} pathLength="1" d="M190 320Q225 185 310 92" />
                      </mask>
                      <mask id="m2">
                        <path className="mk" style={{ '--i': 2 }} pathLength="1" d="M190 320Q225 250 305 190" />
                      </mask>
                      <mask id="m3">
                        <path className="mk" style={{ '--i': 3 }} pathLength="1" d="M190 320Q345 235 505 215" />
                      </mask>
                      <mask id="m4">
                        <path className="mk" style={{ '--i': 4 }} pathLength="1" d="M190 320Q310 440 470 442" />
                      </mask>
                    </defs>
                    <path className="dots" mask="url(#m0)" d="M190 320Q165 195 235 100" />
                    <path className="dots" mask="url(#m1)" d="M190 320Q225 185 310 92" />
                    <path className="dots" mask="url(#m2)" d="M190 320Q225 250 305 190" />
                    <path className="dots" mask="url(#m3)" d="M190 320Q345 235 505 215" />
                    <path className="dots" mask="url(#m4)" d="M190 320Q310 440 470 442" />
                    <circle className="pin" cx="235" cy="100" r="7" />
                    <text className="pl" x="227" y="88" textAnchor="end">London</text>
                    <circle className="pin" cx="310" cy="92" r="7" />
                    <text className="pl" x="316" y="80" textAnchor="start">Berlin</text>
                    <circle className="pin" cx="305" cy="190" r="7" />
                    <text className="pl" x="315" y="194" textAnchor="start">Istanbul</text>
                    <circle className="pin" cx="505" cy="215" r="7" />
                    <text className="pl" x="499" y="201" textAnchor="end">Tokyo</text>
                    <circle className="pin" cx="470" cy="442" r="7" />
                    <text className="pl" x="478" y="458" textAnchor="start">Sydney</text>
                    <circle className="home" cx="190" cy="320" r="9" />
                    <text className="pl" style={{ fill: 'var(--ink)' }} x="190" y="352" textAnchor="middle">
                      Dhaka
                    </text>
                  </svg>
                </div>

                {/* Sheet B: Application Checklist */}
                <div className="sh b">
                  <i className="tp" />
                  <h4>My checklist</h4>
                  <ul>
                    <li>
                      <svg className="tk" viewBox="0 0 20 20">
                        <path d="M3 11 8 16 17 4" />
                      </svg>
                      IELTS result
                    </li>
                    <li>
                      <svg className="tk" viewBox="0 0 20 20">
                        <path d="M3 11 8 16 17 4" />
                      </svg>
                      Transcripts
                    </li>
                    <li>
                      <svg className="tk" viewBox="0 0 20 20">
                        <path d="M3 11 8 16 17 4" />
                      </svg>
                      Recommendations
                    </li>
                    <li>
                      <svg className="tk" viewBox="0 0 20 20">
                        <path d="M3 11 8 16 17 4" />
                      </svg>
                      Statement of purpose
                    </li>
                    <li>
                      <span className="tk o" />
                      Passport copy
                    </li>
                  </ul>
                </div>

                {/* Sheet C: Award Certificate */}
                <div className="sh c">
                  <div className="cb">
                    <small>SCHOLARSHIP AWARD</small>
                    <p className="nm">Your Name Here</p>
                    <span className="ul" />
                    <p className="ds">Your next chapter starts with one application.</p>
                  </div>
                  <div className="seal">
                    <b>SZ</b>
                  </div>
                  <div className="rib">
                    <s />
                    <s />
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* ── Refine Results Filters Bar ────────────────────────────── */}
          <div className="flt" id="flt" role="group" aria-label="Refine results">
            {/* Level Filter */}
            <div className="fg">
              <span className="fl">Level</span>
              <div className="seg" role="group" aria-label="Level">
                {['Any', "Bachelor's", "Master's", 'PhD'].map((lv) => (
                  <button
                    key={lv}
                    type="button"
                    aria-pressed={manualLevel === lv}
                    onClick={() => setManualLevel(lv)}
                  >
                    {lv}
                  </button>
                ))}
              </div>
            </div>

            {/* Funding Filter */}
            <div className="fg">
              <span className="fl">Funding</span>
              <div className="seg" role="group" aria-label="Funding">
                {['Any', 'Fully funded'].map((f) => (
                  <button
                    key={f}
                    type="button"
                    aria-pressed={manualFunding === f}
                    onClick={() => setManualFunding(f)}
                  >
                    {f}
                  </button>
                ))}
              </div>
            </div>

            {/* Country Selector */}
            <div className="fg">
              <span className="fl">Country</span>
              <select
                className="sel"
                id="ctry"
                value={selectedCountry}
                onChange={(e) => setSelectedCountry(e.target.value)}
                aria-label="Country"
              >
                {countryOptions.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>
            </div>

            <aside className="sticky-tip">
              <b>Tip</b>
              Shortlist 3 to 5 programmes. Different deadlines give you more than one chance.
            </aside>
          </div>

          {/* Results Bar */}
          <div className="bar">
            <strong id="cnt" aria-live="polite">
              {matchedScholarships.length} scholarships match{' '}
              {manualLevel !== 'Any' || manualFunding !== 'Any' || selectedCountry !== 'Any'
                ? 'selected filters'
                : 'criteria'}
            </strong>

            <div className="bar2">
              <label className="sort">
                Sort{' '}
                <select
                  className="sel"
                  id="sort"
                  value={sortOption}
                  onChange={(e) => setSortOption(e.target.value)}
                >
                  <option value="fit">Best match</option>
                  <option value="az">Name A to Z</option>
                </select>
              </label>

              {/* My Plan Dropdown Toggle */}
              <button
                className="pill"
                id="sv"
                type="button"
                aria-haspopup="true"
                aria-expanded={planDrawerOpen}
                onClick={() => setPlanDrawerOpen((o) => !o)}
              >
                My plan · {savedCount}
              </button>

              {/* Saved Plan Drawer */}
              {planDrawerOpen && (
                <div className="drawer" id="dr">
                  {savedCount > 0 ? (
                    <>
                      <p className="dt">My plan ({savedCount})</p>
                      {allScholarships
                        .filter((s) => savedIds.includes(s.id) || savedIds.includes(String(s.id)))
                        .map((s) => {
                          const plan = userPlans[s.id] || {}
                          const daysLeft = getDaysLeft(plan.deadline)
                          const readyCount = (plan.checkedTasks || []).length
                          return (
                            <div key={s.id} className="di">
                              <button
                                type="button"
                                className="dn"
                                onClick={() => {
                                  setPlanDrawerOpen(false)
                                  setSelectedSheetItem(s)
                                }}
                              >
                                <span>{s.title}</span>
                                <small>
                                  {readyCount}/8 ready
                                  {daysLeft !== null && ` · ${daysLeft < 0 ? 'deadline passed' : `${daysLeft} days left`}`}
                                </small>
                              </button>
                              <button
                                type="button"
                                data-remove="true"
                                onClick={() => handleToggleSave(s)}
                              >
                                Remove
                              </button>
                            </div>
                          )
                        })}
                    </>
                  ) : (
                    <>
                      <p className="dt">Your plan is empty</p>
                      <p className="dm">
                        Save a scholarship, then open Details to add your target deadline and checklist.
                      </p>
                    </>
                  )}
                </div>
              )}
            </div>
          </div>

          {/* ── Scholarship Cards Grid ───────────────────────────────── */}
          <div className="grid" id="res">
            {matchedScholarships.length === 0 ? (
              <p className="empty">
                Nothing fits this exact combination. Remove a tag above or reset filters to widen your search.
              </p>
            ) : (
              matchedScholarships.map((s, index) => {
                const isSaved = savedIds.includes(s.id) || savedIds.includes(String(s.id))
                const officialLogo = getConfirmedOfficialLogo(s)
                const monogramInitial = getMonogramInitial(s.title)

                return (
                  <article
                    key={s.id}
                    className={`sc ${s.matchPercent < 100 ? 'part' : ''}`}
                    style={{ '--n': index }}
                  >
                    <div className="top">
                      {/* Logo Box: Confirmed official provider logo if verified, or neutral monogram fallback */}
                      <div className="mono" aria-label={officialLogo ? `${s.title} official logo` : undefined}>
                        {officialLogo ? (
                          <img
                            src={officialLogo.url}
                            alt={officialLogo.altText}
                            className="sc-logo-img"
                            onError={(e) => {
                              e.currentTarget.style.display = 'none'
                              if (e.currentTarget.nextSibling) e.currentTarget.nextSibling.style.display = 'block'
                            }}
                          />
                        ) : null}
                        <span
                          className="sc-mono-letter"
                          style={{ display: officialLogo ? 'none' : 'block' }}
                        >
                          {monogramInitial}
                        </span>
                      </div>

                      <div style={{ flex: 1, minWidth: 0 }}>
                        <h3>{s.title}</h3>
                        <p className="w">
                          <span>{flagFor(s.country)}</span>
                          {s.country}
                        </p>
                      </div>

                      <button
                        type="button"
                        className="dtl"
                        onClick={() => setSelectedSheetItem(s)}
                      >
                        Details
                      </button>
                    </div>

                    <p className="cv">{s.coverage}</p>

                    <div className="tags">
                      <span className={s.isFull ? 'f' : ''}>{s.funding}</span>
                      {s.levels.map((lvl) => (
                        <span key={lvl}>{lvl}</span>
                      ))}
                    </div>

                    <div className="fit">
                      <span>
                        {s.totalCriteria > 1
                          ? `Matches ${s.matchScore} of ${s.totalCriteria}`
                          : 'All criteria'}
                      </span>
                      <i>
                        <s style={{ width: `${s.matchPercent}%` }} />
                      </i>
                      <button
                        type="button"
                        className="save"
                        aria-pressed={isSaved}
                        onClick={() => handleToggleSave(s)}
                      >
                        {isSaved ? 'Saved' : 'Save'}
                      </button>
                    </div>
                  </article>
                )
              })
            )}
          </div>

          <p className="hint" style={{ maxWidth: '75ch', marginTop: '24px' }}>
            Showing verified international programmes for students from Bangladesh. Always confirm specific degree prerequisites, deadlines and attested documents on each official page.
          </p>
        </div>
      </section>

      {/* ── Marquee Ticker ───────────────────────────────────────────── */}
      <div className="mq" aria-hidden="true">
        <div>
          <span>{marqueeText} · </span>
          <span>{marqueeText} · </span>
        </div>
      </div>

      {/* ── 02. TOOLKIT (Bento Grid) ─────────────────────────────────── */}
      <section id="tools">
        <div className="wrap">
          <p className="eb">
            <b>02</b>Toolkit
          </p>
          <h2>Everything after the search, in one place.</h2>
          <p className="lead">Compare, write and track without switching tools.</p>

          <div className="bento">
            <div className="tl t1">
              <h3>Match</h3>
              <p>Programmes ranked by how many of your criteria they meet.</p>
              <div className="mb">
                <span>Chevening</span>
                <i><s style={{ width: '100%' }} /></i>
                <em>3/3</em>
              </div>
              <div className="mb">
                <span>Erasmus Mundus</span>
                <i><s style={{ width: '100%' }} /></i>
                <em>3/3</em>
              </div>
              <div className="mb">
                <span>DAAD</span>
                <i><s style={{ width: '66%' }} /></i>
                <em>2/3</em>
              </div>
              <div className="mb">
                <span>MEXT</span>
                <i><s style={{ width: '66%' }} /></i>
                <em>2/3</em>
              </div>
              <div className="mb">
                <span>Fulbright</span>
                <i><s style={{ width: '66%' }} /></i>
                <em>2/3</em>
              </div>
              <div className="mb">
                <span>Türkiye</span>
                <i><s style={{ width: '66%' }} /></i>
                <em>2/3</em>
              </div>
            </div>

            <div className="tl t2">
              <h3>Compare</h3>
              <p>Side by side funding.</p>
              <div className="cols">
                <s style={{ height: '70%' }} />
                <s style={{ height: '100%' }} />
                <s style={{ height: '48%' }} />
              </div>
            </div>

            <div className="tl t3">
              <h3>Statement coach</h3>
              <p>Guidance per section.</p>
              <div className="sk" />
              <div className="sk" style={{ width: '80%' }} />
              <div className="sk" style={{ width: '55%' }} />
            </div>

            <div className="tl t4">
              <h3>Applications</h3>
              <p>Know where every application stands.</p>
              <div className="kb">
                <span>Saved · {savedCount}</span>
                <span>Writing · 2</span>
                <span className="g">Submitted · 1</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ── 03. LEARN SECTION ────────────────────────────────────────── */}
      <section id="learn">
        <div className="wrap">
          <p className="eb">
            <b>03</b>Learn
          </p>
          <h2>Scholarship basics, in plain words.</h2>
          <p className="lead">A few minutes here can save you months of guessing.</p>

          <div className="lg">
            {/* Funding Breakdown */}
            <article className="pp nb">
              <i className="tp" />
              <h3>
                What does <mark>“funded”</mark> actually cover?
              </h3>
              <div className="ftabs" role="tablist">
                {FUNDING_MATRIX.map((f, i) => (
                  <button
                    key={f.title}
                    type="button"
                    role="tab"
                    aria-selected={fundingTab === i}
                    onClick={() => setFundingTab(i)}
                  >
                    {f.title}
                  </button>
                ))}
              </div>

              <div className="cov">
                {['Tuition fees', 'Living costs', 'Flights', 'Health insurance'].map((rw, k) => {
                  const s = FUNDING_MATRIX[fundingTab].scores[k]
                  const label = s === 'y' ? 'usually' : s === 's' ? 'varies' : 'rarely'
                  return (
                    <div key={rw} className="cr">
                      <span className="ic" data-s={s} />
                      <span className="rn">{rw}</span>
                      <em>{label}</em>
                    </div>
                  )
                })}
              </div>

              <p className="cx">{FUNDING_MATRIX[fundingTab].summary}</p>
              <p className="cn">Typical patterns only. Every programme sets its own rules.</p>
            </article>

            {/* When to Start Timeline */}
            <article className="pp tm">
              <h3>
                When to <mark>start</mark>
              </h3>
              <p className="cn" style={{ margin: '4px 0 0' }}>
                Counting back from the start of your degree.
              </p>
              <ol>
                <li>
                  <span className="mo">18 to 12 months</span>
                  Research programmes, check eligibility and shortlist 3 to 5.
                </li>
                <li>
                  <span className="mo">12 to 9 months</span>
                  Book your language test (IELTS / TOEFL) and start your statement of purpose.
                </li>
                <li>
                  <span className="mo">9 to 6 months</span>
                  Ask referees early. Collect transcripts, degree certificates and attestations.
                </li>
                <li>
                  <span className="mo">6 to 3 months</span>
                  Finish application forms and submit a few days before each deadline.
                </li>
                <li>
                  <span className="mo">3 to 0 months</span>
                  Prepare for interviews, embassy visa processing and flight bookings.
                </li>
              </ol>
              <p className="cn">A typical plan. Deadlines differ, so always verify each official portal.</p>
            </article>
          </div>

          {/* Glossary */}
          <div className="gls">
            <div>
              <h3 className="h3s">Glossary</h3>
              <p className="cn2">Tap a term to see what it means.</p>
              <div className="gch">
                {GLOSSARY.map(([term], idx) => (
                  <button
                    key={term}
                    type="button"
                    aria-pressed={glossaryIdx === idx}
                    onClick={() => setGlossaryIdx(idx)}
                  >
                    {term}
                  </button>
                ))}
              </div>
            </div>

            <article className="pp def" aria-live="polite">
              <small>DEFINITION</small>
              <h4>{GLOSSARY[glossaryIdx][0]}</h4>
              <p>{GLOSSARY[glossaryIdx][1]}</p>
            </article>
          </div>

          {/* Statement Coach */}
          <h3 className="h3s mh">
            Write a statement that sounds like <mark>you</mark>
          </h3>
          <div className="sg">
            <article className="pp sp">
              <div className="ftabs" role="tablist">
                {STATEMENT_SECTIONS.map((sec, i) => (
                  <button
                    key={sec.title}
                    type="button"
                    role="tab"
                    aria-selected={statementTab === i}
                    onClick={() => setStatementTab(i)}
                  >
                    {sec.title}
                  </button>
                ))}
              </div>

              <div>
                <p className="sw">What to write</p>
                <p className="sx2">{STATEMENT_SECTIONS[statementTab].whatToWrite}</p>
                <p className="sw">Ask yourself</p>
                <p className="sq">{STATEMENT_SECTIONS[statementTab].askYourself}</p>
                <div className="pair">
                  <div className="wk">
                    <small>Too general</small>
                    <p>{STATEMENT_SECTIONS[statementTab].tooGeneral}</p>
                  </div>
                  <div className="sr">
                    <small>Stronger</small>
                    <p>{STATEMENT_SECTIONS[statementTab].stronger}</p>
                  </div>
                </div>
                <p className="cn">Examples are only illustrations. Write your own authentic journey.</p>
              </div>
            </article>

            <aside className="pp wb">
              <h4>Where the words go</h4>
              <div className="wbar">
                {STATEMENT_SECTIONS.map((sec, i) => (
                  <button
                    key={sec.title}
                    type="button"
                    className={`seg2 ${statementTab === i ? 'on' : ''}`}
                    style={{ flexGrow: sec.percent }}
                    aria-label={`${sec.title}, about ${sec.percent} percent`}
                    onClick={() => setStatementTab(i)}
                  >
                    <span>{sec.percent}%</span>
                  </button>
                ))}
              </div>
              <p className="cn">A rough guide for a 600 to 800 word statement. Always follow each programme’s own word limit.</p>
            </aside>
          </div>

          {/* Documents You Will Likely Need */}
          <h3 className="h3s mh">
            Documents you will <mark>likely</mark> need
          </h3>
          <p className="cn2">Lists differ by programme. Use this as a starting point, then follow the official checklist.</p>
          <div className="docs">
            {REQUIRED_DOCUMENTS.map(([title, desc, tip], i) => (
              <article
                key={title}
                className="pp dc"
                style={{
                  '--r': `${((i % 3) - 1) * 0.8}deg`,
                }}
              >
                <b>0{i + 1}</b>
                <h4>{title}</h4>
                <p>{desc}</p>
                <em>Tip: {tip}</em>
              </article>
            ))}
          </div>

          {/* Mistakes That Cost Applicants */}
          <h3 className="h3s mh">Mistakes that cost applicants</h3>
          <div className="mist">
            <article className="pp idx" style={{ '--r': '-1.2deg' }}>
              <b className="x">✗</b>
              <h4>One generic statement for every programme</h4>
              <p><span>Instead:</span> tailor your opening and the “why this programme” paragraph each time.</p>
            </article>
            <article className="pp idx" style={{ '--r': '0.9deg' }}>
              <b className="x">✗</b>
              <h4>Starting once the deadline is close</h4>
              <p><span>Instead:</span> referees and test scores take weeks, so begin months ahead.</p>
            </article>
            <article className="pp idx" style={{ '--r': '-0.7deg' }}>
              <b className="x">✗</b>
              <h4>Skipping the eligibility page</h4>
              <p><span>Instead:</span> check nationality, degree and language rules before writing a word.</p>
            </article>
            <article className="pp idx" style={{ '--r': '1.3deg' }}>
              <b className="x">✗</b>
              <h4>Uploading unclear documents</h4>
              <p><span>Instead:</span> use clean scans in the exact file format the portal asks for.</p>
            </article>
          </div>

          {/* Interactive Quiz */}
          <h3 className="h3s mh">Check what you learned</h3>
          <article className="pp qz" id="qz">
            {quizIdx < QUIZ_QUESTIONS.length ? (
              <>
                <p className="qk">Question {quizIdx + 1} of {QUIZ_QUESTIONS.length}</p>
                <h3 className="qq">{QUIZ_QUESTIONS[quizIdx].q}</h3>
                <div className="qo">
                  {QUIZ_QUESTIONS[quizIdx].opts.map((opt, optIdx) => {
                    const isSelected = selectedQuizOption === optIdx
                    const isCorrect = optIdx === QUIZ_QUESTIONS[quizIdx].correct
                    let btnClass = ''
                    if (selectedQuizOption !== null) {
                      if (isCorrect) btnClass = 'ok'
                      else if (isSelected) btnClass = 'no'
                    }

                    return (
                      <button
                        key={opt}
                        type="button"
                        disabled={selectedQuizOption !== null}
                        className={btnClass}
                        onClick={() => {
                          setSelectedQuizOption(optIdx)
                          if (isCorrect) {
                            setQuizScore((s) => s + 1)
                            setQuizFeedback(`Correct! ${QUIZ_QUESTIONS[quizIdx].tip}`)
                          } else {
                            setQuizFeedback(`Not quite. ${QUIZ_QUESTIONS[quizIdx].tip}`)
                          }
                        }}
                      >
                        {opt}
                      </button>
                    )
                  })}
                </div>

                {selectedQuizOption !== null && (
                  <>
                    <p className="qf">{quizFeedback}</p>
                    <button
                      type="button"
                      className="btn"
                      onClick={() => {
                        setSelectedQuizOption(null)
                        setQuizFeedback('')
                        setQuizIdx((i) => i + 1)
                      }}
                    >
                      {quizIdx === QUIZ_QUESTIONS.length - 1 ? 'See score' : 'Next question'}
                    </button>
                  </>
                )}
              </>
            ) : (
              <div className="qd">
                <p className="qk">Your score</p>
                <h3>{quizScore} of {QUIZ_QUESTIONS.length}</h3>
                <p className="qm">
                  {quizScore === QUIZ_QUESTIONS.length
                    ? 'Great work! You are ready to start your shortlist.'
                    : quizScore >= 2
                    ? 'Good start. Review the sections above and try again.'
                    : 'No problem. Read the guidance above, then give it another try.'}
                </p>
                <button
                  type="button"
                  className="btn"
                  onClick={() => {
                    setQuizIdx(0)
                    setQuizScore(0)
                    setSelectedQuizOption(null)
                    setQuizFeedback('')
                  }}
                >
                  Try again
                </button>
              </div>
            )}
          </article>
        </div>
      </section>

      {/* ── Pull Quote Banner ────────────────────────────────────────── */}
      <section className="band">
        <p className="pqt">A scholarship is a story, told in documents.</p>
      </section>

      {/* ── 04. PROCESS (How It Works) ───────────────────────────────── */}
      <section id="how">
        <div className="wrap how">
          <div className="st">
            <p className="eb">
              <b>04</b>Process
            </p>
            <h2>From one sentence to a submitted application.</h2>
            <p className="lead">Three steps, and you always see what to do next.</p>
          </div>

          <div id="steps">
            <div className="step on">
              <h3>Tell us your goal</h3>
              <p>Write it in your own words. We turn it into degree level, funding and country criteria.</p>
            </div>
            <div className="step on">
              <h3>See what fits</h3>
              <p>Programmes are ranked by how many of your criteria they meet. Remove a tag to widen the search.</p>
            </div>
            <div className="step on">
              <h3>Prepare and track</h3>
              <p>Write your statement section by section, then follow every application to the deadline.</p>
            </div>
          </div>
        </div>
      </section>

      {/* ── 05. CALL TO ACTION (#end) ─────────────────────────────────── */}
      <section id="end">
        <div className="wrap">
          <h2>Start with one sentence about your goal.</h2>
          <div className="cta2">
            <span className="hw">It only takes one sentence</span>
            <svg className="ar" viewBox="0 0 40 60" aria-hidden="true">
              <path d="M20 4C8 20 32 30 20 52M12 44 20 54 28 44" />
            </svg>
            <a
              className="btn"
              href="#top"
              onClick={(e) => {
                e.preventDefault()
                document.getElementById('top')?.scrollIntoView({ behavior: 'smooth' })
              }}
            >
              Try the match
            </a>
          </div>
        </div>
      </section>

      {/* ── Editorial Footer ─────────────────────────────────────────── */}
      <footer className="ft">
        <div>
          <span className="fb">ScholarZone</span>
          <p>
            Scholarship search, planning and application support, designed for students and researchers from Bangladesh.
          </p>
        </div>
        <div className="fn">
          <a href="#top">Match</a>
          <a href="#tools">Toolkit</a>
          <a href="#learn">Learn</a>
          <a href="#how">How it works</a>
          <Link to="/scholarships">Full Catalogue</Link>
        </div>
        <p className="f3">
          Curated international directory with verified guidelines. Always confirm eligibility, funding allowances and deadlines on each awarding body’s official portal. © 2026 ScholarZone.
        </p>
      </footer>

      {/* ── Slide-over Details Sheet ─────────────────────────────────── */}
      <div
        className={`scrim ${selectedSheetItem ? 'on' : ''}`}
        onClick={() => setSelectedSheetItem(null)}
        aria-hidden="true"
      />

      {selectedSheetItem && (
        <aside
          className="sheet open"
          role="dialog"
          aria-modal="true"
          aria-label={selectedSheetItem.title}
        >
          <button
            className="sx"
            type="button"
            aria-label="Close details"
            onClick={() => setSelectedSheetItem(null)}
          >
            ×
          </button>

          <p className="eb">
            {flagFor(selectedSheetItem.country)} {selectedSheetItem.country}
          </p>
          <h3 className="sh3">{selectedSheetItem.title}</h3>

          <div className="tags" style={{ marginBottom: '14px' }}>
            <span className={selectedSheetItem.isFull ? 'f' : ''}>{selectedSheetItem.funding}</span>
            {selectedSheetItem.levels.map((lvl) => (
              <span key={lvl}>{lvl}</span>
            ))}
            {selectedSheetItem.verified && <span>Verified Official Source</span>}
          </div>

          <p className="sm">{selectedSheetItem.coverage}</p>

          {selectedSheetItem.officialUrl && (
            <div style={{ marginBottom: '24px' }}>
              <a
                href={selectedSheetItem.officialUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="btn"
                style={{ fontSize: '0.84rem', padding: '8px 16px' }}
              >
                Visit Official Portal ↗
              </a>
            </div>
          )}

          {/* Target Deadline Input */}
          <div className="dl">
            <label htmlFor="ddl">Your target deadline</label>
            <div className="dr2">
              <input
                id="ddl"
                type="date"
                value={userPlans[selectedSheetItem.id]?.deadline || ''}
                onChange={(e) => updatePlan(selectedSheetItem.id, { deadline: e.target.value })}
              />
              <span id="dleft">
                {(() => {
                  const dl = getDaysLeft(userPlans[selectedSheetItem.id]?.deadline)
                  if (dl === null) return ''
                  if (dl < 0) return 'Deadline passed'
                  if (dl === 0) return 'Due today'
                  return `${dl} days left`
                })()}
              </span>
            </div>
          </div>

          {/* Checklist Progress */}
          {(() => {
            const plan = userPlans[selectedSheetItem.id] || { checkedTasks: [] }
            const checkedCount = (plan.checkedTasks || []).length
            const totalTasks = PREPARATION_TASKS.length
            const pct = Math.round((checkedCount / totalTasks) * 100)

            return (
              <>
                <div className="pr2">
                  <div className="prog2">
                    <i style={{ width: `${pct}%` }} />
                  </div>
                  <span id="pt">{checkedCount} of {totalTasks} ready</span>
                </div>

                <div className="ck">
                  {PREPARATION_TASKS.map((taskText, taskIdx) => {
                    const isChecked = (plan.checkedTasks || []).includes(taskIdx)
                    return (
                      <label key={taskText}>
                        <input
                          type="checkbox"
                          checked={isChecked}
                          onChange={(e) => {
                            const current = plan.checkedTasks || []
                            const next = e.target.checked
                              ? [...current, taskIdx]
                              : current.filter((x) => x !== taskIdx)
                            updatePlan(selectedSheetItem.id, { checkedTasks: next })
                          }}
                        />
                        <span>{taskText}</span>
                      </label>
                    )
                  })}
                </div>
              </>
            )
          })()}

          <p className="nt">
            Requirements change every year. Always confirm the final requirements on the programme’s official website.
          </p>

          <button
            className="btn"
            type="button"
            style={{ width: '100%', marginTop: '14px' }}
            onClick={() => handleToggleSave(selectedSheetItem)}
          >
            {savedIds.includes(selectedSheetItem.id) || savedIds.includes(String(selectedSheetItem.id))
              ? 'Remove from my plan'
              : 'Add to my plan'}
          </button>
        </aside>
      )}

      {/* ── Toast Notifications ──────────────────────────────────────── */}
      <div className={`toast ${toast.show ? 'on' : ''}`} role="status" aria-live="polite">
        <span>{toast.message}</span>
        {toast.undo && (
          <button
            type="button"
            onClick={() => {
              toast.undo()
              setToast({ show: false, message: '', undo: null })
            }}
          >
            Undo
          </button>
        )}
      </div>
    </div>
  )
}
