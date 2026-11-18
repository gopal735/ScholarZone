import { useState, useMemo, useEffect } from 'react'
import './ItalyDsuGuidePage.css'

function parseDeadlineToDate(deadlineStr) {
  if (!deadlineStr) return null

  const normalized = deadlineStr.replace(/[()/]/g, ' ').replace(/\s+/g, ' ').trim()

  const patterns = [
    { regex: /^(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})/, format: 'dd MMM yyyy' },
    { regex: /^([A-Za-z]+)\s+(\d{1,2}),?\s+(\d{4})/, format: 'MMM dd yyyy' },
    { regex: /^(\d{1,2})\/(\d{1,2})\/(\d{4})/, format: 'dd/MM/yyyy' },
    { regex: /^(\d{4})-(\d{2})-(\d{2})/, format: 'yyyy-MM-dd' },
  ]

  for (const { regex, format } of patterns) {
    const match = normalized.match(regex)
    if (match) {
      let day, month, year
      if (format === 'dd MMM yyyy') {
        day = parseInt(match[1], 10)
        month = new Date(`${match[2]} 1, 2000`).getMonth()
        year = parseInt(match[3], 10)
      } else if (format === 'MMM dd yyyy') {
        day = parseInt(match[2], 10)
        month = new Date(`${match[1]} 1, 2000`).getMonth()
        year = parseInt(match[3], 10)
      } else if (format === 'dd/MM/yyyy') {
        day = parseInt(match[1], 10)
        month = parseInt(match[2], 10) - 1
        year = parseInt(match[3], 10)
      } else if (format === 'yyyy-MM-dd') {
        year = parseInt(match[1], 10)
        month = parseInt(match[2], 10) - 1
        day = parseInt(match[3], 10)
      }
      if (!isNaN(day) && !isNaN(month) && !isNaN(year)) {
        return new Date(Date.UTC(year, month, day, 23, 59, 59))
      }
    }
  }

  const monthMap = {
    jan: 0, january: 0, feb: 1, february: 1, mar: 2, march: 2,
    apr: 3, april: 3, may: 4, jun: 5, june: 5, jul: 6, july: 6,
    aug: 7, august: 7, sep: 8, september: 8, oct: 9, october: 9,
    nov: 10, november: 10, dec: 11, december: 11
  }

  const rangeMatch = normalized.match(/([A-Za-z]+)[\s-]*(\d{1,2})?\s*[–-]\s*([A-Za-z]+)?\s*(\d{1,2})?,?\s*(\d{4})/i)
  if (rangeMatch) {
    const endMonth = monthMap[rangeMatch[3]?.toLowerCase() || rangeMatch[1].toLowerCase()]
    const endDay = parseInt(rangeMatch[4] || rangeMatch[2] || '30', 10)
    const year = parseInt(rangeMatch[5], 10)
    if (!isNaN(endMonth) && !isNaN(endDay) && !isNaN(year)) {
      return new Date(Date.UTC(year, endMonth, endDay, 23, 59, 59))
    }
  }

  const singleMatch = normalized.match(/([A-Za-z]+)\s+(\d{1,2}),?\s+(\d{4})/i)
  if (singleMatch) {
    const month = monthMap[singleMatch[1].toLowerCase()]
    const day = parseInt(singleMatch[2], 10)
    const year = parseInt(singleMatch[3], 10)
    if (!isNaN(month) && !isNaN(day) && !isNaN(year)) {
      return new Date(Date.UTC(year, month, day, 23, 59, 59))
    }
  }

  return null
}

function getCurrentRomeTime() {
  const now = new Date()
  const romeOffset = 2 * 60 * 60 * 1000
  const romeTime = new Date(now.getTime() + romeOffset - (now.getTimezoneOffset() * 60 * 1000))
  return romeTime
}

function calculateStatus(deadline2026) {
  if (!deadline2026) return 'closed'

  const deadlineDate = parseDeadlineToDate(deadline2026)
  if (!deadlineDate) return 'closed'

  const now = getCurrentRomeTime()

  if (deadlineDate < now) return 'closed'
  return 'open'
}

const REGIONS = [
  {
    id: 'abruzzo',
    name: 'Abruzzo',
    agencies: ["ADSU L'Aquila", 'ADSU Teramo', 'ADSU Chieti-Pescara'],
    universities: ["Università degli Studi dell'Aquila", 'Università degli Studi di Teramo', "Università degli Studi G. d'Annunzio Chieti-Pescara"],
    deadline2026: 'Aug–Sep 2026',
    iseeLimit: '€24,335–€28,339',
    note: null,
  },
  {
    id: 'basilicata',
    name: 'Basilicata',
    agencies: ['ARDSU Basilicata'],
    universities: ['Università degli Studi della Basilicata'],
    deadline2026: '9 Oct 2026',
    iseeLimit: '€28,339.88',
    note: null,
  },
  {
    id: 'calabria',
    name: 'Calabria',
    agencies: ['Univ. della Calabria (CR)', 'Univ. Mediterranea Reggio Calabria'],
    universities: ['Università della Calabria', 'Università Mediterranea di Reggio Calabria'],
    deadline2026: 'Aug–Sep 2026',
    iseeLimit: '€26,500',
    note: null,
  },
  {
    id: 'campania',
    name: 'Campania',
    agencies: ['ADiSURC Campania'],
    universities: ['Università di Napoli Federico II', 'Università di Salerno', 'Università Parthenope', 'Università del Sannio', 'Suor Orsola Benincasa'],
    deadline2026: '10 Sep 2026',
    iseeLimit: '€26,887.93',
    note: null,
  },
  {
    id: 'emilia-romagna',
    name: 'Emilia-Romagna',
    agencies: ['ER.GO'],
    universities: ['Università di Bologna', 'Università di Ferrara', 'Università di Modena e Reggio Emilia', 'Università di Parma', 'Università di Piacenza', 'Politecnico di Milano (Piacenza)'],
    deadline2026: 'Jul–Sep 2026',
    iseeLimit: '€25,000',
    note: null,
  },
  {
    id: 'friuli-vg',
    name: 'Friuli-Venezia Giulia',
    agencies: ['ARDiS'],
    universities: ['Università di Trieste', 'Università di Udine', 'Conservatori', 'Accademia Tiepolo'],
    deadline2026: '17 Sep 2026',
    iseeLimit: '€28,339.88',
    note: null,
  },
  {
    id: 'lazio',
    name: 'Lazio',
    agencies: ['DiSCo Lazio'],
    universities: ['Sapienza Università di Roma', 'Università di Roma Tor Vergata', 'Università Roma Tre', 'LUMSA', 'Università di Cassino', 'Università della Tuscia'],
    deadline2026: '22 Jul / 11 Aug 2026',
    iseeLimit: '€28,339.88',
    note: null,
  },
  {
    id: 'liguria',
    name: 'Liguria',
    agencies: ['ALISEO'],
    universities: ['Università di Genova', 'AFAM Liguria'],
    deadline2026: '31 Jul 2026',
    iseeLimit: '€28,339',
    note: null,
  },
  {
    id: 'lombardia',
    name: 'Lombardia',
    agencies: ['Per-university (UniMi, PoliMi, UniBg, UniBs, UniPv, etc.)'],
    universities: ['Università degli Studi di Milano', 'Politecnico di Milano', 'Università di Bergamo', 'Università di Brescia', 'Università di Pavia', "Università degli Studi di Milano-Bicocca"],
    deadline2026: 'Aug–Sep 2026',
    iseeLimit: '€26,887.93',
    note: null,
  },
  {
    id: 'marche',
    name: 'Marche',
    agencies: ['ERDIS Marche'],
    universities: ['Università Politecnica delle Marche', 'Università di Camerino', 'Università di Macerata', 'Università di Urbino Carlo Bo'],
    deadline2026: '28 Aug 2026',
    iseeLimit: '€24,000',
    note: null,
  },
  {
    id: 'molise',
    name: 'Molise',
    agencies: ['ESU Molise'],
    universities: ['Università degli Studi del Molise', "Università Cattolica del Sacro Cuore Campobasso", 'Conservatorio Perosi'],
    deadline2026: '30 Oct 2026',
    iseeLimit: '€19,837.92',
    note: null,
  },
  {
    id: 'piemonte',
    name: 'Piemonte',
    agencies: ['EDISU Piemonte'],
    universities: ['Università di Torino', 'Politecnico di Torino', 'Università del Piemonte Orientale', 'Università di Scienze Gastronomiche'],
    deadline2026: 'PhD/Specialisation: 27 Nov 2026; Undergrad/Master: 4 Sep 2026',
    iseeLimit: '€28,339.88',
    note: 'PhD/Specialisation window open until 27 Nov 2026; Undergrad/Master closed 4 Sep 2026',
  },
  {
    id: 'puglia',
    name: 'Puglia',
    agencies: ['ADISU Puglia'],
    universities: ['Università degli Studi di Bari', 'Politecnico di Bari', 'Università del Salento', 'Università di Foggia'],
    deadline2026: '13 Aug / 30 Oct 2026',
    iseeLimit: '€26,000',
    note: null,
  },
  {
    id: 'sardegna',
    name: 'Sardegna',
    agencies: ['ERSU Cagliari', 'ERSU Sassari'],
    universities: ['Università di Cagliari', 'Università di Sassari'],
    deadline2026: '28 Aug / 7 Sep 2026',
    iseeLimit: '€28,339.88',
    note: null,
  },
  {
    id: 'sicilia',
    name: 'Sicilia',
    agencies: ['ERSU Palermo', 'ERSU Catania'],
    universities: ['Università degli Studi di Palermo', 'Università degli Studi di Catania', 'LUMSA Palermo', 'Accademie', 'Conservatori'],
    deadline2026: 'Jul–Sep 2026',
    iseeLimit: '€23,000–€25,000',
    note: null,
  },
  {
    id: 'toscana',
    name: 'Toscana',
    agencies: ['ARDSU Toscana'],
    universities: ['Università di Firenze', 'Università di Pisa', 'Università di Siena', 'AFAM (Cherubini, Accademia Belle Arti, ecc.)'],
    deadline2026: '7 Sep / 16 Nov 2026',
    iseeLimit: '€25,000',
    note: 'Late window for some programmes until 16 Nov 2026',
  },
  {
    id: 'trentino-trento',
    name: 'Trentino (Trento)',
    agencies: ['Opera Universitaria Trento'],
    universities: ['Università di Trento', 'Conservatorio Bonporti', "Accademia d'Arte Trentino"],
    deadline2026: 'PhD: 30 Nov 2026; earlier windows closed',
    iseeLimit: '€26,000',
    note: 'Non-EU non-residents EXCLUDED from Opera Universitaria call. EU citizens and non-EU residents in Italy may apply.',
  },
  {
    id: 'trentino-bolzano',
    name: 'Alto Adige (Bolzano)',
    agencies: ['Province of Bolzano (separate call)'],
    universities: ['Free University of Bozen-Bolzano'],
    deadline2026: '3 Nov 2026',
    iseeLimit: 'DURP / VSE assessment',
    note: 'Separate provincial call; uses DURP and VSE financial assessment. Non-EU eligibility per provincial rules — check bando.',
  },
  {
    id: 'umbria',
    name: 'Umbria',
    agencies: ['ADiSU Umbria'],
    universities: ['Università degli Studi di Perugia', 'Università per Stranieri di Perugia', 'Accademia Belle Arti', 'Conservatorio Morlacchi'],
    deadline2026: '2 Sep 2026',
    iseeLimit: '€28,339.88',
    note: null,
  },
  {
    id: 'valle-aosta',
    name: "Valle d'Aosta",
    agencies: ["Regione Autonoma Valle d'Aosta (direct)"],
    universities: ["Università della Valle d'Aosta", "Conservatoire de la Vallée d'Aoste", 'Corso Infermieristica UniTo Aosta (VDA2 only)'],
    deadline2026: '4 Dec 2026, 12:00',
    iseeLimit: 'VDA1: ISEE ≤ €28,339.88 + ISPE ≤ €61,608.48 / VDA2: ISEE ≤ €44,968 (no ISPE)',
    note: 'TWO SEPARATE BANDI: VDA1 (more generous) for ISEE ≤28,339.88 AND ISPE ≤61,608.48; VDA2 for ISEE ≤44,968 (no ISPE). Nursing students at UniTo Aosta ONLY VDA2 (apply to EDISU Piemonte). Non-cumulative. Grants vary by ISEE band + residence status.',
  },
  {
    id: 'veneto',
    name: 'Veneto',
    agencies: ["Ca' Foscari (scholarships) / ESU Venezia (accommodation)"],
    universities: ["Università Ca' Foscari Venezia", 'IUAV'],
    deadline2026: '30 Sep 2026',
    iseeLimit: '€26,306.25',
    note: null,
  },
]

const REGIONS_WITH_STATUS = REGIONS.map(region => ({
  ...region,
  status: calculateStatus(region.deadline2026),
}))

const DSU_SECTIONS = [
  {
    id: 'overview',
    title: 'What is DSU?',
    content: `
      <p><strong>DSU (Diritto allo Studio Universitario)</strong> is Italy's constitutional right-to-study system, implementing Article 34 of the Italian Constitution: "Capable and deserving students, even if lacking financial means, have the right to reach the highest levels of education."</p>
      <p>DSU is <strong>not a single national scholarship</strong>. It is a framework of regional calls (<em>bandi</em>) administered by 20+ independent regional agencies (ADISU, EDISU, ARDSU, ERSU, ERDIS, ER.GO, DiSCo, ALISEO, Opera Universitaria, etc.). Each region sets its own:</p>
      <ul>
        <li>Income thresholds (ISEE/ISPE)</li>
        <li>Application deadlines</li>
        <li>Scholarship amounts</li>
        <li>Merit requirements</li>
        <li>Benefit packages (cash + services)</li>
      </ul>
      <p><strong>Key principle:</strong> Never apply one region's rules to another. Always check the specific regional <em>bando</em> for your university.</p>
    `,
  },
  {
    id: 'eligibility',
    title: 'Who Can Apply',
    content: `
      <h4>Citizenship</h4>
      <ul>
        <li><strong>Italian citizens</strong></li>
        <li><strong>EU citizens</strong> (same treatment as Italians)</li>
        <li><strong>Non-EU international students</strong> — eligible under same economic/merit conditions</li>
        <li><strong>Stateless persons & refugees</strong> — special provisions (often ISEE based only on Italian income/assets)</li>
      </ul>
      <h4>Enrollment Status</h4>
      <ul>
        <li><strong>First-year students</strong> (matricole) — apply on economic criteria only; merit checked ex-post</li>
        <li><strong>Subsequent-year students</strong> — must meet merit requirements (CFU credits) at application</li>
        <li><strong>PhD students</strong> — eligible if not receiving other PhD scholarships/grants</li>
        <li><strong>Specialisation students</strong> — eligible except medical area (D.Lgs. 368/1999)</li>
      </ul>
      <h4>Exclusions</h4>
      <ul>
        <li>Already hold a degree of same/higher level (Italy or abroad, recognised)</li>
        <li>Receiving another public scholarship for same academic year</li>
        <li>Part-time students (mostly excluded)</li>
        <li>Repeating a year (mostly excluded)</li>
      </ul>
    `,
  },
  {
    id: 'isee',
    title: 'ISEE / ISEE Parificato / ISPE',
    content: `
      <h4>ISEE Universitario</h4>
      <p>The standard indicator for students with family income/assets in Italy. Requested via <strong>DSU (Dichiarazione Sostitutiva Unica)</strong> at CAF or INPS. Must specify "prestazioni agevolate per il diritto allo studio universitario" with student's tax code.</p>
      <h4>ISEE Parificato (Equalized ISEE)</h4>
      <p>For students whose family resides abroad and/or has income/assets abroad. Calculated by authorised <strong>CAF (Centro di Assistenza Fiscale)</strong> from foreign documents.</p>
      <p><strong>Required documents (typically):</strong></p>
      <ul>
        <li>Family composition certificate</li>
        <li>Gross income 2025 for each family member (issued by competent foreign authority)</li>
        <li>Real estate owned abroad at 31 Dec 2025 (surface area in m², value — conventionally €500/m² if not declared)</li>
        <li>Movable assets (bank balances, investments) at 31 Dec 2025</li>
        <li>Rent paid for family residence abroad</li>
        <li><strong>Translation into Italian</strong> by certified translator</li>
        <li><strong>Legalisation/Apostille</strong> by Italian diplomatic authorities (Embassy/Consulate) or foreign diplomatic representation in Italy + Prefecture legalisation</li>
      </ul>
      <h4>ISPE (Indicatore Situazione Patrimoniale Equivalente)</h4>
      <p>Asset indicator = ISP / equivalence scale. Most regions set both ISEE and ISPE limits; both must be satisfied.</p>
      <h4>Valle d'Aosta Specifics</h4>
      <ul>
        <li><strong>VDA1:</strong> BOTH ISEE-Universitario ≤ €28,339.88 AND ISPE ≤ €61,608.48 required</li>
        <li><strong>VDA2:</strong> ONLY ISEE-Universitario ≤ €44,968 required; NO ISPE limit</li>
        <li><strong>Disability exceptions:</strong> Adjustments to ISEE/ISPE thresholds for students with disability ≥66% (per bando Art. 3.3)</li>
        <li><strong>CAF-confirmed ISEE exception:</strong> If grave/documented impediments prevent obtaining ISEE-Universitario, ordinary ISEE accepted with explicit request in application notes (Art. 3.3)</li>
        <li><strong>Foreign non-resident temporary credentials:</strong> Accepted for portal access (SPID/CIE not required for non-residents)</li>
        <li><strong>ISEE Corrente accepted:</strong> Valid if includes ISEE-Universitario indicator and student name</li>
        <li><strong>Scholarship deduction:</strong> 2024 scholarship amounts declared in DSU (quadro FC4) can be deducted from ISEE-Universitario if declared in application</li>
      </ul>
      <h4>Independent Student Status</h4>
      <p>Student living outside family home ≥2 years in non-family-owned housing + declared taxable income ≥€9,000/year for 2 years. Treated as <em>fuori sede</em> (off-site) for scholarship amount.</p>
    `,
  },
  {
    id: 'status',
    title: 'In Sede / Pendolare / Fuori Sede',
    content: `
      <p>Classification determines scholarship amount. Definitions vary slightly by region.</p>
      <table>
        <thead><tr><th>Status</th><th>Typical Definition</th><th>Scholarship Level</th></tr></thead>
        <tbody>
          <tr><td><strong>In sede</strong> (at home)</td><td>Resides in same municipality as university (or within short commute)</td><td>Lowest (≈€2,890 base)</td></tr>
          <tr><td><strong>Pendolare</strong> (commuter)</td><td>Resides in nearby municipality; commute ≤60–90 min by public transport</td><td>Medium (≈€4,190 base)</td></tr>
          <tr><td><strong>Fuori sede</strong> (off-site)</td><td>Resides far from university; rents accommodation near campus ≥10 months/year</td><td>Highest (≈€7,170 base)</td></tr>
        </tbody>
      </table>
      <p><strong>International students:</strong> Most regions classify non-resident international students as <strong>fuori sede</strong> automatically (family abroad), regardless of Italian address. However, family residence abroad does not guarantee the higher fuori sede payment. Applicants may need to submit a paid-accommodation declaration by the deadline. Check your regional call for the applicable requirements.</p>
      <p><strong>Proof for fuori sede:</strong> Registered rental contract ≥10 months (Sep–Jul), rent ≥€150–200/month, property within 15–26 km of campus.</p>
      <h4>Valle d'Aosta (VDA1/VDA2) Specifics</h4>
      <ul>
        <li><strong>Column A (Resident/Housing beneficiary):</strong> Resident <24 km from university OR housing contribution beneficiary → lower grant</li>
        <li><strong>Column B (Fuori sede):</strong> Resident ≥24 km from university AND (no housing request / not eligible / eligible but no funds / family abroad & 1st year fuori corso) → higher grant</li>
        <li><strong>Housing-aid request BEFORE supporting proof:</strong> Must request contributo alloggio in application; proof of accommodation can be submitted later</li>
        <li><strong>Acceptable later residence documentation:</strong> Proof of accommodation can be provided after application submission</li>
        <li><strong>Students with family abroad:</strong> Classified as fuori sede (Column B) if in 1st year fuori corso, regardless of distance, if not receiving housing contribution</li>
      </ul>
    `,
  },
  {
    id: 'benefits',
    title: 'Benefits Breakdown',
    content: `
      <p>The DSU scholarship comprises a <strong>cash portion</strong> + <strong>services</strong> (deducted from gross amount).</p>
      <h4>Typical Benefits</h4>
      <ul>
        <li><strong>Monetary grant</strong> — varies by ISEE band and status (fuori sede/pendolare/in sede)</li>
        <li><strong>Accommodation</strong> — free place in regional residence (ERSU/ADISU/ESU/Opera/ARDiS/DiSCo/ALISEO) OR rent subsidy (≈€1,500–2,600/year) if no place available</li>
        <li><strong>Meals</strong> — free daily meal(s) at university canteens (1 for in sede/pendolare, 2 for fuori sede)</li>
        <li><strong>Tuition exemption</strong> — full or partial waiver of university fees (varies by region/university)</li>
        <li><strong>Regional tax refund</strong> — €140 regional DSU tax reimbursed to eligible students</li>
        <li><strong>International mobility supplement</strong> — €600/month up to 10 months for Erasmus+/overseas (deduct EU grants)</li>
        <li><strong>Degree award</strong> — bonus for graduating on time (often 50% of last year's grant)</li>
      </ul>
      <h4>Amount Ranges (2026/27 base, before ISEE band adjustments)</h4>
      <table>
        <thead><tr><th>Status</th><th>Min (3rd band)</th><th>Max (1st band)</th></tr></thead>
        <tbody>
          <tr><td>In sede</td><td>€1,445–€2,890</td><td>€2,890–€3,323</td></tr>
          <tr><td>Pendolare</td><td>€2,095–€4,190</td><td>€4,190–€4,819</td></tr>
          <tr><td>Fuori sede</td><td>€3,585–€7,171</td><td>€7,171–€8,246</td></tr>
        </tbody>
      </table>
      <p><em>Increases:</em> +15% for ISEE ≤50% threshold; +20% for female STEM students; +20% for dual enrolment; +20–40% for disability ≥66%.</p>
      <h4>Valle d'Aosta (VDA1) — a.a. 2026/27 Official Amounts</h4>
      <table>
        <thead><tr><th>ISEE Band</th><th>ISEE Range</th><th>Column A (Resident/Housing)</th><th>Column B (Fuori sede ≥24km)</th></tr></thead>
        <tbody>
          <tr><td>1ª</td><td>€0 – €14,169.94</td><td>€3,476</td><td>€4,972</td></tr>
          <tr><td>2ª</td><td>€14,169.95 – €18,893.25</td><td>€3,042</td><td>€4,343</td></tr>
          <tr><td>3ª</td><td>€18,893.26 – €25,452.43</td><td>€2,598</td><td>€3,762</td></tr>
          <tr><td>4ª</td><td>€25,452.44 – €28,339.88</td><td>€2,248</td><td>€3,063</td></tr>
        </tbody>
      </table>
      <ul>
        <li><strong>Housing contribution (contributo alloggio):</strong> €3,145 – €4,924</li>
        <li><strong>Tuition refund:</strong> YES — full reimbursement of university fees if already paid (VDA1 only)</li>
        <li><strong>Meal allowance:</strong> NO free canteen; replaced by lump-sum included in study grant for eligible students (buoni pasto discontinued)</li>
        <li><strong>International mobility:</strong> Separate daily rates (VDA1-specific)</li>
        <li><strong>Travel reimbursement:</strong> Up to official limit (VDA1 only)</li>
        <li><strong>Degree bonus:</strong> Yes</li>
        <li><strong>Ranking-by-merit exception:</strong> VDA1-specific provision</li>
      </ul>
      <h4>Valle d'Aosta (VDA2) — a.a. 2026/27 Official Amounts</h4>
      <table>
        <thead><tr><th>ISEE Band</th><th>ISEE Range</th><th>Grant Range</th></tr></thead>
        <tbody>
          <tr><td>1ª</td><td>€0 – €14,169.94</td><td>€1,502 – €2,524</td></tr>
          <tr><td>2ª</td><td>€14,169.95 – €18,893.25</td><td>€1,502 – €2,524</td></tr>
          <tr><td>3ª</td><td>€18,893.26 – €25,452.43</td><td>€1,502 – €2,524</td></tr>
          <tr><td>4ª</td><td>€25,452.44 – €32,992.00</td><td>€1,502 – €2,524</td></tr>
          <tr><td>5ª</td><td>€32,992.01 – €44,968.00</td><td>€1,502 – €2,524</td></tr>
        </tbody>
      </table>
      <ul>
        <li><strong>Housing contribution (contributo alloggio):</strong> €2,013 – €2,933</li>
        <li><strong>Tuition refund:</strong> NO (VDA2 only)</li>
        <li><strong>International mobility:</strong> Separate daily rates (VDA2-specific, different from VDA1)</li>
        <li><strong>Meal allowance:</strong> Not provided</li>
        <li><strong>Degree bonus:</strong> Yes</li>
      </ul>
    `,
  },
  {
    id: 'process',
    title: 'Application Process',
    content: `
      <ol>
        <li><strong>University admission</strong> — Apply to your chosen programme (separate from DSU). You can apply for DSU before formal enrolment.</li>
        <li><strong>DSU application</strong> — Online via regional agency portal (SPID/CIE required; non-resident internationals get temporary credentials).</li>
        <li><strong>Identity & portal registration</strong> — Create account on agency portal (Sportello Studente, SOSCR, Area Studenti, etc.)</li>
        <li><strong>Financial document preparation</strong> — Get ISEE Universitario (Italy residents) or ISEE Parificato via authorised CAF (family abroad).</li>
        <li><strong>Application submission</strong> — Complete online form by regional deadline. Select benefits: scholarship, accommodation, mobility.</li>
        <li><strong>Accommodation request</strong> — Indicate housing preference in application; confirm/accept place if assigned.</li>
        <li><strong>Provisional ranking</strong> — Published ~1–2 months after deadline. Check for errors; submit appeals within 3–10 days.</li>
        <li><strong>Final ranking</strong> — Confirms beneficiaries (winners) and eligible non-winners (idonei non beneficiari).</li>
        <li><strong>Enrolment confirmation</strong> — Must complete university enrolment by university deadline (check with your university; the March 31 date is NOT in the VDA bando).</li>
        <li><strong>Payment</strong> — IBAN + PEC required. Instalments: 1st (20–50%) by Nov–Dec 2026; balance after merit verification (Aug–Nov 2027).</li>
      </ol>
      <h4>Valle d'Aosta (VDA1/VDA2) Specific Requirements</h4>
      <ul>
        <li><strong>IBAN required BEFORE submission:</strong> Must provide Italian IBAN in the application form</li>
        <li><strong>Housing-aid request BEFORE supporting proof:</strong> Must request contributo alloggio in application; proof of accommodation can be submitted later</li>
        <li><strong>Acceptable later residence documentation:</strong> Proof of accommodation (rental contract, etc.) can be provided after application submission</li>
        <li><strong>Foreign non-resident temporary credentials:</strong> Accepted for portal access (no SPID/CIE needed)</li>
        <li><strong>ISEE-Universitario mandatory:</strong> Must have valid ISEE with Universitario indicator at submission (or DSU receipt); name must appear in ISEE section</li>
        <li><strong>ISEE Corrente accepted:</strong> If valid and includes Universitario indicator</li>
        <li><strong>Ordinary ISEE exception:</strong> Only for grave/documented impediments; must request explicitly in application notes</li>
        <li><strong>Scholarship deduction:</strong> 2024 scholarship amounts in DSU (quadro FC4) can be deducted from ISEE-Universitario if declared</li>
      </ul>
    `,
  },
  {
    id: 'ranking',
    title: 'Ranking, Payments & Renewal',
    content: `
      <h4>Eligible vs Winner</h4>
      <ul>
        <li><strong>Winner (assegnatario/beneficiario)</strong> — Receives cash + services within available budget.</li>
        <li><strong>Eligible non-winner (idoneo non beneficiario)</strong> — Meets all criteria but no funds left. Receives services (meals, tuition exemption, tax refund) but NO cash grant.</li>
      </ul>
      <h4>Provisional → Appeals → Final</h4>
      <p>Provisional rankings published; students have 3–10 days to appeal errors. Final rankings are binding.</p>
      <h4>Payment Installments</h4>
      <ul>
        <li><strong>First-year:</strong> ~20% by Nov 10, ~30% by Dec 31, balance after 20 CFU by Aug 10 / Nov 30 2027</li>
        <li><strong>Master's 1st year:</strong> ~50% by Dec 31, balance after 20–23 CFU</li>
        <li><strong>Subsequent years:</strong> ~50% by Dec 31, ~50% after merit verification</li>
      </ul>
      <h4>Merit Requirements (2026/27 typical)</h4>
      <ul>
        <li>First-year Bachelor/Single-cycle: 20 CFU by Aug 10 2027 (30 Nov 2027 = 50% grant)</li>
        <li>First-year Master's: 20–23 CFU by Aug 10 2027</li>
        <li>Subsequent years: Varies by year/course (e.g., 2nd year Bachelor: 35 CFU; 3rd year: 80 CFU)</li>
      </ul>
      <h4>Valle d'Aosta (VDA1/VDA2) Specific Merit Requirements</h4>
      <ul>
        <li><strong>Programme-specific CFU requirements:</strong> Minimum CFU thresholds vary by course/year (consult bando for your specific programme)</li>
        <li><strong>No grade requirement:</strong> Only CFU count matters, not exam scores</li>
        <li><strong>VDA1 Ranking-by-merit exception:</strong> Specific provision for merit-based ranking in VDA1 (consult bando Art. 6)</li>
        <li><strong>Merit deadline:</strong> CFU must be acquired by the date specified in the bando</li>
      </ul>
      <h4>Renewal</h4>
      <p>Not automatic. Must reapply each year. Must meet merit requirements for previous year to renew.</p>
      <h4>Revocation & Repayment</h4>
      <p>Failure to meet merit, enrolment, or income conditions → revocation + repayment of cash + service costs.</p>
    `,
  },
  {
    id: 'differences',
    title: 'DSU vs MAECI vs University Merit',
    content: `
      <table>
        <thead><tr><th>Feature</th><th>DSU (Regional)</th><th>MAECI (National)</th><th>University Merit</th></tr></thead>
        <tbody>
          <tr><td>Scope</td><td>One region</td><td>All Italy</td><td>Single university</td></tr>
          <tr><td>Basis</td><td>Income + Merit</td><td>Citizenship + Merit</td><td>Merit only</td></tr>
          <tr><td>Funding</td><td>Cash + services</td><td>€10,800 stipend</td><td>Tuition waiver + stipend</td></tr>
          <tr><td>Accommodation</td><td>Yes (regional residences)</td><td>No</td><td>Rarely</td></tr>
          <tr><td>Meals</td><td>Yes (canteen)</td><td>No</td><td>No</td></tr>
          <tr><td>Tuition</td><td>Exemption (often)</td><td>Exemption (regional tax due)</td><td>Full waiver</td></tr>
          <tr><td>Application</td><td>Regional portal</td><td>Study in Italy portal</td><td>University portal</td></tr>
          <tr><td>Compatibility</td><td>Incompatible with MAECI/other DSU</td><td>Incompatible with DSU</td><td>Incompatible with DSU/MAECI</td></tr>
        </tbody>
      </table>
      <p><strong>Rule:</strong> You must choose ONE if eligible for multiple. Exercise choice within 10 days of latest award.</p>
    `,
  },
  {
    id: 'vda-detail',
    title: 'Valle d'Aosta (VDA1 / VDA2) — Complete Official Details',
    content: `
      <p>Valle d'Aosta runs <strong>two separate, non-cumulative bandi</strong> for a.a. 2026/27. Both published at the start of the academic year with a single deadline: <strong>4 December 2026, 12:00</strong>.</p>
      <h4>VDA1 — Bando per studenti iscritti agli Atenei valdostani</h4>
      <ul>
        <li><strong>Eligible institutions:</strong> Università della Valle d'Aosta, Conservatoire de la Vallée d'Aoste</li>
        <li><strong>EXCLUDED:</strong> Corso Infermieristica UniTo sede Aosta (apply to EDISU Piemonte)</li>
        <li><strong>Economic requirements (BOTH required):</strong> ISEE-Universitario ≤ €28,339.88 AND ISPE ≤ €61,608.48</li>
        <li><strong>Grant amounts (Assegno di studio):</strong> 4 ISEE bands, two columns (A: resident/housing beneficiary; B: fuori sede ≥24km)</li>
        <li><strong>Housing contribution:</strong> €3,145 – €4,924</li>
        <li><strong>Tuition refund:</strong> YES — full reimbursement if already paid</li>
        <li><strong>Meal allowance:</strong> NO free canteen; lump-sum included in grant for eligible students (buoni pasto discontinued)</li>
        <li><strong>International mobility:</strong> VDA1-specific daily rates</li>
        <li><strong>Travel reimbursement:</strong> Up to official limit</li>
        <li><strong>Degree bonus:</strong> Yes</li>
        <li><strong>Ranking-by-merit exception:</strong> VDA1-specific provision</li>
        <li><strong>Nursing students:</strong> EXCLUDED from VDA1</li>
      </ul>
      <h4>VDA2 — Bando per studenti fuori regione / telematiche / non-VA1</h4>
      <ul>
        <li><strong>Eligible:</strong> Students NOT meeting VDA1 economic criteria but with ISEE-Universitario ≤ €44,968 (NO ISPE limit)</li>
        <li><strong>Also includes:</strong> Nursing students at UniTo Aosta</li>
        <li><strong>Grant amounts:</strong> 5 ISEE bands, €1,502 – €2,524 (no resident/fuori sede split)</li>
        <li><strong>Housing contribution:</strong> €2,013 – €2,933</li>
        <li><strong>Tuition refund:</strong> NO</li>
        <li><strong>International mobility:</strong> VDA2-specific daily rates (different from VDA1)</li>
        <li><strong>Meal allowance:</strong> Not provided</li>
        <li><strong>Degree bonus:</strong> Yes</li>
      </ul>
      <h4>Common Requirements (Both Bandi)</h4>
      <ul>
        <li><strong>Application deadline:</strong> 4 December 2026, 12:00</li>
        <li><strong>Online only:</strong> SPID/CIE or temporary credentials (non-residents)</li>
        <li><strong>IBAN required at submission</strong></li>
        <li><strong>Housing request in application; proof later acceptable</strong></li>
        <li><strong>ISEE-Universitario mandatory</strong> (or DSU receipt); name must be in ISEE section</li>
        <li><strong>ISEE Corrente accepted</strong> (if valid + includes Universitario)</li>
        <li><strong>Ordinary ISEE exception</strong> only for grave/documented impediments (explicit request in notes)</li>
        <li><strong>Disability ISEE/ISPE adjustments</strong> (≥66%)</li>
        <li><strong>Scholarship deduction:</strong> 2024 scholarship in DSU (quadro FC4) deductible from ISEE if declared</li>
        <li><strong>Programme-specific CFU merit requirements</strong></li>
        <li><strong>Annual reapplication required</strong></li>
      </ul>
      <h4>Official Sources</h4>
      <ul>
        <li><a href="https://www.regione.vda.it/allegato.aspx?pk=97584" target="_blank" rel="noopener">Bando VDA1 (Atenei valdostani) — PDF</a></li>
        <li><a href="https://www.regione.vda.it/allegato.aspx?pk=97595" target="_blank" rel="noopener">Bando VDA2 (Fuori regione / Telematiche) — PDF</a></li>
        <li><a href="https://www.regione.vda.it/istruzione/dirittostudio/borse_universita_valdostane/default_i.aspx" target="_blank" rel="noopener">Regione VdA DSU Portal</a></li>
      </ul>
    `,
  },
  {
    id: 'visa',
    title: 'Admission, DSU & Student Visa',
    content: `
      <ol>
        <li><strong>University admission</strong> → Get admission letter / pre-enrolment confirmation.</li>
        <li><strong>DSU application</strong> — Can apply before visa; use temporary credentials if no SPID/CIE.</li>
        <li><strong>Visa application</strong> — DSU award letter (or provisional ranking) supports visa as proof of financial means.</li>
        <li><strong>Minimum means for visa</strong> — For 2026/27 university-enrolment visas, the Italian Foreign Ministry lists €10,179.85 per year. A DSU fuori sede award (max ~€7,171) may not meet this threshold alone. Consult your consulate for acceptable proof and any additional requirements.</li>
        <li><strong>Arrival in Italy</strong> — Non-EU students on long-stay study visas must apply for a residence permit (permesso di soggiorno) within eight working days of arrival. The application receipt comes before the permit; check which document your agency accepts for upload.</li>
        <li><strong>Enrolment confirmation</strong> — Complete by university deadline (check with your university; the March 31 date is NOT in the VDA bando).</li>
        <li><strong>Payment activation</strong> — Provide Italian IBAN + PEC; first instalment after enrolment verified.</li>
      </ol>
      <p><strong>Critical:</strong> DSU eligibility does not guarantee a scholarship. Budget limits mean eligible non-winners receive services only. Visa requires proof of sufficient means — DSU provisional ranking helps but final award is not guaranteed.</p>
    `,
  },
  {
    id: 'checklist',
    title: 'International Applicant Checklist',
    content: `
      <h4>Before Applying</h4>
      <ul>
        <li>[ ] Identify your university's regional DSU agency (see table below)</li>
        <li>[ ] Check 2026/27 bando deadline — <strong>most are CLOSED</strong></li>
        <li>[ ] Verify ISEE/ISPE limits for your region</li>
        <li>[ ] Determine your status: in sede / pendolare / fuori sede</li>
      </ul>
      <h4>Financial Documents (Family Abroad)</h4>
      <ul>
        <li>[ ] Family composition certificate</li>
        <li>[ ] 2025 income statements for each family member</li>
        <li>[ ] Property ownership docs (31 Dec 2025) with surface area</li>
        <li>[ ] Bank/investment statements (31 Dec 2025)</li>
        <li>[ ] Rent receipts for family residence</li>
        <li>[ ] Certified Italian translation</li>
        <li>[ ] Legalisation/Apostille by Italian Embassy/Consulate</li>
        <li>[ ] Contact authorised CAF for ISEE Parificato calculation</li>
      </ul>
      <h4>Application</h4>
      <ul>
        <li>[ ] Register on agency portal (SPID/CIE or temporary credentials)</li>
        <li>[ ] Complete online application by deadline</li>
        <li>[ ] Upload all required documents</li>
        <li>[ ] Request accommodation if needed</li>
        <li>[ ] Save application receipt</li>
      </ul>
      <h4>After Submission</h4>
      <ul>
        <li>[ ] Monitor provisional ranking publication</li>
        <li>[ ] Submit appeals within deadline if errors found</li>
        <li>[ ] Complete university enrolment by deadline</li>
        <li>[ ] Provide IBAN + PEC for payments</li>
        <li>[ ] Upload residence permit (non-EU) within agency deadline</li>
      </ul>
    `,
  },
  {
    id: 'warnings',
    title: 'Critical Warnings',
    content: `
      <ul>
        <li><strong>Regional rules differ.</strong> Do not assume Lazio rules apply in Lombardia. Check your agency's bando.</li>
        <li><strong>2026/27 deadlines mostly passed.</strong> Check the status column in the table above for currently open calls.</li>
        <li><strong>No 2027/28 calls published yet.</strong> Expected Jun–Sep 2027 based on historical patterns — not confirmed.</li>
        <li><strong>ISEE Parificato takes time.</strong> CAF processing + legalisation can take 4–8 weeks. Start early.</li>
        <li><strong>Fuori sede proof is strict.</strong> Registered contract ≥10 months, rent ≥€150/mo, within km limit. Private agreements without registration don't count.</li>
        <li><strong>Merit is mandatory for renewal.</strong> First-year: 20 CFU by Aug 10. Missed = 50% grant; missed by Nov 30 = revocation + repayment.</li>
        <li><strong>Incompatibility is enforced.</strong> Cannot hold DSU + MAECI + university merit simultaneously. Choose within 10 days.</li>
        <li><strong>Eligible ≠ Winner.</strong> Budget caps mean many eligible students get services only (no cash).</li>
        <li><strong>Trentino (Trento) excludes non-resident non-EU.</strong> Only EU citizens + non-EU residents in Italy may apply to Opera Universitaria call. Alto Adige (Bolzano) has a separate provincial call with its own rules.</li>
        <li><strong>Valle d'Aosta: VDA1 & VDA2 are mutually exclusive.</strong> Choose based on ISEE/ISPE. VDA1 more generous (higher grants, tuition refund) but stricter (ISPE limit). VDA2 no ISPE but lower grants, no tuition refund.</li>
        <li><strong>Nursing students at UniTo Aosta:</strong> ONLY eligible for VDA2 (must apply to EDISU Piemonte).</li>
        <li><strong>No March 31 enrolment deadline in VDA bando.</strong> Check university-specific enrolment deadlines.</li>
        <li><strong>Meal vouchers (buoni pasto) discontinued for VDA1.</strong> Replaced by lump-sum in study grant for eligible students.</li>
      </ul>
    `,
  },
  {
    id: 'sources',
    title: 'Official Sources by Region',
    content: `
      <p>Always verify on the official agency website. Links current as of Nov 2026.</p>
      <ul>
        <li><strong>Abruzzo:</strong> ADSU L'Aquila (adsuaq.org), ADSU Teramo (adsuteramo.it), ADSU Chieti-Pescara (adsuchietipescara.it)</li>
        <li><strong>Basilicata:</strong> ARDSU (ardsubasilicata.it)</li>
        <li><strong>Calabria:</strong> Univ. Calabria CR (unical.it/diritto-allo-studio), UniRC (unirc.it)</li>
        <li><strong>Campania:</strong> ADiSURC (adisurcampania.it)</li>
        <li><strong>Emilia-Romagna:</strong> ER.GO (er-go.it)</li>
        <li><strong>Friuli-VG:</strong> ARDiS (ardis.fvg.it)</li>
        <li><strong>Lazio:</strong> DiSCo (laziodisco.it)</li>
        <li><strong>Liguria:</strong> ALISEO (aliseo.liguria.it)</li>
        <li><strong>Lombardia:</strong> UniMi (unimi.it), PoliMi (polimi.it), others per university</li>
        <li><strong>Marche:</strong> ERDIS (erdis.it)</li>
        <li><strong>Molise:</strong> ESU Molise (esu.molise.it)</li>
        <li><strong>Piemonte:</strong> EDISU (edisu.piemonte.it)</li>
        <li><strong>Puglia:</strong> ADISU (adisupuglia.it)</li>
        <li><strong>Sardegna:</strong> ERSU Cagliari (ersucagliari.it), ERSU Sassari (ersusassari.it)</li>
        <li><strong>Sicilia:</strong> ERSU Palermo (ersupalermo.it), ERSU Catania (ersucatania.it)</li>
        <li><strong>Toscana:</strong> ARDSU Toscana (dsu.toscana.it)</li>
        <li><strong>Trentino:</strong> Opera Universitaria (operauni.tn.it)</li>
        <li><strong>Umbria:</strong> ADiSU (adisu.umbria.it)</li>
        <li><strong>Valle d'Aosta:</strong> Regione VdA (regione.vda.it/istruzione/dirittostudio)</li>
        <li><strong>Veneto:</strong> Ca' Foscari (unive.it/diritto-allo-studio), ESU Venezia (esuvenezia.it)</li>
      </ul>
      <p><strong>National:</strong> MAECI Study in Italy (studyinitaly.esteri.it), MUR (mur.gov.it), Universitaly (universitaly.it)</p>
    `,
  },
]

export default function ItalyDsuGuidePage() {
  const [searchTerm, setSearchTerm] = useState('')
  const [regionFilter, setRegionFilter] = useState('all')
  const [currentRomeTime, setCurrentRomeTime] = useState(() => getCurrentRomeTime())

  useEffect(() => {
    const interval = setInterval(() => {
      setCurrentRomeTime(getCurrentRomeTime())
    }, 60000)
    return () => clearInterval(interval)
  }, [])

  const filteredRegions = useMemo(() => {
    return REGIONS_WITH_STATUS.filter(r => {
      const searchLower = searchTerm.toLowerCase()
      const matchesSearch = !searchTerm ||
        r.name.toLowerCase().includes(searchLower) ||
        r.agencies.some(a => a.toLowerCase().includes(searchLower)) ||
        r.universities.some(u => u.toLowerCase().includes(searchLower))
      const matchesFilter = regionFilter === 'all' || regionFilter === r.status
      return matchesSearch && matchesFilter
    })
  }, [searchTerm, regionFilter])

  const openRegions = useMemo(() => REGIONS_WITH_STATUS.filter(r => r.status === 'open').length, [])
  const closedRegions = useMemo(() => REGIONS_WITH_STATUS.filter(r => r.status === 'closed').length, [])

  const getMatchingUniversities = (region) => {
    if (!searchTerm) return region.universities
    const searchLower = searchTerm.toLowerCase()
    return region.universities.filter(u => u.toLowerCase().includes(searchLower))
  }

  const getMatchingAgencies = (region) => {
    if (!searchTerm) return region.agencies
    const searchLower = searchTerm.toLowerCase()
    return region.agencies.filter(a => a.toLowerCase().includes(searchLower))
  }

  const formatRomeDate = (date) => {
    return new Intl.DateTimeFormat('en-GB', {
      timeZone: 'Europe/Rome',
      weekday: 'short',
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    }).format(date)
  }

  return (
    <div className="italy-dsu-guide">
      <header className="italy-dsu-guide__header">
        <span className="italy-dsu-guide__kicker">Italy DSU Knowledge System</span>
        <h1 className="italy-dsu-guide__title">Diritto allo Studio Universitario — Complete Guide</h1>
        <p className="italy-dsu-guide__subtitle">
          Regional right-to-study funding for international students. 20 regions, 20+ agencies, one constitutional right.
        </p>
        <div className="italy-dsu-guide__status-bar">
          <span className={`status-pill status-pill--open`}>
            {openRegions} Open
          </span>
          <span className={`status-pill status-pill--closed`}>
            {closedRegions} Closed (2026/27)
          </span>
          <span className="status-pill status-pill--note">
            As of {formatRomeDate(currentRomeTime)} (Europe/Rome)
          </span>
        </div>
      </header>

      <div className="italy-dsu-guide__layout">
        <nav className="italy-dsu-guide__sidebar" aria-label="Guide sections">
          <div className="italy-dsu-guide__search">
            <input
              type="search"
              placeholder="Search regions, agencies, universities…"
              value={searchTerm}
              onChange={e => setSearchTerm(e.target.value)}
              aria-label="Search regions"
              aria-describedby="search-hint"
            />
            <select
              value={regionFilter}
              onChange={e => setRegionFilter(e.target.value)}
              aria-label="Filter by status"
            >
              <option value="all">All Regions</option>
              <option value="open">Open Only</option>
              <option value="closed">Closed (2026/27)</option>
            </select>
            <span id="search-hint" className="sr-only">
              {filteredRegions.length} of {REGIONS_WITH_STATUS.length} regions match
            </span>
          </div>

          <ul className="italy-dsu-guide__region-list" role="list">
            {filteredRegions.map(region => (
              <li key={region.id} className="italy-dsu-guide__region-item">
                <a
                  href={`#${region.id}`}
                  className={`italy-dsu-guide__region-btn ${region.status}`}
                  aria-label={`${region.name} — ${region.status.toUpperCase()}`}
                >
                  <span className="italy-dsu-guide__region-name">{region.name}</span>
                  <span className={`italy-dsu-guide__region-status status-${region.status}`}>
                    {region.status === 'open' ? 'OPEN' : 'CLOSED'}
                  </span>
                </a>
                {region.note && (
                  <div className="italy-dsu-guide__region-note" aria-live="polite">
                    {region.note}
                  </div>
                )}
              </li>
            ))}
          </ul>

          <div className="italy-dsu-guide__sidebar-footer">
            <p className="italy-dsu-guide__disclaimer">
              <strong>⚠ Strict inclusion rule:</strong> Only OPEN cycles shown as active opportunities.
              CLOSED 2026/27 calls are reference only. No 2027/28 calls officially announced.
            </p>
          </div>
        </nav>

        <main className="italy-dsu-guide__content" role="main">
          <section id="overview" className="italy-dsu-guide__section">
            <h2>What is DSU?</h2>
            <div className="italy-dsu-guide__section-content" dangerouslySetInnerHTML={{ __html: DSU_SECTIONS[0].content }} />
          </section>

          <section id="regional-table" className="italy-dsu-guide__section">
            <h2>Regional Agency Directory — 2026/27 Status</h2>
            <div className="italy-dsu-guide__table-wrap">
              <table className="italy-dsu-guide__region-table">
                <thead>
                  <tr>
                    <th>Region</th>
                    <th>Agency(ies)</th>
                    <th>Key Universities</th>
                    <th>2026/27 Deadline</th>
                    <th>ISEE Limit</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {REGIONS_WITH_STATUS.map(region => (
                    <tr key={region.id} id={region.id} className={`region-row status-${region.status}`}>
                      <td className="region-name"><strong>{region.name}</strong></td>
                      <td className="region-agencies">{region.agencies.join(', ')}</td>
                      <td className="region-universities">
                        {getMatchingUniversities(region).slice(0, 3).join(', ')}
                        {region.universities.length > 3 ? ' +' : ''}
                      </td>
                      <td className="region-deadline">{region.deadline2026}</td>
                      <td className="region-isee">{region.iseeLimit}</td>
                      <td className="region-status">
                        <span className={`status-badge status-${region.status}`}>
                          {region.status === 'open' ? 'OPEN' : 'CLOSED'}
                        </span>
                        {region.note && <div className="region-note">{region.note}</div>}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          {DSU_SECTIONS.slice(1).map(section => (
            <section key={section.id} id={section.id} className="italy-dsu-guide__section">
              <h2>{section.title}</h2>
              <div className="italy-dsu-guide__section-content" dangerouslySetInnerHTML={{ __html: section.content }} />
            </section>
          ))}
        </main>
      </div>
    </div>
  )
}