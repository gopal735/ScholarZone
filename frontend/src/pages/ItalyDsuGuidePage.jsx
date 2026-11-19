import { useState, useMemo, useEffect } from 'react'
import './ItalyDsuGuidePage.css'

function parseDeadlineToDate(deadlineStr) {
  if (!deadlineStr) return null

  const normalized = deadlineStr.replace(/[()/]/g, ' ').replace(/\s+/g, ' ').trim()

  const monthMap = {
    jan: 0, january: 0, feb: 1, february: 1, mar: 2, march: 2,
    apr: 3, april: 3, may: 4, jun: 5, june: 5, jul: 6, july: 6,
    aug: 7, august: 7, sep: 8, september: 8, oct: 9, october: 9,
    nov: 10, november: 10, dec: 11, december: 11
  }

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

  const dateMatches = [...normalized.matchAll(/([A-Za-z]{3,9})[\s-]+(\d{1,2}),?\s+(\d{4})/gi)]
  if (dateMatches.length > 0) {
    let latestDate = null
    for (const match of dateMatches) {
      const month = monthMap[match[1].toLowerCase()]
      const day = parseInt(match[2], 10)
      const year = parseInt(match[3], 10)
      if (!isNaN(month) && !isNaN(day) && !isNaN(year)) {
        const date = new Date(Date.UTC(year, month, day, 23, 59, 59))
        if (!latestDate || date > latestDate) {
          latestDate = date
        }
      }
    }
    if (latestDate) return latestDate
  }

  const dayFirstMatches = [...normalized.matchAll(/(\d{1,2})[\s-]+([A-Za-z]{3,9})[\s-]+(\d{4})/gi)]
  if (dayFirstMatches.length > 0) {
    let latestDate = null
    for (const match of dayFirstMatches) {
      const day = parseInt(match[1], 10)
      const month = monthMap[match[2].toLowerCase()]
      const year = parseInt(match[3], 10)
      if (!isNaN(month) && !isNaN(day) && !isNaN(year)) {
        const date = new Date(Date.UTC(year, month, day, 23, 59, 59))
        if (!latestDate || date > latestDate) {
          latestDate = date
        }
      }
    }
    if (latestDate) return latestDate
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
  // Return the actual instant. Comparison logic relies on absolute instants;
  // Europe/Rome is applied only for calendar display via Intl (see formatRomeDate).
  return new Date()
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
    aliases: ['Trentino-Alto Adige', 'Trentino Alto Adige', 'Trentino'],
    agencies: ['Opera Universitaria Trento'],
    universities: ['Università di Trento', 'Conservatorio Bonporti', "Accademia d'Arte Trentino"],
    deadline2026: 'PhD: 30 Nov 2026; earlier windows closed',
    iseeLimit: '€26,000',
    note: 'Non-EU non-residents EXCLUDED from Opera Universitaria call. EU citizens and non-EU residents in Italy may apply.',
  },
  {
    id: 'trentino-bolzano',
    name: 'Alto Adige (Bolzano)',
    aliases: ['Trentino-Alto Adige', 'Trentino Alto Adige', 'Alto Adige', 'Bolzano'],
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
    universities: ["Università della Valle d'Aosta", "Conservatoire de la Vallée d'Aoste", 'Corso Infermieristica UniTo Aosta'],
    deadline2026: '4 Dec 2026, 12:00',
    iseeLimit: 'VDA1: €28,339.88 / VDA2: €44,968',
    note: null,
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

function getRegionsWithStatus(currentTime) {
  return REGIONS.map(region => ({
    ...region,
    status: calculateStatus(region.deadline2026, currentTime),
  }))
}

function calculateStatus(deadline2026, currentTime) {
  if (!deadline2026) return 'closed'

  const deadlineDate = parseDeadlineToDate(deadline2026)
  if (!deadlineDate) return 'closed'

  const now = currentTime || getCurrentRomeTime()

  if (deadlineDate < now) return 'closed'
  return 'open'
}

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
      <h3>Citizenship</h3>
      <ul>
        <li><strong>Italian citizens</strong></li>
        <li><strong>EU citizens</strong> (same treatment as Italians)</li>
        <li><strong>Non-EU international students</strong> — eligible under same economic/merit conditions</li>
        <li><strong>Stateless persons & refugees</strong> — special provisions (often ISEE based only on Italian income/assets)</li>
      </ul>
      <h3>Enrollment Status</h3>
      <ul>
        <li><strong>First-year students</strong> (matricole) — apply on economic criteria only; merit checked ex-post</li>
        <li><strong>Subsequent-year students</strong> — must meet merit requirements (CFU credits) at application</li>
        <li><strong>PhD students</strong> — eligible if not receiving other PhD scholarships/grants</li>
        <li><strong>Specialisation students</strong> — eligible except medical area (D.Lgs. 368/1999)</li>
      </ul>
      <h3>Exclusions</h3>
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
      <h3>ISEE Universitario</h3>
      <p>The standard indicator for students with family income/assets in Italy. Requested via <strong>DSU (Dichiarazione Sostitutiva Unica)</strong> at CAF or INPS. Must specify "prestazioni agevolate per il diritto allo studio universitario" with student's tax code.</p>
      <h3>ISEE Parificato (Equalized ISEE)</h3>
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
<p><strong>Reference year varies by agency and call.</strong> Do not assume one universal year. For example, ER.GO 2026/27 requires 2025 foreign income/assets, while UniSR 2026/27 requires 2024 foreign income/assets. Always use the reference year stated in the official call for your agency and academic year.</p>
      <h3>ISPE (Indicatore Situazione Patrimoniale Equivalente)</h3>
      <p>Asset indicator = ISP / equivalence scale. Most regions set both ISEE and ISPE limits; both must be satisfied.</p>
      <h3>Independent Student Status</h3>
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
    `,
  },
  {
    id: 'benefits',
    title: 'Benefits Breakdown',
    content: `
      <p>The DSU scholarship comprises a <strong>cash portion</strong> + <strong>services</strong> (deducted from gross amount).</p>
      <h3>Typical Benefits</h3>
      <ul>
        <li><strong>Monetary grant</strong> — varies by ISEE band and status (fuori sede/pendolare/in sede)</li>
        <li><strong>Accommodation</strong> — free place in regional residence (ERSU/ADISU/ESU/Opera/ARDiS/DiSCo/ALISEO) OR rent subsidy (≈€1,500–2,600/year) if no place available</li>
        <li><strong>Meals</strong> — free daily meal(s) at university canteens (1 for in sede/pendolare, 2 for fuori sede)</li>
        <li><strong>Tuition exemption</strong> — full or partial waiver of university fees (varies by region/university)</li>
        <li><strong>Regional tax refund</strong> — €140 regional DSU tax reimbursed to eligible students</li>
        <li><strong>International mobility supplement</strong> — €600/month up to 10 months for Erasmus+/overseas (deduct EU grants)</li>
        <li><strong>Degree award</strong> — bonus for graduating on time (often 50% of last year's grant)</li>
      </ul>
      <h3>Amount Ranges (2026/27 base, before ISEE band adjustments)</h3>
      <table>
        <thead><tr><th>Status</th><th>Min (3rd band)</th><th>Max (1st band)</th></tr></thead>
        <tbody>
          <tr><td>In sede</td><td>€1,445–€2,890</td><td>€2,890–€3,323</td></tr>
          <tr><td>Pendolare</td><td>€2,095–€4,190</td><td>€4,190–€4,819</td></tr>
          <tr><td>Fuori sede</td><td>€3,585–€7,171</td><td>€7,171–€8,246</td></tr>
        </tbody>
      </table>
      <p><em>Increases:</em> +15% for ISEE ≤50% threshold; +20% for female STEM students; +20% for dual enrolment; +20–40% for disability ≥66%.</p>
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
        <li><strong>Enrolment confirmation</strong> — Must complete university enrolment by deadline (often 31 Mar 2027 for 2026/27).</li>
        <li><strong>Payment</strong> — IBAN + PEC required. Instalments: 1st (20–50%) by Nov–Dec 2026; balance after merit verification (Aug–Nov 2027).</li>
      </ol>
    `,
  },
  {
    id: 'ranking',
    title: 'Ranking, Payments & Renewal',
    content: `
      <h3>Eligible vs Winner</h3>
      <ul>
        <li><strong>Winner (assegnatario/beneficiario)</strong> — Receives cash + services within available budget.</li>
        <li><strong>Eligible non-winner (idoneo non beneficiario)</strong> — Meets all criteria but no funds left. Receives services (meals, tuition exemption, tax refund) but NO cash grant.</li>
      </ul>
      <h3>Provisional → Appeals → Final</h3>
      <p>Provisional rankings published; students have 3–10 days to appeal errors. Final rankings are binding.</p>
      <h3>Payment Installments</h3>
      <ul>
        <li><strong>First-year:</strong> ~20% by Nov 10, ~30% by Dec 31, balance after 20 CFU by Aug 10 / Nov 30 2027</li>
        <li><strong>Master's 1st year:</strong> ~50% by Dec 31, balance after 20–23 CFU</li>
        <li><strong>Subsequent years:</strong> ~50% by Dec 31, ~50% after merit verification</li>
      </ul>
      <h3>Merit Requirements (2026/27 typical)</h3>
      <ul>
        <li>First-year Bachelor/Single-cycle: 20 CFU by Aug 10 2027 (30 Nov 2027 = 50% grant)</li>
        <li>First-year Master's: 20–23 CFU by Aug 10 2027</li>
        <li>Subsequent years: Varies by year/course (e.g., 2nd year Bachelor: 35 CFU; 3rd year: 80 CFU)</li>
      </ul>
      <h3>Renewal</h3>
      <p>Not automatic. Must reapply each year. Must meet merit requirements for previous year to renew.</p>
      <h3>Revocation & Repayment</h3>
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
    id: 'visa',
    title: 'Admission, DSU & Student Visa',
    content: `
      <ol>
        <li><strong>University admission</strong> → Get admission letter / pre-enrolment confirmation.</li>
        <li><strong>DSU application</strong> — Can apply before visa; use temporary credentials if no SPID/CIE.</li>
        <li><strong>Visa application</strong> — DSU award letter (or provisional ranking) supports visa as proof of financial means.</li>
        <li><strong>Minimum means for visa</strong> — For 2026/27 university-enrolment visas, the Italian Foreign Ministry lists €10,179.85 per year. A DSU fuori sede award (max ~€7,171) may not meet this threshold alone. Consult your consulate for acceptable proof and any additional requirements.</li>
        <li><strong>Arrival in Italy</strong> — Non-EU students on long-stay study visas must apply for a residence permit (permesso di soggiorno) within eight working days of arrival. The application receipt comes before the permit; check which document your agency accepts for upload.</li>
        <li><strong>Enrolment confirmation</strong> — Complete by university deadline (often 31 Mar 2027).</li>
        <li><strong>Payment activation</strong> — Provide Italian IBAN + PEC; first instalment after enrolment verified.</li>
      </ol>
      <p><strong>Critical:</strong> DSU eligibility does not guarantee a scholarship. Budget limits mean eligible non-winners receive services only. Visa requires proof of sufficient means — DSU provisional ranking helps but final award is not guaranteed.</p>
    `,
  },
  {
    id: 'checklist',
    title: 'International Applicant Checklist',
    content: `
      <h3>Before Applying</h3>
      <ul>
        <li>[ ] Identify your university's regional DSU agency (see table below)</li>
        <li>[ ] Check 2026/27 bando deadline — <strong>most are CLOSED</strong></li>
        <li>[ ] Verify ISEE/ISPE limits for your region</li>
        <li>[ ] Determine your status: in sede / pendolare / fuori sede</li>
      </ul>
      <h3>Financial Documents (Family Abroad)</h3>
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
      <h3>Application</h3>
      <ul>
        <li>[ ] Register on agency portal (SPID/CIE or temporary credentials)</li>
        <li>[ ] Complete online application by deadline</li>
        <li>[ ] Upload all required documents</li>
        <li>[ ] Request accommodation if needed</li>
        <li>[ ] Save application receipt</li>
      </ul>
      <h3>After Submission</h3>
      <ul>
        <li>[ ] Monitor provisional ranking publication</li>
        <li>[ ] Submit appeals within deadline if errors found</li>
        <li>[ ] Complete university enrolment by deadline</li>
        <li>[ ] Provide IBAN + PEC for payments</li>
        <li>[ ] Upload residence permit receipt (permesso di soggiorno receipt) as interim proof if the permit is not yet issued, or the permit itself — whichever your agency requires by its deadline</li>
        <li>[ ] Upload residence permit (non-EU) within agency deadline once issued</li>
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

  const regionsWithStatus = useMemo(() => getRegionsWithStatus(currentRomeTime), [currentRomeTime])

  const filteredRegions = useMemo(() => {
    return regionsWithStatus.filter(r => {
      const searchLower = searchTerm.toLowerCase()
      const matchesSearch = !searchTerm ||
        r.name.toLowerCase().includes(searchLower) ||
        r.agencies.some(a => a.toLowerCase().includes(searchLower)) ||
        r.universities.some(u => u.toLowerCase().includes(searchLower)) ||
        (r.aliases || []).some(a => a.toLowerCase().includes(searchLower))
      const matchesFilter = regionFilter === 'all' || regionFilter === r.status
      return matchesSearch && matchesFilter
    })
  }, [searchTerm, regionFilter, regionsWithStatus])

  const openRegions = useMemo(() => regionsWithStatus.filter(r => r.status === 'open').length, [regionsWithStatus])
  const closedRegions = useMemo(() => regionsWithStatus.filter(r => r.status === 'closed').length, [regionsWithStatus])

  const getMatchingUniversities = (region) => {
    if (!searchTerm) return region.universities
    const searchLower = searchTerm.toLowerCase()
    const matches = region.universities.filter(u => u.toLowerCase().includes(searchLower))
    if (matches.length > 0) return matches
    // If the search matched the region or an agency but no university name,
    // keep the full regional university list instead of hiding it.
    const regionMatched =
      region.name.toLowerCase().includes(searchLower) ||
      (region.aliases || []).some(a => a.toLowerCase().includes(searchLower)) ||
      region.agencies.some(a => a.toLowerCase().includes(searchLower))
    return regionMatched ? region.universities : []
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
              {filteredRegions.length} of {regionsWithStatus.length} regions match
            </span>
          </div>

          <ul className="italy-dsu-guide__region-list" role="list" data-testid="region-list">
            {filteredRegions.map(region => (
              <li key={region.id} className="italy-dsu-guide__region-item" role="listitem">
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
                  {regionsWithStatus.map(region => (
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