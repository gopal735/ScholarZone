// English + Bangla strings for the Global Study-to-Career Strategist.
//
// The project's existing i18n approach (features/journey/i18n) is a feature-scoped
// dictionary with three modes: `en`, `bn`, and `both` (Bangla first, English
// beneath). This mirrors it exactly so the strategist is i18n-ready the same way
// the rest of the app is, and so a reviewer can compare the two side by side.
//
// Keys map to an `{ en, bn }` pair. `both` is the default render because the
// primary audience reads Bangla but verifies terminology in English.

const STRINGS = {
  'page.title': { en: 'Global Study-to-Career Strategist', bn: 'গ্লোবাল স্টাডি-টু-ক্যারিয়ার স্ট্র্যাটেজিস্ট' },
  'page.subtitle': {
    en: 'One decision, every dimension - subject, degree, funding, country, career and immigration. Informational only.',
    bn: 'একটি সিদ্ধান্ত, সব মাত্রা - বিষয়, ডিগ্রি, ফান্ডিং, দেশ, ক্যারিয়ার ও ইমিগ্রেশন। শুধুমাত্র তথ্যভিত্তিক।',
  },
  'language.label': { en: 'Language', bn: 'ভাষা' },
  'language.en': { en: 'English', bn: 'ইংরেজি' },
  'language.bn': { en: 'Bangla', bn: 'বাংলা' },
  'language.both': { en: 'Both', bn: 'উভয়' },

  'step.subject': { en: 'Subject', bn: 'বিষয়' },
  'step.degree': { en: 'Degree', bn: 'ডিগ্রি' },
  'step.funding': { en: 'Funding model', bn: 'ফান্ডিং মডেল' },
  'step.budget': { en: 'Budget', bn: 'বাজেট' },
  'step.priorities': { en: 'Priorities', bn: 'অগ্রাধিকার' },
  'step.results': { en: 'Results', bn: 'ফলাফল' },

  'btn.next': { en: 'Next', bn: 'পরবর্তী' },
  'btn.back': { en: 'Back', bn: 'পূর্ববর্তী' },
  'btn.viewResults': { en: 'See results', bn: 'ফলাফল দেখুন' },
  'btn.compare': { en: 'Compare countries', bn: 'দেশ তুলনা করুন' },

  'subject.pick': { en: 'Choose your subject', bn: 'আপনার বিষয় নির্বাচন করুন' },
  'degree.pick': { en: 'Choose your degree', bn: 'আপনার ডিগ্রি নির্বাচন করুন' },
  'degree.bachelor': { en: "Bachelor's", bn: 'স্নাতক' },
  'degree.master': { en: "Master's", bn: 'স্নাতকোত্তর' },
  'degree.phd': { en: 'PhD', bn: 'পিএইচডি' },

  'funding.pick': { en: 'How is your study funded?', bn: 'আপনার পড়াশোনা কীভাবে তহবিলিত?' },
  'funding.fully_funded': { en: 'Fully funded', bn: 'সম্পূর্ণ তহবিল' },
  'funding.tuition_only': { en: 'Tuition only', bn: 'শুধু বেতন' },
  'funding.partial': { en: 'Partial', bn: 'আংশিক' },
  'funding.self_funded': { en: 'Self-funded', bn: 'স্ব-তহবিল' },

  'budget.label': { en: 'Budget (BDT)', bn: 'বাজেট (টাকা)' },
  'budget.hint': {
    en: 'A figure for your range. It never changes which facts exist, only how cost coverage is shown. The exchange-rate date is shown beside every BDT figure.',
    bn: 'আপনার পরিসরের একটি সংখ্যা। এটি কী তথ্য আছে তা বদলায় না, শুধু খরচ কভারেজ কীভাবে দেখানো হয়। প্রতিটি টাকার অঙ্কের পাশে বিনিময়-হারের তারিখ দেখানো হয়।',
  },

  'priorities.explain': {
    en: 'Set the weight of each dimension. There is no hidden score: these weights are shown on your results and drive the "why recommended" notes.',
    bn: 'প্রতিটি মাত্রার গুরুত্ব ঠিক করুন। কোনো লুকানো স্কোর নেই: এই গুরুত্ব আপনার ফলাফলে দেখানো হয় এবং "কেন সুপারিশ" নোট তৈরি করে।',
  },
  'priorities.cost': { en: 'Cost (tuition + living)', bn: 'খরচ (শিক্ষা বেতন + জীবনযাত্রা)' },
  'priorities.funding': { en: 'Funding', bn: 'তহবিল' },
  'priorities.career': { en: 'Career (subject pay)', bn: 'ক্যারিয়ার (বিষয়ভিত্তিক বেতন)' },
  'priorities.pathway': { en: 'Immigration pathway', bn: 'ইমিগ্রেশন পথ' },

  'results.title': { en: 'Criterion-by-criterion comparison', bn: 'মাপকাঠি অনুযায়ী তুলনা' },
  'results.noSame': {
    en: 'No single "best" country is declared. Comparison is shown per criterion, with weights you set.',
    bn: 'কোনো একক "সেরা" দেশ ঘোষণা করা হয় না। তুলনা প্রতি মাপকাঠিতে দেখানো হয়, আপনি যে গুরutta নির্ধারণ করেছেন সেগুলি দিয়ে।',
  },
  'results.evidence': { en: 'Evidence completeness', bn: 'প্রমাণ সম্পূর্ণতা' },
  'results.whyRecommended': { en: 'Why recommended', bn: 'কেন সুপারিশ করা হলো' },
  'results.whyExcluded': { en: 'Why excluded / risks', bn: 'কেন বাদ / ঝুঁকি' },
  'results.ranked': { en: 'Ranked (all essential criteria sourced)', bn: 'ক্রমিত (সব প্রয়োজনীয় মাপকাঠি প্রমাণিত)' },
  'results.notRanked': { en: 'Not enough data to rank', bn: 'ক্রম করতে পর্যাপ্ত তথ্য নেই' },
  'results.empty': {
    en: 'No country could be ranked for these choices yet. This is a data gap, not a judgement - see each country\'s missing evidence below.',
    bn: 'এই পছন্দগুলির জন্য কোনো দেশ এখনো ক্রমসজ্জা করা যায়নি। এটি একটি তথ্য ঘাটতি, বিচার নয় - নিচে প্রতিটি দেশের অনুপস্থিত প্রমাণ দেখুন।',
  },
  'insufficient': { en: 'Insufficient data', bn: 'পর্যাপ্ত তথ্য নেই' },
  'reverify': { en: 'Re-verify (stale/undated)', bn: 'পুনরায় যাচাই (পুরনো/তারিখহীন)' },
  'source': { en: 'Source', bn: 'সূত্র' },
  'checked': { en: 'Checked / as-of', bn: 'যাচাই / তা-পর্যন্ত' },
  'status': { en: 'Status', bn: 'অবস্থা' },
  'notLegal': {
    en: 'Informational only. Not legal, immigration, financial or admission advice. No admission, visa or citizenship outcome is predicted.',
    bn: 'শুধুমাত্র তথ্যভিত্তিক। আইনি, ইমিগ্রেশন, আর্থিক বা ভর্তির পরামর্শ নয়। কোনো ভর্তি, ভিসা বা নাগরিকত্ব ফলাফল পূর্বাভাস দেওয়া হয় না।',
  },

  'bdt.title': { en: 'BDT', bn: 'টাকা' },
  'bdt.original': { en: 'original', bn: 'মূল' },
  'bdt.rateDate': { en: 'rate date', bn: 'হারের তারিখ' },
  'bdt.unavailable': { en: 'BDT unavailable (no sourced rate)', bn: 'টাকা অনুপলব্ধ (প্রমাণিত হার নেই)' },

  'pathway.title': { en: 'Pathway (student visa to citizenship)', bn: 'পথ (শিক্ষার্থী ভিসা থেকে নাগরিকত্ব)' },
  'pathway.noStep': { en: 'Not sourced for this country', bn: 'এই দেশের জন্য প্রমাণিত নয়' },

  'whatif.title': { en: 'What-if', bn: 'কী- hypothetical' },

  'shortlist.save': { en: 'Save shortlist', bn: 'শর্টলিস্ট সংরক্ষণ' },
  'shortlist.share': { en: 'Share link', bn: 'লিঙ্ক শেয়ার' },
  'shortlist.pdf': { en: 'Export PDF', bn: 'পিডিএফ এক্সপোর্ট' },
  'shortlist.saved': { en: 'Shortlist saved on this device only (no personal data).', bn: 'শর্টলিস্ট শুধু এই ডিভাইসে সংরক্ষিত (কোনো ব্যক্তিগত তথ্য নেই)।' },
  'shortlist.shared': { en: 'Share link copied. It contains only your subject/degree/funding choices - no personal data.', bn: 'শেয়ার লিঙ্ক কপি হয়েছে। এতে শুধু আপনার বিষয়/ডিগ্রি/ফান্ডিং পছন্দ - কোনো ব্যক্তিগত তথ্য নেই।' },
  'shortlist.pdfNote': { en: 'Opened print view. Use your browser save-to-PDF. No personal data is added.', bn: 'প্রিন্ট ভিউ খোলা হয়েছে। ব্রাউজারে save-to-PDF ব্যবহার করুন। কোনো ব্যক্তিগত তথ্য যোগ হয় না।' },

  'state.loading': { en: 'Comparing countries...', bn: 'দেশ তুলনা করা হচ্ছে...' },
  'state.error': { en: 'Something went wrong loading results.', bn: 'ফলাফল লোড করার সময় কিছু ভুল হয়েছে।' },
  'state.offline': { en: 'You appear to be offline. Last results shown are cached locally.', bn: 'আপনি অফলাইনে আছেন। দেখানো শেষ ফলাফল স্থানীয়ভাবে সংরক্ষিত।' },
  'state.partial': { en: 'Some evidence is missing below and is marked "Insufficient data".', bn: 'নিচে কিছু প্রমাণ অনুপস্থিত এবং "পর্যাপ্ত তথ্য নেই" চিহ্নিত।' },
}

export default STRINGS
