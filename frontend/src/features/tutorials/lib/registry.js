/**
 * The tutorial registry — the single source of truth for Help Center content.
 *
 * Every user-facing feature on the site has exactly one entry here. Nothing in
 * this file renders and nothing imports React: it is data, so that a tutorial
 * can be reviewed without reading a component, and so that coverage can be
 * asserted by a test rather than assumed by a reader.
 *
 * ## Shape
 *
 * A tutorial is a plain object with the fields below. Each piece of *prose* is a
 * `{ en, bn }` pair, following the convention `features/journey/i18n/strings.js`
 * established: authored in both languages rather than translated at render time,
 * because a UI string and a three-paragraph explanation do not fail in the same
 * way and a machine translation of the latter is worse than none.
 *
 * | field | meaning |
 * |---|---|
 * | `id` | unique, stable, never reused after removal |
 * | `route` | the route this tutorial covers, exactly as declared in `App.jsx` |
 * | `navLabel` | short name for the feature, used in nav tiles and cross-links |
 * | `category` | one of the `category.*` ids in `i18n/strings.js` |
 * | `audience` | `public`, `auth` or `admin` |
 * | `status` | `enabled` or `disabled` — disabled features are not published |
 * | `goals` | ids from the `goal.*` vocabulary, used by the goal index |
 * | `purpose` | what the feature does |
 * | `whenToUse` | when a reader should reach for it |
 * | `steps` | ordered walkthrough; steps are real and follow the real UI |
 * | `fields` | what to type into each box, with a worked example |
 * | `interpretResult` | how to read what comes back |
 * | `mistakes` | `{ mistake, fix }` pairs drawn from real failure modes |
 * | `recovery` | how to get out of a bad state without losing work |
 * | `storage` | where the reader's information actually lives |
 * | `notGuarantee` | what the feature does not promise — never omitted |
 *
 * ## Rules this file keeps to
 *
 * 1. **No invented UI.** A step names a control that exists in the component
 *    named by `route`. If a page has no search box, its tutorial does not
 *    describe one.
 * 2. **No outcome claims.** `notGuarantee` is never omitted and never says the
 *    feature will get you admitted, awarded a scholarship, or granted a visa.
 * 3. **Disabled features are not published as available.** The consistency
 *    auditor's `status` is `disabled` and its tutorial is marked as such, so a
 *    reader is never told to visit a route that renders the not-found page.
 * 4. **Admin tutorials are marked admin-only** and are only listed to an admin
 *    reader, not shelved next to scholarship browsing.
 * 5. **Provider names, URLs and dates are never translated or softened.** A
 *    deadline or an official page is the provider's own, and approximating it
 *    here would be the tutorial contradicting the catalogue.
 */

/** The audience values, so a test and a filter agree on them. */
export const AUDIENCE = Object.freeze({
  PUBLIC: 'public',
  AUTH: 'auth',
  ADMIN: 'admin',
})

/** Whether a feature is reachable from the public site right now. */
export const FEATURE_STATUS = Object.freeze({
  ENABLED: 'enabled',
  DISABLED: 'disabled',
})

/**
 * The tutorial catalogue, in reading order.
 *
 * Order is the order of the categories in `i18n/strings.js` — discover, then
 * prepare, then write, then apply, then account — so the Help Center reads down
 * a student's actual path rather than by whatever the feature folder happened
 * to be called.
 */
export const TUTORIALS = Object.freeze([
  /* ── Discover ──────────────────────────────────────────────────── */

  {
    id: 'home',
    route: '/',
    navLabel: 'Home',
    category: 'discover',
    audience: AUDIENCE.PUBLIC,
    status: FEATURE_STATUS.ENABLED,
    goals: ['findScholarships', 'seeMyProgress'],
    purpose: {
      en: 'The front door. It shows how large the verified catalogue is right now, what an entry covers, and the quickest way into the scholarships you can actually apply for. Use it to get your bearings and to check the catalogue is alive.',
      bn: 'প্রথম দরজা। এখানে এখন যাচাই করা তালিকায় কতটি বৃত্তি আছে, একটি এন্ট্রিতে কী থাকে, এবং আপনি যেগুলিতে আবেদন করতে পারবেন সেগুলোতে পৌঁছานোর দ্রুততম পথ — সবই দেখানো হয়। আবেশ নিতে ও তালিকা সচল আছে কিনা দেখতে এটি ব্যবহার করুন।',
    },
    whenToUse: {
      en: 'When you first arrive and want to know what this site is for, and when you want a quick answer to "is the catalogue up to date?" before you start browsing.',
      bn: 'যখন আপনি প্রথম আসেন এবং জানতে চান এই সাইট কী জন্য, আর যখন ব্রাউজ করার আগে দ্রুত জানতে চান — তালিকা হালনাগাদ আছে কিনা।',
    },
    steps: [
      {
        title: { en: 'Read the headline numbers', bn: 'মুখ্য সংখ্যাগুলো পড়ুন' },
        body: {
          en: 'The figures near the top are counts from the published catalogue. They are the whole catalogue, not a sample you have filtered. If a number shows a dash instead, the count could not be loaded — see the mistakes section.',
          bn: 'উপরের দিকের সংখ্যাগুলো প্রকাশিত তালিকা থেকে আসা হিসাব। এটি পুরো তালিকা, আপনি যতগুলো ফিল্টার করেছেন তার নমুনা নয়। যদি বিন্দুর চিহ্ন দেখায়, তাহলে হিসাব লোড হয়নি — ভুলের অংশটি দেখুন।',
        },
      },
      {
        title: { en: 'Pick where to start', bn: 'কোথা থেকে শুরু করবেন বেছে নিন' },
        body: {
          en: 'The main action takes you to the catalogue with the filters in their default state. That is the right first move for almost everyone, because from there you can narrow by what applies to you.',
          bn: 'মূল বোতামটি আপনাকে ডিফল্ট অবস্থায় ফিল্টার সহ তালিকায় নিয়ে যায়। প্রায় সবাইয়ের জন্য এটিই সঠিক প্রথম পদক্ষেপ, কারণ সেখান থেকে আপনি নিজের অবস্থান অনুযায়ী সীমিত করতে পারবেন।',
        },
      },
      {
        title: { en: 'Check what a record contains', bn: 'একটি এন্ট্রিতে কী থাকে দেখুন' },
        body: {
          en: 'The page explains the fields a scholarship record carries and that each one links back to the provider own page. That link is the authority; nothing on this site replaces it.',
          bn: 'পেজটি বোঝায় একটি বৃত্তির এন্ট্রিতে কী ফিল্ড থাকে এবং প্রতিটি ফিল্ড সরাসরি সরবরাহকারীর নিজের পাতায় যেতে পারে। ওই লিঙ্কই কর্তৃত্ব; এই সাইটের কোনো কিছু তার বদলী নয়।',
        },
      },
    ],
    fields: [],
    interpretResult: {
      en: 'The counts tell you how much has been verified and how much is still excluded — closed, expired or quarantined records are deliberately not in the public count. A number that has not moved for a while is normal: the catalogue is refreshed on a schedule, not on every visit.',
      bn: 'হিসাবগুলো বলছে কতগুলো যাচাই হয়েছে আর কতগুলো এখনো বাদ দেওয়া হয়েছে — বন্ধ, মেয়াদোত্তীর্ণ বা স্বতঃস্ফূর্তভাবে বাদ দেওয়া রেকর্ড ইচ্ছাকৃতভাবে গণনায় নেই। সংখ্যা কিছুক্ষণ না বাড়লেই চলে: তালিকা সময়সূচি অনুযায়ী হালনাগাদ হয়, প্রতি ভিজিটে নয়।',
    },
    mistakes: [
      {
        mistake: { en: 'Reading the total as "everything that exists"', bn: 'মোট সংখ্যাকে "যা কিছু আছে সব" বলে ধরেছেন' },
        fix: {
          en: 'The total is the verified and publicly visible catalogue, not every scholarship in the world. A provider that publishes nothing usable is absent rather than counted wrongly.',
          bn: 'মোট সংখ্যাটি যাচাই করা ও প্রকাশ্যে দৃশ্যমান তালিকা, পৃথিবীর প্রতিটি বৃত্তি নয়। যে সরবরাহকারী ব্যবহারযোগ্য কিছু প্রকাশ করে না, সে ভুলভাবে গণনা নয় — বাদ পড়ে যায়।',
        },
      },
      {
        mistake: { en: 'Treating a dash as "zero scholarships"', bn: 'বিন্দুর চিহ্নকে "শূন্য বৃত্তি" বলে ধরেছেন' },
        fix: {
          en: 'A dash means the count was not retrieved. Reload once; if it stays, the catalogue is being read from a previously saved copy on this device and the page will say so.',
          bn: 'বিন্দুর চিহ্নের অর্থ হিসাব পাওয়া যায়নি। একবার রিলোড করুন; থেকে গেলে, তালিকা এখন ডিভাইসে আগে রাখা একটি কপি থেকে পড়া হচ্ছে এবং পেজটি সেটি জানাবে।',
        },
      },
    ],
    recovery: {
      en: 'Nothing on this page is written into, so there is nothing to recover. If it looks wrong, go straight to the Scholarships page — that is where the real filtering happens.',
      bn: 'এই পেজে কিছু লেখা হয় না, তাই ফেরানোর কিছু নেই। কিছু ভুল দেখলে সরাসরি Scholarships পাতায় যান — আসল ফিল্টারিং সেখানেই হয়।',
    },
    storage: {
      en: 'Nothing is stored from the home page. It reads a published snapshot of the catalogue and does not write anything about you.',
      bn: 'হোম পেজ থেকে কিছুই রাখা হয় না। এটি তালিকার একটি প্রকাশিত স্ন্যাপশট পড়ে এবং আপনার সম্পর্কে কিছু লেখে না।',
    },
    notGuarantee: {
      en: 'The home page does not predict whether you will qualify for anything, and the counts are not a promise that a listed scholarship is still open. Always open the scholarship own page before you rely on a deadline or a rule.',
      bn: 'হোম পেজ বারতায় না আপনি কোনো কিছুর যোগ্য হবেন কি না, আর হিসাব কোনো তালিকাভুক্ত বৃত্তি এখনো খোলা আছে এমন গ্যারান্টি নয়। কোনো শেষ সময় বা নিয়মের উপর নির্ভর করার আগে সবসময় বৃত্তিটির নিজের পাতা খুলুন।',
    },
  },

  {
    id: 'scholarships',
    route: '/scholarships',
    navLabel: 'Scholarships',
    category: 'discover',
    audience: AUDIENCE.PUBLIC,
    status: FEATURE_STATUS.ENABLED,
    goals: ['findScholarships'],
    purpose: {
      en: 'The catalogue. Every scholarship that is verified and currently visible is listed here with its filters, so you can go from the whole list down to the handful that plausibly fit you.',
      bn: 'তালিকা। যেসব বৃত্তি যাচাই হয়েছে এবং এখন দৃশ্যমান, সব এখানে ফিল্টার সহ তালিকাভুক্ত — যাতে পুরো তালিকা থেকে আপনি যেগুলোতে সম্ভবত যোগ্য, সেই অল্প কয়েকটিতে নামতে পারেন।',
    },
    whenToUse: {
      en: 'Whenever you want to see what is available, or when you have a specific country, degree or funding type in mind and want to narrow to it.',
      bn: 'যখন আপনি কী পাওয়া যায় দেখতে চান, অথবা আপনার মনে দেশ, ডিগ্রি বা অর্থায়নের কোনো নির্দিষ্ট ধরন আছে এবং তার মধ্যেই সীমিত করতে চান।',
    },
    steps: [
      {
        title: { en: 'Open the catalogue', bn: 'তালিকা খুলুন' },
        body: {
          en: 'Choose Scholarships in the top navigation. The page opens with every visible record and no filter applied, so the first number you see is the whole public catalogue.',
          bn: 'উপরের নেভিগেশনে Scholarships বেছে নিন। পাতা সব দৃশ্যমান রেকর্ড ও কোনো ছাঁকনি ছাড়া খোলে, তাই প্রথম সংখ্যাটি হলো পুরো প্রকাশ্য তালিকা।',
        },
      },
      {
        title: { en: 'Narrow with the filters', bn: 'ফিল্টার দিয়ে সীমিত করুন' },
        body: {
          en: 'Use the filter controls to reduce the list by country, level of study and funding type. Each one narrows the list; they combine, so applying two is narrower than either alone.',
          bn: 'ফিল্টার নিয়ন্ত্রণ দিয়ে দেশ, পড়ার স্তর ও অর্থায়নের ধরন অনুযায়ী তালিকা ছোট করুন। প্রতিটি তালিকা সংকুচিত করে এবং তারা একসঙ্গেও কাজ করে — তাই দুটো একসাথে প্রয়োগ করলে যেকোনো একটির চেয়ে সংকীর্ণ হয়।',
        },
      },
      {
        title: { en: 'Search by name if you know it', bn: 'নাম জানলে খুঁজুন' },
        body: {
          en: 'If you have a specific provider or programme in mind, type part of its name into the search box. The match is on words in the scholarship title, so a single distinctive word is usually enough.',
          bn: 'আপনার মনে কোনো নির্দিষ্ট সরবরাহকারী বা প্রোগ্রাম থাকলে, খোঁজার ঘরে তার নামের অংশ লিখুন। মিল হয় বৃত্তির শিরোনামের শব্দে, তাই একটি বিশেষ শব্দ সাধারণত যথেষ্ট।',
        },
      },
      {
        title: { en: 'Open one record', bn: 'একটি রেকর্ড খুলুন' },
        body: {
          en: 'Choose a card to open its full page. That page carries the detail the card cannot: the official link, the deadline as the provider words it, and what the record does and does not state.',
          bn: 'একটি কার্ড বেছে নিন তার পুরো পাতা খুলতে। সেই পাতায় থাকে কার্ডে থাকা না বস্তু: অফিশিয়াল লিঙ্ক, সরবরাহকারী নিজের ভাষায় লেখা শেষ সময়, এবং রেকর্ড কী বলছে ও কী বলছে না।',
        },
      },
    ],
    fields: [
      {
        name: { en: 'Search', bn: 'খোঁজ' },
        meaning: {
          en: 'Matches words in the scholarship title and the provider name. Leave it empty to see everything.',
          bn: 'বৃত্তির শিরোনাম ও সরবরাহকারীর নামের শব্দের সঙ্গে মেলে। সব দেখতে খালি রাখুন।',
        },
        example: {
          en: 'Typing "Helsinki" returns every record whose title or provider contains that word.',
          bn: '"Helsinki" লিখলে ওই শব্দটি যার শিরোনাম বা সরবরাহকারীর নামে আছে সব রেকর্ড ফিরে আসে।',
        },
      },
      {
        name: { en: 'Country', bn: 'দেশ' },
        meaning: {
          en: 'Where the scholarship is awarded, not where you live.',
          bn: 'বৃত্তিটি কোথায় দেওয়া হয়, আপনি কোথায় থাকেন তা নয়।',
        },
        example: { en: 'Choose "Finland" for a scholarship at a Finnish university.', bn: 'ফিনল্যান্ডের বিশ্ববিদ্যালয়ের বৃত্তির জন্য "Finland" বেছে নিন।' },
      },
      {
        name: { en: 'Level of study', bn: 'পড়ার স্তর' },
        meaning: {
          en: 'The degree the award funds — undergraduate, master or doctoral.',
          bn: 'পুরস্কারটি কোন ডিগ্রির জন্য — স্নাতক, মাস্টার বা ডক্টরেট।',
        },
        example: { en: 'A doctoral funding record is filtered out by choosing "Masters".', bn: '"Masters" বেছে নিলে ডক্টরাত অর্থায়ন রেকর্ড বাদ পড়ে।' },
      },
      {
        name: { en: 'Funding type', bn: 'অর্থায়নের ধরন' },
        meaning: {
          en: 'Whether the award is full, partial, a fee waiver or something else, as the provider states it.',
          bn: 'পুরস্কারটি পুরো, আংশিক, ফি মাফ, নাকি অন্য কিছু — সরবরাহকারী যেভাবে বলছেন।',
        },
        example: {
          en: 'A record marked as a partial award is not described as full, even if it is generous.',
          bn: 'আংশিক হিসেবে চিহ্নিত রেকর্ড পুরো বলা হয় না, উদার পর্যায়ে হোক কেন।',
        },
      },
    ],
    interpretResult: {
      en: 'The result is a list of records that satisfy the filters you set — nothing more. It is not a ranking and not a recommendation: a record appearing first is not one the site thinks you should apply for. The count shown is how many records match, and it changes as you filter.',
      bn: 'ফলাফল হলো আপনি যে ফিল্টার দিয়েছেন তা মেটে এমন রেকর্ডের তালিকা — এর বেশি কিছু নয়। এটি ক্রমবৈভব নয়, সুপারিশও নয়: যে রেকর্ড আগে আসে তা এই সাইটের মনে নেই যে আপনি সেটিতে আবেদন করবেন। দেখানো হিসাব হলো কত রেকর্ড মিলেছে, এবং ফিল্টার বদলালে সেটিও বদলায়।',
    },
    mistakes: [
      {
        mistake: { en: 'Applying every filter at once and finding nothing', bn: 'সব ফিল্টার একসঙ্গে প্রয়োগ করে কিছুই না পাওয়া' },
        fix: {
          en: 'Filters combine, so three filters can be narrower than any real scholarship. Clear the last one you added and look at what remains; then re-add it to a smaller result.',
          bn: 'ফিল্টার একসঙ্গে কাজ করে, তাই তিনটি ফিল্টার যেকোনো বাস্তব বৃত্তির চেয়ে সংকীর্ণ হতে পারে। শেষ যে টি যোগ করেছেন সেটি সরিয়ে বাকিগুলো দেখুন; তারপর ছোট ফলাফলে আবার যোগ করুন।',
        },
      },
      {
        mistake: { en: 'Searching for a word that is not in the title', bn: 'এমন শব্দ দিয়ে খোঁজা যা শিরোনামে নেই' },
        fix: {
          en: 'Search matches title and provider words, so a subject or a city may return nothing. Use the filters instead — they cover country, level and funding type.',
          bn: 'খোঁজ শিরোনাম ও সরবরাহকারীর শব্দে মেলে, তাই কোনো বিষয় বা শহরের নামে কিছুই না আসতে পারে। বদলে ফিল্টার ব্যবহার করুন — দেশ, স্তর ও অর্থায়নের ধরন সেখানে আছে।',
        },
      },
      {
        mistake: { en: 'Assuming a missing scholarship means it does not exist', bn: 'বৃত্তি অনুপস্থিত মানে নেই — এমনভাবেই ভাবছেন' },
        fix: {
          en: 'The catalogue holds verified, publicly visible records. Closed, expired or quarantined ones are deliberately excluded. Check the provider own site before concluding anything.',
          bn: 'তালিকায় আছে যাচাই করা, প্রকাশ্যভাবে দৃশ্যমান রেকর্ড। বন্ধ, মেয়াদোত্তীর্ণ বা স্বতঃস্ফূর্তভাবে বাদ দেওয়া রেকর্ড ইচ্ছাকৃতভাবে নেই। সিদ্ধান্তে আসার আগে সরবরাহকারীর নিজের সাইট দেখুন।',
        },
      },
    ],
    recovery: {
      en: 'Every filter is a single control: undo it individually, or reset the whole page by choosing Scholarships in the navigation again. Nothing you type here is saved, so there is no filter state to restore.',
      bn: 'প্রতিটি ফিল্টার একটি নিয়ন্ত্রণ: আলাদাভাবেই সরান, বা উপরের নেভিগেশনে আবার Scholarships বেছে পুরো পাতা রিসেট করুন। আপনি এখানে যা লিখেন তা রাখা হয় না, তাই ফিরানোর কোনো ফিল্টার অবস্থাও নেই।',
    },
    storage: {
      en: 'The catalogue is read from a published snapshot, so browsing works without an account. The filters themselves are not remembered when you leave the page.',
      bn: 'তালিকা একটি প্রকাশিত স্ন্যাপশট থেকে পড়া হয়, তাই অ্যাকাউন্ট ছাড়াই ব্রাউজ করা চলে। পাতা ছেড়ে দিলে ফিল্টারগুলো মনে রাখা হয় না।',
    },
    notGuarantee: {
      en: 'A record in the catalogue is not a statement that you qualify, and the list is not an endorsement of any provider. Eligibility is decided by the provider, and only the provider page is authoritative.',
      bn: 'তালিকার একটি রেকর্ড থেকে আপনার যোগ্যতা বলা যায় না, আর তালিকা কোনো সরবরাহকারীর সমর্থনও নয়। যোগ্যতা ঠিক করে সরবরাহকারী, এবং কেবল সরবরাহকারীর পাতাই কর্তৃত্বসম্মত।',
    },
  },

  {
    id: 'scholarship-details',
    route: '/scholarships/:id',
    navLabel: 'Scholarship details',
    category: 'discover',
    audience: AUDIENCE.PUBLIC,
    status: FEATURE_STATUS.ENABLED,
    goals: ['understandOne', 'knowWhatINeed'],
    purpose: {
      en: 'The full page for one scholarship. It gathers everything the record states — funding, deadlines, eligibility, how to apply — and links out to the provider page so you can check the original.',
      bn: 'একটি বৃত্তির সম্পূর্ণ পাতা। এটি রেকর্ডে যা কিছু আছে — অর্থায়ন, শেষ সময়, যোগ্যতা, কীভাবে আবেদন — সব একত্র করে এবং মূল আলাদা দেখতে সরবরাহকারীর পাতায় লিঙ্ক করে।',
    },
    whenToUse: {
      en: 'When you are seriously considering one scholarship and need the detail a card cannot hold, especially the deadline and the application route.',
      bn: 'যখন আপনি একটি বৃত্তি নিয়ে বাস্তবভাবেই ভাবছেন এবং কার্ডে থাকা না বস্তু দরকার — বিশেষ করে শেষ সময় ও আবেদনের পথ।',
    },
    steps: [
      {
        title: { en: 'Open the record from the catalogue', bn: 'তালিকা থেকে রেকর্ড খুলুন' },
        body: {
          en: 'Choose a card in the Scholarships list. The address in your browser gets a record id at the end, so you can bookmark it or come back to the same scholarship.',
          bn: 'Scholarships তালিকায় একটি কার্ড বেছে নিন। ব্রাউজারের ঠিকানার শেষে একটি রেকর্ড আইডি বসে, তাই এটি বুকমার্ক করতে বা একই বৃত্তিতে ফিরে আসতে পারেন।',
        },
      },
      {
        title: { en: 'Read the quick facts first', bn: 'প্রথমে দ্রুত তথ্য পড়ুন' },
        body: {
          en: 'The summary block carries the fields that usually matter most — level, funding type, country and the deadline. Read these before the longer sections.',
          bn: 'সারসংক্ষেপ অংশে থাকে সাধারণত সবচেয়ে গুরুত্বপূর্ণ ফিল্ড — স্তর, অর্থায়নের ধরন, দেশ ও শেষ সময়। দীর্ঘ অংশগুলোর আগে এগুলো পড়ুন।',
        },
      },
      {
        title: { en: 'Check the deadline wording exactly', bn: 'শেষ সময়ের ভাষা হুবহু দেখুন' },
        body: {
          en: 'The deadline is shown the way the provider words it. If it is rolling, annual, monthly or not stated, the page says so rather than inventing a date.',
          bn: 'শেষ সময় দেখানো হয় সরবরাহকারী যেভাবে ভাষ্য করেছেন। যদি তা rolling, বার্ষিক, মাসিক বা অপ্রকাশিত হয়, পাতা তা বলে দেয় — তারিখ বানিয়ে দেওয়া হয় না।',
        },
      },
      {
        title: { en: 'Open the official source', bn: 'অফিশিয়াল উৎস খুলুন' },
        body: {
          en: 'Every record links to the provider own page. Treat that link as the authority on eligibility, fees and deadlines; this page is a structured summary of it, not a replacement.',
          bn: 'প্রতিটি রেকর্ড সরবরাহকারীর নিজের পাতায় লিঙ্ক করে। যোগ্যতা, ফি ও শেষ সময়ে ওই লিঙ্কটিকে কর্তৃত্বসম্মত ধরুন; এই পাতা তার সুসজ্জিত সারসংক্ষেপ, বদলী নয়।',
        },
      },
    ],
    fields: [
      {
        name: { en: 'Section headings', bn: 'অনুচ্ছেদ শিরোনাম' },
        meaning: {
          en: 'Each block on the page covers one area of the application — funding, deadlines, how to apply, supervision.',
          bn: 'পাতার প্রতিটি অংশ আবেদনের একটি দিক কভার করে — অর্থায়ন, শেষ সময়, কীভাবে আবেদন করবেন, তত্ত্বাবধান।',
        },
        example: { en: 'Sections reveal as you scroll; the heading order follows reading order.', bn: 'স্ক্রল করলে অংশগুলি খোলে; শিরোনামের ক্রম পড়ার ক্রম মেনেই চলে।' },
      },
    ],
    interpretResult: {
      en: 'What the page shows is what the record states, and gaps are labelled as gaps. A field that reads "not stated" means the record does not carry it — it does not mean the prize has no such requirement. That distinction is the whole point of the page.',
      bn: 'পাতায় যা দেখানো হয় তা রেকর্ড যা বলছে, আর ফাঁকাগুলো ফাঁকা হিসেবে চিহ্নিত। "not stated" দেখানো ফিল্ড মানে রেকর্ডে সেটি নেই — পুরস্কারে এরূপ কোনো দাবি নেই বোঝায় না। এই পার্থক্যই পুরো পাতার মূল বিষয়।',
    },
    mistakes: [
      {
        mistake: { en: 'Reading "not stated" as "there is none"', bn: '"not stated" কে "কিছু নেই" বলা হচ্ছে' },
        fix: {
          en: 'Absence in the record is not absence in the requirement. Open the official source to see whether the provider states it there.',
          bn: 'রেকর্ডে অনুপস্থিতি মানে দাবিতে অনুপস্থিতি নয়। সরবরাহকারী সেখানে বলছে কি না দেখতে অফিশিয়াল উৎস খুলুন।',
        },
      },
      {
        mistake: { en: 'Planning around a rolling deadline as if it were a fixed date', bn: 'rolling শেষ সময়কে নির্দিষ্ট তারিখ হিসেবে ধরছেন' },
        fix: {
          en: 'If the deadline is rolling or annual, there is no single date to plan around. Work out how much notice you need and start well before the earliest plausible date.',
          bn: 'শেষ সময় rolling বা বার্ষিক হলে, পরিকল্পনার মতো একটি নির্দিষ্ট তারিখ নেই। আপনার কত দিন নোটিশ লাগে বের করুন এবং সম্ভাব্য সবচেয়ে আগম তারিখের অনেক আগেই শুরু করুন।',
        },
      },
    ],
    recovery: {
      en: 'If a record will not open, go back to the Scholarships list and open it again — the page reads the same published data, so a wrong address is the usual cause. Nothing on this page is written into.',
      bn: 'একটি রেকর্ড না খুললে Scholarships তালিকায় ফিরে আবার খুলুন — পাতা একই প্রকাশিত তথ্য পড়ে, তাই ভুল ঠিকানাই সাধারণ কারণ। এই পাতায় কিছু লেখা হয় না।',
    },
    storage: {
      en: 'Nothing is stored from this page. Opening a record does not add it to your saved list — that is a separate, deliberate action on the page.',
      bn: 'এই পাতা থেকে কিছু রাখা হয় না। একটি রেকর্ড খোলার সঙ্গে সেটি আপনার সেভ করা তালিকায় যোগ হয় না — এটি পাতার একটি আলাদা, ইচ্ছাকৃত কাজ।',
    },
    notGuarantee: {
      en: 'The page is a structured summary of a provider record. It does not verify that you are eligible, that the award is still open, or that applying will succeed. The provider decides all of those.',
      bn: 'পাতাটি একটি সরবরাহকারী রেকর্ডের সুসজ্জিত সারসংক্ষেপ। এটি যাচাই করে না যে আপনি যোগ্য, পুরস্কার এখনো খোলা, বা আবেদন সফল হবে। ওগুলো ঠিক করে সরবরাহকারী।',
    },
  },

  {
    id: 'countries',
    route: '/countries',
    navLabel: 'Countries',
    category: 'discover',
    audience: AUDIENCE.PUBLIC,
    status: FEATURE_STATUS.ENABLED,
    goals: ['findScholarships', 'planMoney'],
    purpose: {
      en: 'A per-country view of the catalogue. It shows how many verified scholarships are recorded for a country and what the published cost estimates are, so you can compare destinations before you commit to one.',
      bn: 'তালিকার প্রতি-দেশের দৃশ্য। এটি দেখায় কোনো দেশের জন্য কত যাচাই করা বৃত্তি রেকর্ড করা আছে এবং প্রকাশিত খরচের আনুমানিক কত, যাতে একটি দেশে প্রতিশ্রুতি দেওয়ার আগে গন্তব্য তুলনা করতে পারেন।',
    },
    whenToUse: {
      en: 'When you have not decided where to apply, or when you want a rough sense of what a country costs before looking at individual scholarships there.',
      bn: 'যখন আপনি কোথায় আবেদন করবেন ঠিক করেননি, বা ওই দেশের নির্দিষ্ট বৃত্তি দেখার আগে খরচের একটি মোটামুটি ধারণা নিতে চান।',
    },
    steps: [
      {
        title: { en: 'Open the Countries page', bn: 'Countries পাতা খুলেন' },
        body: {
          en: 'Choose Countries in the top navigation. Each country is listed with its scholarship count, so the ones with the most coverage are easiest to explore.',
          bn: 'উপরের নেভিগেশনে Countries বেছে নিন। প্রতিটি দেশ তার বৃত্তির হিসাব সহ তালিকাভুক্ত, তাই যেখানে কভারেজ বেশি সেগুলো ঘাঁটনিকর করতে সহজ।',
        },
      },
      {
        title: { en: 'Pick a country', bn: 'একটি দেশ বেছে নিন' },
        body: {
          en: 'Choose a country to see its own page. There you get the catalogue count for that country and the published cost figures, if any are recorded for it.',
          bn: 'একটি দেশ বেছে নিন তার নিজের পাতাটি দেখতে। সেখানে আপনি সেই দেশের তালিকা হিসাব ও প্রকাশিত খরচের তথ্য পাবেন — যদি কিছু রেকর্ড করা থাকে।',
        },
      },
      {
        title: { en: 'Read the cost estimate with its caveat', bn: 'খরচের আনুমানিক সহ সতর্কতা পড়েন' },
        body: {
          en: 'Cost figures are estimates drawn from published sources, not the live price of anything. They are a starting point for your own mathematics, not a quotation.',
          bn: 'খরচের তথ্য প্রকাশিত উৎস থেকে নেওয়া আনুমানিক, কোনো কিছুর চলমান দাম নয়। এটি আপনার নিজের হিসাব-নিকাশের শুরুর বিন্দু, কোনো উদ্ধৃতি নয়।',
        },
      },
    ],
    fields: [
      {
        name: { en: 'Scholarship count', bn: 'বৃত্তির হিসাব' },
        meaning: {
          en: 'How many verified records reference that country. It is not a count of scholarships you qualify for.',
          bn: 'কত যাচাই করা রেকর্ড ওই দেশ উল্লেখ করে। এটি আপনি যেগুলোর যোগ্য, তার হিসাব নয়।',
        },
        example: { en: 'A count of 12 means 12 verified records name that country.', bn: '১২ হিসাব মানে ১২টি যাচাই করা রেকর্ড ওই দেশের নাম নেয়।' },
      },
    ],
    interpretResult: {
      en: 'A high count means a lot of verified coverage, not that many awards are open right now. A country with no cost figures simply has none published in the record — that is a gap in the data, not a cheap place to study.',
      bn: 'বেশি হিসাব মানে অনেক যাচাই করা কভারেজ, বোঝায় না যে এখন অনেক পুরস্কার খোলা। যে দেশে খরচের কোনো তথ্য নেই, তার রেকর্ডে কিছুই প্রকাশ করা হয়নি — এটি তথ্যের একটি ফাঁক, নিরীহ পড়ার জায়গা নয়।',
    },
    mistakes: [
      {
        mistake: { en: 'Treating the estimate as your cost', bn: 'আনুমানিক কে নিজের খরচ ধরা হচ্ছে' },
        fix: {
          en: 'The published estimate is a general figure. Add your own tuition, travel, insurance and living costs, and check the country page for what the estimate covers.',
          bn: 'প্রকাশিত আনুমানিক একটি সাধারণ চিত্র। নিজের টিউশন, যাতায়াত, বীমা ও রহন-সহন খরচ যোগ করুন, আর আনুমানিকটি কী অন্তর্ভুক্ত করে দেশের পাতায় দেখুন।',
        },
      },
      {
        mistake: { en: 'Choosing a country by count alone', bn: 'কেવল হিসাব দেখে দেশ বেছে নেওয়া' },
        fix: {
          en: 'Use the count to decide where to look, then judge each scholarship on its own page. A country with three close matches beats one with thirty that do not fit.',
          bn: 'কোথায় দেখবেন তা ঠিক করতে হিসাব ব্যবহার করুন, তারপর প্রতিটি বৃত্তি তার নিজের পাতায় বিচার করুন। তিনটি ঘনিষ্ঠ মিলের দেশ ত্রিশটি না-মিলের দেশের চেয়ে ভালো।',
        },
      },
    ],
    recovery: {
      en: 'The page reads published data and writes nothing, so there is nothing to restore. If a country page is empty, go back to the list and choose another.',
      bn: 'পাতাটি প্রকাশিত তথ্য পড়ে ও কিছু লেখে না, তাই ফিরানোর কিছু নেই। কোনো দেশের পাতা খালি হলে তালিকায় ফিরে অন্যটি বেছে নিন।',
    },
    storage: {
      en: 'Nothing is stored. This page is read-only and works without an account.',
      bn: 'কিছুই রাখা হয় না। এটি একটি read-only পাতা এবং অ্যাকাউন্ট ছাড়াই চলে।',
    },
    notGuarantee: {
      en: 'The cost figures are estimates from published sources and are not the price you will pay. Nothing here confirms your eligibility, your visa, or that any award is open.',
      bn: 'খরচের তথ্য প্রকাশিত উৎস থেকে নেওয়া আনুমানিক এবং আপনি যত দেবেন তা নয়। এখানে কিছুই আপনার যোগ্যতা, ভিসা, বা কোনো পুরস্কার খোলা আছে — সেগুলো প্রকাশিত উৎস থেকে নেওয়া আনুমানিক এবং আপনি যত দেবেন তা নয়।',
    },
  },

  {
    id: 'match',
    route: '/match',
    navLabel: 'Match',
    category: 'discover',
    audience: AUDIENCE.PUBLIC,
    status: FEATURE_STATUS.ENABLED,
    goals: ['findScholarships', 'understandOne'],
    purpose: {
      en: 'A matching helper. You enter basic facts about yourself — country, level of study, subjects, grades — and the page returns which records in the catalogue fit those facts, with the reason each one was included.',
      bn: 'মিল খুঁজে পেতে একটি সহায়ক। আপনি নিজের সম্পর্কে মৌলিক তথ্য দেন — দেশ, পড়ার স্তর, বিষয়, গ্রেড — আর পাতা বলদেয় তালিকার কোন রেকর্ডে সেই তথ্য মেলে, প্রতিটি অন্তর্ভুক্ত করার কারণ সহ।',
    },
    whenToUse: {
      en: 'When the full catalogue is too large to scan and you want a plausible shortlist from what you already know about yourself.',
      bn: 'যখন পুরো তালিকা স্ক্যান করতে অনেক বড় এবং আপনি নিজের পরিচিত তথ্য থেকে একটি সম্ভাব্য ছোট তালিকা চান।',
    },
    steps: [
      {
        title: { en: 'Enter your own facts', bn: 'নিজের তথ্য দিন' },
        body: {
          en: 'Fill in the details of where you study, what level you are at, your subject area and your results. These are your own answers about yourself — the page does not look them up.',
          bn: 'আপনি কোথায় পড়েন, কোন স্তরে আছেন, বিষয় কী ও ফলাফল কী — তা পূরণ করুন। এগুলো আপনার নিজের উত্তর; পাতা এগুলো খুঁজে নেয় না।',
        },
      },
      {
        title: { en: 'Run the match', bn: 'মিল চালান' },
        body: {
          en: 'Choose the button that runs the match. The page then compares what you typed against every field the catalogue actually carries, and lists what fits.',
          bn: 'মিল চালানোর বোতাম বেছে নিন। পাতা তখন আপনার লেখার সঙ্গে তুলনা করে, এবং যা মেলে তা তালিকা করে।',
        },
      },
      {
        title: { en: 'Read the reason for each match', bn: 'প্রতিটি মিলের কারণ পড়ুন' },
        body: {
          en: 'Each result says which parts of your profile matched — and where a record does not state something, it says that too rather than assuming it.',
          bn: 'প্রতিটি ফলাফল বলদেয় আপনার প্রোফাইলের কোন অংশ মিলেছে — এবং কোন রেকর্ডে কিছু নেই, সেটিও বলদেয় ধরে নেওয়ার বদলে।',
        },
      },
    ],
    fields: [
      {
        name: { en: 'Country of study', bn: 'পড়ার দেশ' },
        meaning: {
          en: 'Where you study now, used to filter records that are restricted by home region.',
          bn: 'আপনি এখন কোথায় পড়েন; এটি নিজের অঞ্চল অনুযায়ী সীমিত রেকর্ড ছাঁকতে ব্যবহৃত হয়।',
        },
        example: { en: 'Choosing India narrows to records that do not exclude Indian applicants.', bn: 'India বেছে নিলে যেসব রেকর্ড ভারতীয় আবেদনকারী বাদ দেয় না সেগুলোই থাকে।' },
      },
      {
        name: { en: 'Level of study', bn: 'পড়ার স্তর' },
        meaning: { en: 'The level you want to apply for, matched against the level each award funds.', bn: 'আপনি কোন স্তরে আবেদন করবেন, প্রতিটি পুরস্কার কোন স্তর অর্থায়ন করে তার সঙ্গে মেলানো হয়।' },
        example: { en: 'A doctoral award is not returned when you choose "Masters".', bn: '"Masters" বেছে নিলে ডক্টরাত পুরস্কার ফিরে আসে না।' },
      },
      {
        name: { en: 'Subject area and results', bn: 'বিষয় ও ফলাফল' },
        meaning: { en: 'What you study and what you have achieved so far.', bn: 'আপনি কী পড়েন এবং এখন পর্যন্ত কী পেয়েছেন।' },
        example: { en: 'A record asking for a science background is only returned when your subject matches.', bn: 'বিজ্ঞানের পটভূমি চাওয়া রেকর্ড কেবল আপনার বিষয় মিললে ফিরে আসে।' },
      },
    ],
    interpretResult: {
      en: 'A match means the record does not contradict the facts you typed. It is not a decision that you qualify, and the page shows which requirements the record does not state, because those can only be resolved by the provider.',
      bn: 'একটি মিল মানে রেকর্ড আপনি দ到的 তথ্যের সঙ্গে সাংঘর্ষিক নয়। এটি সিদ্ধান্ত নয় যে আপনি যোগ্য, আর পাতা দেখায় কোন দাবিগুলো রেকর্ডে নেই — কারণ কেবল সরবরাহকারীই সেগুলো ঠিক করতে পারে।',
    },
    mistakes: [
      {
        mistake: { en: 'Assuming everything listed will accept you', bn: 'তালিকাভুক্ত সবই আপনাকে গ্রহণ করবে ধরে নেওয়া' },
        fix: {
          en: 'A match means "not excluded on what you typed", not "eligible". Read each award page and confirm every requirement there.',
          bn: 'একটি মিল মানে "যা লিখেছেন তার সঙ্গে বাদ দেওয়া হয়নি", "যোগ্য" নয়। প্রতিটি পুরস্কারের পাতা পড়ে ও সেখানকার প্রতিটি দাবি নিশ্চিত করুন।',
        },
      },
      {
        mistake: { en: 'Entering hopeful rather than accurate answers', bn: 'সঠিক নয়, প্রত্যাশিত উত্তর দেওয়া' },
        fix: {
          en: 'The match is only as good as what you type. Enter your real results — an accurate match that drops an option is safer than a wrong one that adds it.',
          bn: 'মিল কেবল আপনি যা দেন ততটাই ভালো। নিজের সত্যিকারের ফলাফল দিন — একটি বিকল্প ফেলে দেওয়া সঠিক মিল, যোগ করা ভুল মিলের চেয়ে নিরাপদ।',
        },
      },
      {
        mistake: { en: 'Reading the weights as a probability', bn: 'ওজনকে সম্ভাবনা বলা হচ্ছে' },
        fix: {
          en: 'The weights show which requirement drove the decision, not how likely you are to succeed. They are an audit trail, not a score.',
          bn: 'ওজন দেখায় কোন দাবি সিদ্ধান্ত চালিয়েছে, আপনি কত সফল হবেন তা নয়। এটি একটি নিরীক্ষার পথ, স্কোর নয়।',
        },
      },
    ],
    recovery: {
      en: 'Your entries are only on this page while you are on it. Reloading starts you fresh — change an answer and run the match again rather than trying to undo it.',
      bn: 'আপনার এন্ট্রিগুলো কেবল এই পাতায় থাকে, আপনি যতক্ষণ সেখানে আছেন। রিলোড করলে আবার শুরু হয় — পাল্টানোর চেষ্টার বদলে উত্তর বদল করে আবার মিল চালান।',
    },
    storage: {
      en: 'The match runs in your browser and the answers you type are not stored anywhere by this page. There is no account and no history.',
      bn: 'মিল আপনার ব্রাউজারে চলে ও আপনি যে উত্তর দেন তা এই পাতা কোথাও রাখে না। কোনো অ্যাকাউন্ট নেই, কোনো ইতিহাস নেই।',
    },
    notGuarantee: {
      en: 'The match is a filter over published records, not an assessment of your chances. It cannot tell you whether you will be admitted or funded — only the provider can.',
      bn: 'মিল হলো প্রকাশিত রেকর্ডের উপর একটি ছাঁকনি, আপনার সম্ভাবনার মূল্যায়ন নয়। এটি বলতে পারে না আপনি ভর্তি বা অর্থায়ন পাবেন কি না — কেবল সরবরাহকারী পারে।',
    },
  },

  {
    id: 'plan',
    route: '/plan',
    navLabel: 'Plan',
    category: 'prepare',
    audience: AUDIENCE.PUBLIC,
    status: FEATURE_STATUS.ENABLED,
    goals: ['trackDeadlines', 'prepareDocuments'],
    purpose: {
      en: 'A private planning workspace in your browser. You keep a checklist of what an application needs, a timeline of deadlines, notes on each scholarship and a backup of the whole thing. It is yours alone — nothing is synced.',
      bn: 'আপনার ব্রাউজারে একটি ব্যক্তিগত পরিকল্পনার কাজের জায়গা। আপনি একটি আবেদনে কী দরকার তার চেকলিস্ট, শেষ সময়ের সময়রেখা, প্রতি বৃত্তির নোট এবং সব কিছুর একটি ব্যাকআপ রাখেন। এটি কেবল আপনার — কিছুই সিঙ্ক হয় না।',
    },
    whenToUse: {
      en: 'When you have a shortlist and want to organise it — what to prepare, by when, and what you have already done.',
      bn: 'যখন আপনার একটি ছোট তালিকা আছে এবং সেটি সাজাতে চান — কী প্রস্তুত, কবে, আর কী আগে করার হয়েছে।',
    },
    steps: [
      {
        title: { en: 'Open Plan', bn: 'Plan খুলুন' },
        body: {
          en: 'Choose Plan in the navigation. It opens empty if you have never used it, with a clear place to start rather than a blank box.',
          bn: 'নেভিগেশনে Plan বেছে নিন। আগে কখনো না ব্যবহার করলে এটি খালি অবস্থায় খোলে, ফাঁকা ঘরের বদলে শুরু করার একটি স্পষ্ট জায়গা সহ।',
        },
      },
      {
        title: { en: 'Add what you need to do', bn: 'যা করতে হবে যোগ করুন' },
        body: {
          en: 'Use the checklist to record each task an application needs. Tick one as you finish it; there is no ordering enforced.',
          bn: 'চেকলিস্ট দিয়ে একটি আবেদনের প্রতিটি কাজ লিখে রাখুন। শেষ হলে একটি টিক দিন; কোনো ক্রম বাধ্যতামূলক নয়।',
        },
      },
      {
        title: { en: 'Record your deadlines', bn: 'শেষ সময় লিখে রাখুন' },
        body: {
          en: 'Add deadlines to the timeline so you can see what is coming. If you export them, the dates go with you in calendar form.',
          bn: 'সময়রেখায় শেষ সময় যোগ করুন যাতে সামনে আসছে কী তা দেখতে পান। রপ্তানি করলে তারিখগুলি ক্যালেন্ডার রূপে আপনার সঙ্গে যায়।',
        },
      },
      {
        title: { en: 'Take a backup before you clear anything', bn: 'কিছু মুছার আগে ব্যাকআপ নিন' },
        body: {
          en: 'Use Export to keep a copy of the whole workspace as a file. This is the only way to move it to another device, because nothing is synced.',
          bn: 'সম্পূর্ণ পরিকল্পনার একটি কপি রাখতে Export ব্যবহার করুন। এটিই অন্য ডিভাইসে সরানোর একমাত্র উপায়, কারণ কিছুই সিঙ্ক হয় না।',
        },
      },
    ],
    fields: [
      {
        name: { en: 'Checklist items', bn: 'চেকলিস্টের বস্তু' },
        meaning: { en: 'One line per task, in your own words.', bn: 'প্রতি কাজ একটি লাইন, নিজের ভাষায়।' },
        example: { en: '"Request the reference letter from Dr Nkemelu" is specific enough to act on.', bn: '"ড. এনকেমেলুর কাছ থেকে সুপারিশ চিঠি চাইতে" যথেষ্ট নির্দিষ্ট যে কাজ করা যায়।' },
      },
      {
        name: { en: 'Notes', bn: 'নোট' },
        meaning: { en: 'Free text you attach to a scholarship for your own reference later.', bn: 'পরে নিজের রেফারেন্সের জন্য একটি বৃত্তির সঙ্গে যুক্ত মুক্ত পাঠ।' },
        example: { en: '"Asked them about the deadline; they said rolling."', bn: '"তাদের শেষ সময় জানতে চেয়েছি; তারা বললো rolling।"' },
      },
    ],
    interpretResult: {
      en: 'The checklist is your own counting, nothing more. Ticking everything means you decided each task is done — it does not mean an application is submitted or accepted, and no provider is told anything.',
      bn: 'চেকলিস্টটি আপনার নিজের গণনা, এর বেশি কিছু নয়। সব টিক দেওয়ার অর্থ আপনি ঠিক করেছেন প্রতিটি কাজ শেষ — এটি বোঝায় না কোনো আবেদন জমা হয়েছে বা গৃহীত হয়েছে, আর কোনো সরবরাহকারীকে কিছু জানানো হয় না।',
    },
    mistakes: [
      {
        mistake: { en: 'Expecting the plan to follow you to a phone', bn: 'পরিকল্পনা ফোনে গেলে যাবে মনে করা' },
        fix: {
          en: 'Everything is in this browser on this device only. Use Export on one device and Import on another if you need to move it.',
          bn: 'সব কেবল এক ডিভাইসে এই ব্রাউজারে। এক জায়গায় Export ও অন্যটিতে Import ব্যবহার করুন।',
        },
      },
      {
        mistake: { en: 'Clearing the plan before exporting it', bn: 'রপ্তানি করার আগে পরিকল্পনা মুছে ফেলা' },
        fix: {
          en: 'Export first, always. Once you erase the browser storage there is no copy anywhere, and nothing here is recoverable from a server.',
          bn: 'সবসময় আগে রপ্তানি করুন। ব্রাউজারের স্টোরেজ মুছে ফেলার পর কোথাও কোনো কপি থাকে না, আর এখান থেকে কোনো সার্ভার থেকে কিছু ফেরানো যায় না।',
        },
      },
      {
        mistake: { en: 'Treating a checklist tick as an achievement', bn: 'চেকলিস্টের টিককে অর্জন ধরা' },
        fix: {
          en: 'Ticking a task records that you decided it is done. It is your own bookkeeping, not a submission and not a confirmation from anyone.',
          bn: 'একটি কাজে টিক দেওয়া রেকর্ড করে আপনি সেটি শেষ করেছি বলেছেন। এটি আপনার নিজের হিসাবরক্ষণ, কোনো জমা দেওয়া বা কারও নিশ্চিতকরণ নয়।',
        },
      },
    ],
    recovery: {
      en: 'Your entries stay in browser storage, so closing the tab does not lose them. If something looks wrong, check the page says the same thing the fields do before you re-export.',
      bn: 'আপনার এন্ট্রি ব্রাউজারের স্টোরেজে থাকে, তাই ট্যাব বন্ধ করলেও যায় না। কিছু ভুল দেখলে, আবার রপ্তানি করার আগে পাতাটি ফিল্ডের মতো একই কথা বলছে কি না দেখুন।',
    },
    storage: {
      en: 'All of it — checklist, notes, deadlines — is in this browser only, under the plan feature own storage key. There is no account, no server and no sync, and clearing the browser data deletes it. Use Export for a copy.',
      bn: 'সব কিছুই — চেকলিস্ট, নোট, শেষ সময় — কেবল এই ব্রাউজারে, plan ফিচারের নিজের স্টোরেজ কী-তে। কোনো অ্যাকাউন্ট নেই, কোনো সার্ভার নেই, কোনো সিঙ্ক নেই, আর ব্রাউজারের তথ্য মুছে ফেললে এটি মুছে যায়। কপির জন্য Export ব্যবহার করুন।',
    },
    notGuarantee: {
      en: 'The plan is a private planner, not a submission and not a reminder service. It cannot send you alerts, and it knows nothing about your actual deadlines except what you typed.',
      bn: 'পরিকল্পনা একটি ব্যক্তিগত পরিকল্পনাকারী, কোনো জমা দেওয়া বা স্মরণ সেবা নয়। এটি আপনাকে সতর্কতা পাঠাতে পারে না, আর আপনার লেখা ছাড়া এটি আপনার আসল শেষ সময় সম্পর্কে কিছু জানে না।',
    },
  },

  {
    id: 'saved',
    route: '/saved',
    navLabel: 'Saved',
    category: 'prepare',
    audience: AUDIENCE.PUBLIC,
    status: FEATURE_STATUS.ENABLED,
    goals: ['findScholarships', 'seeMyProgress'],
    purpose: {
      en: 'Your shortlist. You save a scholarship from its page and it appears here so you can come back to it later. Signed in, the list follows you; signed out, it lives in this browser only.',
      bn: 'আপনার ছোট তালিকা। একটি বৃত্তির পাতা থেকে সেটি সেভ করলে এখানে দেখায় যাতে পরে ফিরে আসতে পারেন। সাইন ইন থাকলে লিস্টটি আপনার সঙ্গে যায়; সাইন আউট থাকলে এটি কেবল এই ব্রাউজারে থাকে।',
    },
    whenToUse: {
      en: 'While browsing the catalogue and something is worth a second look, and later when you want the shortlist in one place.',
      bn: 'তালিকা ঘাঁটনির সময় কিছু দ্বিতীয়বার দেখার মতো লাগলে, আর পরে যখন ছোট তালিকা এক জায়গায় চান।',
    },
    steps: [
      {
        title: { en: 'Save from a scholarship page', bn: 'একটি বৃত্তির পাতা থেকে সেভ করুন' },
        body: {
          en: 'Open a scholarship and use its save action. The control confirms what it did, so you are not left guessing whether the save landed.',
          bn: 'একটি বৃত্বাতি খুলে তার সেভ কাজ ব্যবহার করুন। নিয়ন্ত্রণটি নিজেই নিশ্চিত করে যে কাজটি হয়েছে, তাই কল্পনা করতে হয় না।',
        },
      },
      {
        title: { en: 'Open Saved', bn: 'Saved খুলুন' },
        body: {
          en: 'Choose Saved in the navigation. Everything you saved is here, with the same detail you saw before.',
          bn: 'নেভিগেশনে Saved বেছে নিন। আপনি যা যা সেভ করেছেন সব এখানে, আগের মতোই বিস্তারিত সহ।',
        },
      },
      {
        title: { en: 'Remove one when it is not for you', bn: 'যুক্ত না হলে সরিয়ে দিন' },
        body: {
          en: 'Each saved item has its own remove control. It removes that one item only, and does not sign you out or clear anything else.',
          bn: 'প্রতিটি সেভ করা বস্তুর নিজের সরানোর নিয়ন্ত্রণ আছে। এটি কেবল ওই একটি বস্তু সরায়, আপনাকে সাইন আউট করে না বা অন্য কিছু মুছে ফেলে না।',
        },
      },
    ],
    fields: [
      {
        name: { en: 'The saved count in the navigation', bn: 'নেভিগেশনের সেভ করা হিসাব' },
        meaning: {
          en: 'How many scholarships are on your shortlist. It appears only when there is something to count.',
          bn: 'আপনার ছোট তালিকায় কত বৃত্তি আছে। কেবল গোনার কিছু থাকলে এটি দেখায়।',
        },
        example: { en: 'No number means an empty shortlist.', bn: 'কোনো সংখ্যা না মানে ছোট তালিকা খালি।' },
      },
    ],
    interpretResult: {
      en: 'This page is your own list, in the order saved. It is not a ranking and not a recommendation — removing something from it does not change anything about the scholarship itself.',
      bn: 'এই পাতাটি আপনার নিজের তালিকা, সেভ করার ক্রমে। এটি ক্রমবৈভব নয় বা সুপারিশ নয় — এখান থেকে কিছু সরিয়ে দেওয়ায় বৃত্তিটির নিজের সম্পর্কে কিছু বদলায় না।',
    },
    mistakes: [
      {
        mistake: { en: 'Saving while signed out and losing the list later', bn: 'সাইন আউট অবস্থায় সেঽ করে লিস্ট পরে হারানো' },
        fix: {
          en: 'Signed out, savings are held in this browser only and disappear if the browser data is cleared. Sign in first if you want the list to follow you.',
          bn: 'সাইন আউট অবস্থায়, সেভ করা কেবল এই ব্রাউজারে থাকে এবং ব্রাউজারের তথ্য মুছে ফেললে হারায়। লিস্টটি আপনার সঙ্গে যেতে চাইলে আগে সাইন ইন করুন।',
        },
      },
      {
        mistake: { en: 'Assuming a save is an application step', bn: 'একটি সেভকে আবেদনের ধাপ ধরা' },
        fix: {
          en: 'Saving is private bookkeeping. Applying is a separate action you take on the provider own page.',
          bn: 'সেঽ করা একটি ব্যক্তিগত হিসাবরক্ষণ। আবেদন করা একটি আলাদা কাজ যা আপনি সরবরাহকারীর নিজের পাতায় করেন।',
        },
      },
    ],
    recovery: {
      en: 'If a save does not appear, reload the page once: signed in it reads from your account, signed out it reads from this browser, and the page says which it is using. A removed item can be saved again from its page.',
      bn: 'একটি সেভ করা বৃত্তি না দেখালে, একবার পাতা রিলোড করুন: সাইন ইন থাকলে এটি আপনার অ্যাকাউন্ট থেকে, সাইন আউট থাকলে এই ব্রাউজার থেকে পড়ে, আর পাতা বলদেয় কোনটি ব্যবহার করছে। সরানো বস্তু তার পাতা থেকে আবার সেঽ করা যায়।',
    },
    storage: {
      en: 'Signed in, the list is held against your account on the server. Signed out, it is in this browser only under the saved-scholarships key. This page tells you which case you are in.',
      bn: 'সাইন ইন থাকলে লিস্টটি সার্ভারে আপনার অ্যাকাউন্টে রাখা হয়। সাইন আউট থাকলে এটি কেবল এই ব্রাউজারে, saved-scholarships কী-তে। এই পাতাটি বলদেয় কোন ক্ষেত্রে আছেন।',
    },
    notGuarantee: {
      en: 'Saving a scholarship does not register interest with a provider, does not reserve a place, and does not put you on a list for an award. It only keeps the record on your own shortlist.',
      bn: 'একটি বৃত্তি সেভ করা সরবরাহকারীর কাছে আগ্রহ নথিভুক্ত করে না, কোনো আসন সংরক্ষণ করে না, বা কোনো পুরস্কারের তালিকায় রাখে না। এটি কেবল রেকর্ডটি আপনার নিজের ছোট তালিকায় রাখে।',
    },
  },

  {
    id: 'compare',
    route: '/compare',
    navLabel: 'Compare',
    category: 'prepare',
    audience: AUDIENCE.PUBLIC,
    status: FEATURE_STATUS.ENABLED,
    goals: ['compareOptions'],
    purpose: {
      en: 'A side-by-side view of the scholarships you picked, so you can see the differences rather than remembering them. You add records from the catalogue and the page lines up the same fields next to each other.',
      bn: 'আপনার বাছাই করা বৃত্তিগুলোর পাশাপাশি দৃশ্য, যাতে পার্থক্যগুলো মনে রাখার বদলে দেখতে পান। আপনি তালিকা থেকে রেকর্ড যোগ করেন আর পাতা একই ফিল্ডগুলো পাশাপাশি সাজিয়ে দেখায়।',
    },
    whenToUse: {
      en: 'When you are choosing between two or three specific scholarships and want the funding, deadline and level laid out together.',
      bn: 'যখন আপনদুয়ি বা তিনটি নির্দিষ্ট বৃত্তির মধ্যে বেছে নিতে চান এবং অর্থায়ন, শেষ সময় ও স্তর একত্রে সাজানো দেখতে চান।',
    },
    steps: [
      {
        title: { en: 'Add scholarships to compare', bn: 'তুলনার জন্য বৃত্তি যোগ করুন' },
        body: {
          en: 'From the catalogue or a scholarship page, use the compare control on the records you are choosing between. The count in the navigation shows how many you have picked.',
          bn: 'তালিকা বা বৃত্তির পাতা থেকে, যেসব রেকর্ডের মধ্যে বেছে নিচ্ছেন সেগুলোর তুলনা নিয়ন্ত্রণ ব্যবহার করুন। নেভিগেশনের হিসাব দেখায় আপনি কতটি বেছেছেন।',
        },
      },
      {
        title: { en: 'Open Compare', bn: 'Compare খুলুন' },
        body: {
          en: 'Choose Compare in the navigation. The page shows your picked records side by side, with each row covering one field the catalogue actually carries.',
          bn: 'নেভিগেশনে Compare বেছে নেন। পাতাটি আপনার বাছাই করা রেকর্ড পাশাপাশি দেখায়, প্রতিটি সারিতে থাকে তালিকায় থাকা একই ফিল্ড।',
        },
      },
      {
        title: { en: 'Read down a column, then across', bn: 'প্রথমে একটি কল بهম নিচে, তারপর পাশে পড়ুন' },
        body: {
          en: 'Reading down a column gives you one scholarship in full; reading across a row compares the same field between them. Both directions are useful, and the second is the one you came for.',
          bn: 'একটি কলামে নিচে পড়লে একটি বৃত্তি পুরোপুরি পেতেন; একটি সারিতে পাশে পড়লে একই ফিল্ডের তুলনা হয়। দুটি দিকই কাজের, আর দ্বিতীয়টিই আপনি আসার কারণ।',
        },
      },
    ],
    fields: [
      {
        name: { en: 'The compare count in the navigation', bn: 'নেভিগেশনের তুলনা হিসাব' },
        meaning: { en: 'How many records are currently selected to be compared.', bn: 'এখন তুলনার জন্য কত রেকর্ড বেছে আছে।' },
        example: { en: 'A limit applies, so only the first few you picked are shown.', bn: 'একটি সীমা আছে, তাই আপনি যে প্রথম কয়েকটি বেছেছেন সেগুলোই দেখানো হয়।' },
      },
    ],
    interpretResult: {
      en: 'The table shows what each record states, field by field. A blank in a column means the record does not carry that field — not that the answer is no. That is a limit of the record, and the award page is where the answer lives.',
      bn: 'সারণিটি প্রতিটি রেকর্ড যা বলছে তা ফিল্ড অনুযায়ী দেখায়। একটি কলামে ফাঁকা মানে রেকর্ডে সেই ফিল্ড নেই — উত্তর না বলার নয়। এটি রেকর্ডের একটি সীমা, আর উত্তর থাকে পুরস্কারের পাতায়।',
    },
    mistakes: [
      {
        mistake: { en: 'Comparing records that carry different fields', bn: 'ভিন্ন ফিল্ডের রেকর্ড তুলনা করা' },
        fix: {
          en: 'A record with no deadline stated and one with a firm date are not the same comparison. Open each award page to fill in the gap before deciding.',
          bn: 'কোনো শেষ সময় না-বলার রেকর্ড আর একটি নির্দিষ্ট তারিখের রেকর্ড একই তুলনা নয়। সিদ্ধান্তে আসার আগে ফাঁকা পূরণ করতে প্রতিটি পুরস্কারের পাতা খুলুন।',
        },
      },
      {
        mistake: { en: 'Assuming the selection follows you across devices', bn: 'বাছাই অন্য ডিভাইসে যাবে আপনি ভাবছেন' },
        fix: {
          en: 'The selection is kept on this device only. Re-add the records if you open Compare somewhere else.',
          bn: 'বাছাই কেবল এই ডিভাইসে রাখা হয়। অন্য কোথাও Compare খুললে রেকর্ডগুলো আবার যোগ করুন।',
        },
      },
    ],
    recovery: {
      en: 'Remove any single record with its own control without clearing the rest. Clearing the selection does not affect anything you saved elsewhere.',
      bn: 'বাকিগুলো না মুছে যেকোনো একটি রেকর্ড তার নিজের নিয়ন্ত্রণ দিয়ে সরান। বাছাই মুছে ফেলার ফলে অন্য কোথাও সেভ করা কিছুতে প্রভাব পড়ে না।',
    },
    storage: {
      en: 'The selection is held on this device, in this browser, under the compare feature own key. It is not synced to an account.',
      bn: 'বাছাই কেবল এই ডিভাইসে, এই ব্রাউজারে, compare ফিচারের নিজের কী-তে রাখা হয়। এটি কোনো অ্যাকাউন্টে সিঙ্ক হয় না।',
    },
    notGuarantee: {
      en: 'Comparing two records does not tell you which one you are more likely to win. The page only lines up published facts; the decision on eligibility and award rests with each provider.',
      bn: 'দুটি রেকর্ড তুলনা করে বলে না কোনটি আপনি জেতার সম্ভাবনা বেশি। পাতা কেবল প্রকাশিত তথ্য সাজায়; যোগ্যতা ও পুরস্কারের সিদ্ধান্ত ঘাড় প্রতি সরবরাহকারীর কাছেই।',
    },
  },

  {
    id: 'statement',
    route: '/statement',
    navLabel: 'Statement',
    category: 'write',
    audience: AUDIENCE.PUBLIC,
    status: FEATURE_STATUS.ENABLED,
    goals: ['writeMyStatement', 'knowWhatINeed'],
    purpose: {
      en: 'A guided workspace for writing your own statement of purpose. It gives you each section in order with instructions on what to write and how to improve it, then runs plain checks over your own words — length, repetition, missing specifics and claims you should be able to back up.',
      bn: 'নিজের স্টেটমেন্ট অফ পারপাস লিখতে একটি নির্দেশিত কাজের জায়গা। এটি ছয়টি অনুচ্ছেদ ক্রম অনুযায়ী দেয় — প্রতিটিতে কী লিখবেন, কেন তা গুরুত্বপূর্ণ এবং কীভাবে উন্নত করবেন তা লেখা থাকে। এরপর আপনার নিজের লেখার উপর সরল পরীক্ষা চালায় — দৈর্ঘ্য, পুনরাবৃত্তি, অনুপস্থিত নির্দিষ্ট তথ্য, আর যেসব দাবি আপনি সমর্থন করতে পারবেন তা।',
    },
    whenToUse: {
      en: 'When you are drafting a statement and want structure plus a second pass over your own text before you send it anywhere.',
      bn: 'যখন আপনি স্টেটমেন্টের খসড়া করছেন এবং গঠন চান, সঙ্গে কোথাও পাঠানোর আগে নিজের লেখার উপর দ্বিতীয় পাস চান।',
    },
    steps: [
      {
        title: { en: 'Fill in what the statement is for', bn: 'স্টেটমেন্টটি কী জন্য তা পূরণ করুন' },
        body: {
          en: 'Enter the kind of application, the institution and the programme. If the provider gave you a prompt, paste it in — the workspace keeps it clearly marked as yours.',
          bn: 'আবেদনের ধরন, প্রতিষ্ঠান ও প্রোগ্রাম লিখুন। সরবরাহকারী কোনো নির্দেশনা দিয়ে থাকলে সেটি বসান — কর্মস্থান সেটি আপনার হিসেবে স্পষ্ট চিহ্নিত রেখে।',
        },
      },
      {
        title: { en: 'Write your background notes', bn: 'নিজের পটভূমির নোট লিখুন' },
        body: {
          en: 'Record your own academic background, projects, achievements and motivation in your own words. Nothing is suggested for you — this space is for facts you will draw on.',
          bn: 'নিজের শিক্ষাগত পটভূমি, প্রকল্প, অর্জন ও অনুপ্রেরণা নিজের ভাষায় লিখে রাখুন। আপনার জন্য কিছুই প্রস্তাব করা হয় না — এখান হলো এমন তথ্যের জায়গা যা আপনি ব্যবহার করবেন।',
        },
      },
      {
        title: { en: 'Write each section', bn: 'প্রতিটি অনুচ্ছেদ লিখুন' },
        body: {
          en: 'Work through the six sections in order, or pick any order. Each explains what to write, why it matters and how to improve it, with questions to answer first.',
          bn: 'ছয়টি অনুচ্ছেদ ক্রম অনুযায়ী করুন, বা যেকোনো ক্রমে বাছুন। প্রতিটি বোঝায় কী লিখবেন, কেন তা গুরুত্বপূর্ণ ও কীভাবে উন্নত করবেন, সঙ্গে আগে উত্তর দেওয়ার প্রশ্ন।',
        },
      },
      {
        title: { en: 'Read the review and answer the claim checks', bn: 'পর্যালোচনা পড়ে দাবির পরীক্ষায় উত্তর দিন' },
        body: {
          en: 'The review flags what it can see — and for anything that reads as a factual claim, it asks you to explain your basis or decide to take it out. It does not write the answer for you.',
          bn: 'পর্যালোচনা যা দেখতে পারে তা চিহ্নিত করে — আর যেসব বাক্য তথ্যগত দাবি মনে হয়, সেগুলোর জন্য আপনার ভিত্তি ব্যাখ্যা করতে বা সরাতে সিদ্ধান্ত নিতে বলদেয়। এটি আপনার জন্য উত্তর লেখে না।',
        },
      },
    ],
    fields: [
      {
        name: { en: 'Word limit and its source', bn: 'শব্দসীমা ও তার উৎস' },
        meaning: {
          en: 'The limit only counts as official if you also record where it came from. Without a source it is treated as a note to yourself.',
          bn: 'সীমাটি কেবল আপনি কোথা থেকে পেয়েছেন তা লিখলেই অফিশিয়াল হয়। উৎস না থাকলে সেটি নিজের নোট বলেই ধরা হয়।',
        },
        example: {
          en: '500 with "the provider guidelines page" is an official limit; 500 alone is not treated as one.',
          bn: '৫০০ — সঙ্গে "সরবরাহকারীর নির্দেশিকার পাতা" একটি অফিশিয়াল সীমা; কেবল ৫০০ তা নয়।',
        },
      },
      {
        name: { en: 'Section editors', bn: 'অনুচ্ছেদ সম্পাদক' },
        meaning: {
          en: 'One editor per section, with a live word count. There is no minimum you must hit.',
          bn: 'প্রতি অনুচ্ছেদে একটি সম্পাদক, সঙ্গে চলমান শব্দ গণনা। পূরণীয় কোনো ন্যূনতম নেই।',
        },
        example: { en: 'A short, complete section reads better than a long padded one.', bn: 'একটি সংক্ষিপ্ত, সম্পূর্ণ অনুচ্ছেদ দীর্ঘ ভরাট একের চেয়ে ভালো পড়ে।' },
      },
    ],
    interpretResult: {
      en: 'A finding is a question to ask yourself, not a verdict. The checks are deterministic — they look at what you wrote and name what they found. They are not a language model and they do not rate your writing.',
      bn: 'একটি পর্যবেক্ষণ নিজেকে জিজ্ঞাসা করার প্রশ্ন, রায় নয়। পরীক্ষাগুলো নির্ধারিত — যা লিখেছেন তা দেখে পাওয়া বস্তুকে নাম দেয়। এগুলি কোনো ভাষা মডেল নয় এবং আপনার লেখার মূল্যায়নও করে না।',
    },
    mistakes: [
      {
        mistake: { en: 'Treating the check list as a score', bn: 'পরীক্ষার তালিকাকে স্কোর ধরা' },
        fix: {
          en: 'Empty is not good and flagged is not a failure. The list shows what the rules found, nothing more.',
          bn: 'খালি মানে ভালো নয় আর চিহ্নিত মানে ব্যর্থ নয়। তালিকায় নিয়মে পাওয়া বস্তুই থাকে, এর বেশি কিছু নয়।',
        },
      },
      {
        mistake: { en: 'Confirming a claim you cannot back up', bn: 'যে দাবি সমর্থন করতে পারবেন না তা নিশ্চিত করা' },
        fix: {
          en: 'The claim step asks for your basis precisely so this does not happen. If you have nothing, take the claim out of your draft.',
          bn: 'দাবির ধাপ ঠিক এ কারণে আপনার ভিত্তি চায়। কিছু না থাকলে দাবিটি খসড়া থেকে সরিয়ে দিন।',
        },
      },
      {
        mistake: { en: 'Expecting the browser to remember it forever', bn: 'ব্রাউজার চিরকাল মনে রাখবে মনে করা' },
        fix: {
          en: 'Everything is in this browser only. Export a copy before clearing anything, because there is no server copy.',
          bn: 'সব কেবল এই ব্রাউজারে। কিছু মুছার আগে একটি কপি রপ্তানি করুন, কারণ কোনো সার্ভার কপি নেই।',
        },
      },
    ],
    recovery: {
      en: 'Your draft is saved as you type into this browser, and reloading keeps it. If a write is refused — private browsing can do this — the page says so rather than pretending it saved.',
      bn: 'আপনার খসড়া এই ব্রাউজারে লেখার সঙ্গে সঙ্গে সেঽ হয়, আর রিলোড করলেও থাকে। কোনো লেখা ফিরানো হলে — প্রাইভেট ব্রাউজিং এটা করতে পারে — সেঽ হয়েছে ভ nibা রেখে পাতাটি সেটি বুলদেয়।',
    },
    storage: {
      en: 'Everything — sections, notes, prompt, word limit, your claim answers — is in this browser only, under the statement feature own key. No server, no account, no sync. Export keeps a copy.',
      bn: 'সব কিছুই — অনুচ্ছেদ, নোট, নির্দেশনা, শব্দসীমা, আপনার দাবির উত্তর — কেবল এই ব্রাউজারে, statement ফিচারের নিজের কী-তে। কোনো সার্ভার নেই, কোনো অ্যাকাউন্ট নেই, কোনো সিঙ্ক নেই। কপি রাখতে রপ্তানি করুন।',
    },
    notGuarantee: {
      en: 'The checks are plain rules over your own words. They do not judge your chances, do not predict an admission or an award, and do not replace a human reader.',
      bn: 'পরীক্ষাগুলো আপনার নিজের লেখার উপর সরল নিয়ম। এগুলি আপনার সম্ভাবনা রায় করে না, কোনো ভর্তি বা পুরস্কার বারতা দেয় না, আর কোনো মানব পাঠকের বদলী নয়।',
    },
  },

  {
    id: 'applications',
    // Two routes share one workspace: the list, and one application.
    routes: ['/applications', '/applications/:applicationId'],
    navLabel: 'Applications',
    category: 'apply',
    audience: AUDIENCE.AUTH,
    status: FEATURE_STATUS.ENABLED,
    goals: ['prepareDocuments', 'seeMyProgress'],
    purpose: {
      en: 'Your application workspace. Each application gets its own checklist, requirement list, notes and progress, so you can see what is still outstanding for a specific scholarship you have decided to pursue.',
      bn: 'আপনার আবেদনের কর্মস্থান। প্রতিটি আবেদন পেলে নিজের চেকলিস্ট, দাবির তালিকা, নোট ও অগ্রগতি, যাতে আপনি যে নির্দিষ্ট বৃত্তিতে অগ্রসর হয়েছেন সেটির 무엇 এখনো বাকি দেখতে পারেন।',
    },
    whenToUse: {
      en: 'Once you have chosen a scholarship and need to track what its application actually requires.',
      bn: 'একবার আপনি একটি বৃত্তি বেছে নেয়েছেন এবং তার আবেদন আসলে কী দাবি করে তা দেখতে হলে।',
    },
    steps: [
      {
        title: { en: 'Sign in', bn: 'সাইন ইন করুন' },
        body: {
          en: 'The workspace needs an account, because applications are held against your account rather than in this browser. If you are not signed in you are sent to sign in first.',
          bn: 'কর্মস্থান একটি অ্যাকাউন্ট দরকার, কারণ আবেদনগুলো এই ব্রাউজারে নয় আপনার অ্যাকাউন্টে রাখা হয়। সাইন ইন না থাকলে আপনাকে আগে সাইন ইন করতে পাঠানো হয়।',
        },
      },
      {
        title: { en: 'Open an application', bn: 'একটি আবেদন খুলুন' },
        body: {
          en: 'Choose an application to see its checklist, requirements and notes. Each one is a separate case with its own progress.',
          bn: 'একটি আবেদন বাছে নেন তার চেকলিস্ট, দাবি ও নোট দেখতে। প্রতিটি একটি আলাদা মামলা নিজের অগ্রগতি সহ।',
        },
      },
      {
        title: { en: 'Work the checklist', bn: 'চেকলিস্ট কাজ করুন' },
        body: {
          en: 'Tick each requirement as you complete it. Each item says where the requirement came from, so you can see what is generic guidance and what is stated by the award.',
          bn: 'প্রতিটি দাবি শেষ হলে টিক দিন। প্রতিটি বস্তু বলদেয় দাবিটি কোথা থেকে এসেছে, যাকে করণ generalmente নির্দেশনা ও পুরস্কারের বলা বস্তু আলাদা করতে পারেন।',
        },
      },
    ],
    fields: [
      {
        name: { en: 'Requirement source', bn: 'দাবির উৎস' },
        meaning: {
          en: 'Where each checklist item came from: the award own requirements, your own profile, or general guidance.',
          bn: 'প্রতিটি চেকলিস্ট বস্তু কোথা থেকে এসেছে: পুরস্কারের নিজের দাবি, আপনার নিজের প্রোফাইল, বা সাধারণ নির্দেশনা।',
        },
        example: {
          en: 'An item marked as an award requirement is worth checking against the official page.',
          bn: 'পুরস্কারের দাবি হিসেবে চিহ্নিত বস্তু অফিশিয়াল পাতার বিপরীতে পরীক্ষা করার মতো মূল্যবান।',
        },
      },
    ],
    interpretResult: {
      en: 'Progress is your own completion of the tasks you set — it is not a submission and not an assessment by anyone. An item at zero weight does not move the number, which is deliberate.',
      bn: 'অগ্রগতি হলো আপনি যে কাজ শেষ করেছেন তা নিজেরই — এটি কোনো জমা দেওয়া বা কারো মূল্যায়ন নয়। শূন্য ওজনের বস্তু সংখ্যাটি নড়ায় না, যা ইচ্ছাকৃত।',
    },
    mistakes: [
      {
        mistake: { en: 'Assuming a tick tells the provider anything', bn: 'একটি টিক সরবরাহকারীকে কিছু জানানোর ধারণা' },
        fix: {
          en: 'Ticking is your own tracking. Applying happens on the provider own system, not here.',
          bn: 'টিক দেওয়া আপনার নিজের লক্ষ্যভেদী। আবেদন করা হয় সরবরাহকারীর নিজের সিস্টেমে, এখানে নয়।',
        },
      },
      {
        mistake: { en: 'Reading a requirement the record does not state', bn: 'এমন দাবি পড়া যা রেকর্ডে নেই' },
        fix: {
          en: 'The checklist marks its source for that reason. If an item is generic guidance rather than an award requirement, check the official page before relying on it.',
          bn: 'চেকলিস্ট ঠিক এ কারণে তার উৎস চিহ্নিত করে। কোনো বস্তু পুরস্কারের দাবি নয় সাধারণ নির্দেশনা হলে, এর উপর নির্ভর করার আগে অফিশিয়াল পাতা দেখুন।',
        },
      },
    ],
    recovery: {
      en: 'The workspace holds your state against your account, so it survives closing the browser. If you lose a tab, sign back in and continue from the workspace.',
      bn: 'কর্মস্থান আপনার অবস্থা অ্যাকাউন্টে রাখে, তাই ব্রাউজার বন্ধ করলেও থাকে। একটি ট্যাব হারালে, আবার সাইন ইন করে কর্মস্থান থেকে চালিয়ে যান।',
    },
    storage: {
      en: 'Applications are held on the server against your account, because they need to survive the device you are on. The requirement list itself is read from the catalogue record.',
      bn: 'আবেদনগুলো সার্ভারে আপনার অ্যাকাউন্টে রাখা হয়, কারণ সেগুলো আপনার যে ডিভাইসে থেকেন তার বাঁচতে হয়। দাবির তালিকাই তালিকার রেকর্ড থেকে পাঠ।',
    },
    notGuarantee: {
      en: 'The workspace does not submit your application, does not check your eligibility, and does not confirm anything with a provider. It is a tracker for your own steps.',
      bn: 'কর্মস্থান আপনার আবেদন জমা দেয় না, যোগ্যতা পরীক্ষা করে না, সরবরাহকারীর কাছে কিছু নিশ্চিত করে না। এটি আপনার নিজের ধাপের একটি অনুসরণী।',
    },
  },

  {
    id: 'dashboard',
    route: '/dashboard',
    navLabel: 'Dashboard',
    category: 'apply',
    audience: AUDIENCE.AUTH,
    status: FEATURE_STATUS.ENABLED,
    goals: ['seeMyProgress', 'trackDeadlines'],
    purpose: {
      en: 'One view of where you are: your applications, what needs attention, and what is coming up. It exists to answer "what should I do next?" without you opening each application in turn.',
      bn: 'আপনি কোথায় আছেন তার একটি দৃশ্য: আপনার আবেদন, যেগুলো যত্ন দরকার, আর কী আসছে। এটি প্রতিটি আবেদন খোলা ছাড়াই "এবার কী করব?" এর উত্তর দিতে থাকে।',
    },
    whenToUse: {
      en: 'When you are returning after a break and want the shortest route to the next thing that needs doing.',
      bn: 'যখন বিরতির পরে ফিরছেন এবং যা করতে হবে তার সংক্ষিপ্ত পথ চান।',
    },
    steps: [
      {
        title: { en: 'Sign in and open Dashboard', bn: 'সাইন ইন করে Dashboard খুলুন' },
        body: {
          en: 'The dashboard reads your account state from the server, so sign in first. If you are not signed in you are sent to the sign-in screen.',
          bn: 'ড্যাশবোর্ড সার্ভার থেকে আপনার অ্যাকাউন্ট অবস্থা পড়ে, তাই আগে সাইন ইন করুন। সাইন ইন না থাকলে আপনাকে সাইন-ইন পর্দায় পাঠানো হয়।',
        },
      },
      {
        title: { en: 'Read the panels in order', bn: 'প্যানেল ক্রম অনুযায়ী পড়ুন' },
        body: {
          en: 'The panels are ordered by what usually matters soonest: what needs attention, then what is coming up, then everything else.',
          bn: 'প্যানেলগুলো সাধারণত শীঘ্রই গুরুত্বপূর্ণ হয়ে যা দরকার, তারপর কী আসছে, তারপর বাকি সব।',
        },
      },
      {
        title: { en: 'Follow a panel into the work', bn: 'একটি প্যানেল থেকে কাজে যান' },
        body: {
          en: 'Each summary can be followed into the actual application or list it came from, so the dashboard is a starting point rather than a separate place to manage things.',
          bn: 'প্রতিটি সারসংক্ষেপের পরে আসল আবেদন বা তালিকায় যাওয়া যায়, তাই ড্যাশবোর্ড একটি শুরুর বিন্দু, কিছু পরিচালনার আলাদা জায়গা নয়।',
        },
      },
    ],
    fields: [],
    interpretResult: {
      en: 'The counts are what your own record contains, not a measure of your chances. A small number here is bookkeeping, not a warning.',
      bn: 'হিসাবগুলো আপনার নিজের রেকর্ডে যা আছে তা, আপনার সম্ভাবনার মাপ নয়। এখানে কম সংখ্যা হিসাবরক্ষণ, কোনো সতর্কতা নয়।',
    },
    mistakes: [
      {
        mistake: { en: 'Expecting an alert you have not asked for', bn: 'যে সতর্কতা চাননি তা আশা করা' },
        fix: {
          en: 'The dashboard shows state when you open it. It is not a reminder service and does not email you. Check it while you are actively applying.',
          bn: 'ড্যাশবোর্ড খোলার সময় অবস্থা দেখায়। এটি স্মরণ সেবা নয় এবং আপনাকে ই-মেইল করে না। সক্রিয়ভাবে আবেদন করার সময় এটি দেখুন।',
        },
      },
    ],
    recovery: {
      en: 'If a panel is empty when you expect it not to be, reload once — the page reads live account state. Sign in first, since the dashboard cannot show anything without it.',
      bn: 'কোনো প্যানেল তখন খালি দেখায় যখন আশা করছেন নয়, একবার রিলোড করুন — পাতা জীবন্ত অ্যাকাউن্ট অবস্থা পড়ে। আগে সাইন ইন করুন, কারণ এটি না হলে ড্যাশবোর্ড কিছু দেখাতে পারে না।',
    },
    storage: {
      en: 'The dashboard reads your applications and account state from the server, so it is the same on any device once you sign in.',
      bn: 'ড্যাশবোর্ড সার্ভার থেকে আপনার আবেদন ও অ্যাকাউন্ট অবস্থা পড়ে, তাই সাইন ইন করলে যেকোনো ডিভাইসে একই।',
    },
    notGuarantee: {
      en: 'The dashboard does not assess your applications, does not tell you your chance of success, and does not communicate with any provider on your behalf.',
      bn: 'ড্যাশবোর্ড আপনার আবেদন মূল্যায়ন করে না, সফলের সম্ভাবনা বলে না, এবং আপনার হয়ে কোনো সরবরাহকারীর সঙ্গে যোগাযোগ করে না।',
    },
  },

  {
    id: 'mentor',
    route: '/mentor',
    navLabel: 'Mentor',
    category: 'apply',
    audience: AUDIENCE.AUTH,
    status: FEATURE_STATUS.ENABLED,
    goals: ['understandOne', 'prepareDocuments'],
    purpose: {
      en: 'A reading surface over your own record: it explains what a scholarship asks for in plain terms, drawing on the same catalogue data you already have. It answers questions about a specific award using that award own published wording.',
      bn: 'নিজের রেকর্ডের উপর একটি পাঠের পাতা: এটি সহজ ভাষায় বোঝায় একটি বৃত্তি কী চাইছে, আপনি যেই তথ্য আগেই রাখেন সেটিই ব্যবহার করে। এটি নির্দিষ্ট পুরস্কারের নিজের প্রকাশিত ভাষা ব্যবহার করে সেই পুরস্কারের প্রশ্নের উত্তর দেয়।',
    },
    whenToUse: {
      en: 'When you are unsure what a particular scholarship is actually asking for, or what a part of an application means.',
      bn: 'যখন আপনি নিশ্চিত নন একটি নির্দিষ্ট বৃত্তি আসলে কী চাইছে, বা আবেদনের কোনো অংশ কী অর্থে?',
    },
    steps: [
      {
        title: { en: 'Sign in and open Mentor', bn: 'সাইন ইন করে Mentor খুলুন' },
        body: {
          en: 'It resolves your own access from the server session, so sign in first. If you are not signed in you are sent to sign in.',
          bn: 'এটি সার্ভারের সেশন থেকে আপনার নিজের অ্যাক্সেস ঠিক করে, তাই আগে সাইন ইন করুন। সাইন ইন না থাকলে আপনাকে আগে সাইন ইন করতে পাঠানো হয়।',
        },
      },
      {
        title: { en: 'Pick the award you are asking about', bn: 'যে পুরস্কার সম্পর্কে জানতে চান সেটি বাছেন!' },
        body: {
          en: 'Choose the scholarship you want help with from your own list, so the answer is about that record rather than about scholarships in general.',
          bn: 'নিজের তালিকা থেকে যে বৃত্তি সম্পর্কে সহায়তা চান বাছুন, যেন উত্তর সেই রেকর্ড সম্পর্কে হয় — বৃত্তি সম্পর্কে সাধারণভাবে নয়।',
        },
      },
      {
        title: { en: 'Read the answer and follow the source', bn: 'উত্তর পড়ে উৎস অনুসরণ করুন' },
        body: {
          en: 'Each answer points back to the wording it came from. If the answer does not cite anything, treat it as a summary and go to the award page.',
          bn: 'প্রতিটি উত্তর যে ভাষা থেকে এসেছে তা দেখায়। উত্তর কিছুই উদ্ধৃত না করলে, সেটি সারসংক্ষেপ ধরেন ও পুরস্কারের পাতায় যান।',
        },
      },
    ],
    fields: [],
    interpretResult: {
      en: 'The answer is an explanation of published information, not advice on what you should personally do. Where the record does not state something, the answer says so instead of guessing.',
      bn: 'উত্তরটি প্রকাশিত তথ্যের ব্যাখ্যা, আপনি ব্যক্তিগতভাবে কী করা উচিত তার পরামর্শ নয়। রেকর্ডে কিছু না থাকলে, উত্তর তা বলে দেয় অনুমানের বদলে।',
    },
    mistakes: [
      {
        mistake: { en: 'Treating an explanation as a decision', bn: 'একটি ব্যাখ্যাকে সিদ্ধান্ত ধরা' },
        fix: {
          en: 'The page explains what a record says. Deciding whether to apply is yours, and every rule the provider set is decided by the provider.',
          bn: 'পাতাটি রেকর্ডে যা আছে তা বোঝায়। আবেদন করবেন কি না সিদ্ধান্ত আপনার, আর সরবরাহকারী যে নিয়ম করেছে তা ঠিক করে সরবরাহকারী।',
        },
      },
      {
        mistake: { en: 'Asking about an award you have not saved', bn: 'যে পুরস্কার সেঽ করেননি তার সম্পর্কে জানতে চাওয়া' },
        fix: {
          en: 'Start from your saved list. If a scholarship is not on it, open it from the catalogue first.',
          bn: 'নিজের সেভ করা তালিকা থেকে শুরু করুন। কোনো বৃত্তি সেখানে না থাকলে, তালিকা থেকে আগে খুলুন।',
        },
      },
    ],
    recovery: {
      en: 'If an answer looks wrong for the award you picked, re-open the award and read the original wording. Your own list is unchanged by anything you do here.',
      bn: 'আপনি বাছাই করা পুরস্কারের জন্য কোনো উত্তর ভুল দেখালে, পুরস্কার আবার খুলে মূল ভাষা পড়ুন। আপনার নিজের তালিকায় এখানে কিছু आपল করলে বদলায় না।',
    },
    storage: {
      en: 'It reads from your account and the catalogue. Nothing you read here is added to the catalogue and nothing you ask is kept as part of your record.',
      bn: 'এটি আপনার অ্যাকাউন্ট ও তালিকা থেকে পড়ে। এখানে আপনি যা পড়েছেন তা তালিকায় যোগ হয় না, আর আপনি যা জানতে চান তা আপনার রেকর্ডের অংশ হিসেবে রাখা হয় না।',
    },
    notGuarantee: {
      en: 'The reading page is not advice and not an assessment of your chances. It explains published information, and it does not predict an admission or an award.',
      bn: 'পড়ার পাতাটি পরামর্শ নয়, আপনার সম্ভাবনার মূল্যায়নও নয়। এটি প্রকাশিত তথ্য বোঝায়, আর কোনো ভর্তি বা পুরস্কার বারতা দেয় না।',
    },
  },

  {
    id: 'bangladesh-journey',
    // The bare path for a fresh visit, and the step segment for a deep link.
    routes: ['/bangladesh-journey', '/bangladesh-journey/:stepId'],
    navLabel: 'BD Journey',
    category: 'prepare',
    audience: AUDIENCE.PUBLIC,
    status: FEATURE_STATUS.ENABLED,
    // This feature has its own i18n; the tutorial points at its own language
    // control rather than duplicating it.
    goals: ['learnBangladesh', 'planMoney', 'prepareDocuments', 'trackDeadlines'],
    purpose: {
      en: 'A step-by-step workspace for applicants applying from Bangladesh. Seven steps cover finding scholarships, eligibility readiness, documents, a timeline, cost planning in taka, official sources, and what happens after an offer.',
      bn: 'বাংলাদেশ থেকে আবেদনকারীদের জন্য একটি ধাপে-ধাপে কর্মস্থান। সাতটি ধাপে আছে বৃত্তি খোঁজা, যোগ্যতার প্রস্তুতি, কাগজপত্র, সময়রেখা, টাকায় খরচের পরিকল্পনা, অফিশিয়াল উৎস, আর অফারের পরে কী হয়।',
    },
    whenToUse: {
      en: 'When you are applying from Bangladesh and want the whole path in one place, in Bangla or English.',
      bn: 'যখন আপনি বাংলাদেশ থেকে আবেদন করছেন এবং পুরো পথ এক জায়গায় চান, বাংলা বা ইংরেজিতে।',
    },
    steps: [
      {
        title: { en: 'Pick your language', bn: 'নিজের ভাষা বাছুন' },
        body: {
          en: 'The journey has its own language control: Bangla, English, or both at once with Bangla first. Choose it before you start reading, and change it any time.',
          bn: 'জার্নির নিজের ভাষার নিয়ন্ত্রণ আছে: বাংলা, ইংরেজি, বা দুটোই একসাথে — বাংলা আগে। পড়া শুরুর আগে বাছুন, আর কোনো সময় বদলান।',
        },
      },
      {
        title: { en: 'Work through the seven steps in order', bn: 'সাতটি ধাপ ক্রম অনুযায়ী করুন' },
        body: {
          en: 'Each step has its own workspace. They are ordered as a real path, and the page shows your overall completion.',
          bn: 'প্রতিটি ধাপে নিজের কর্মস্থান আছে। সেগুলো একটি বাস্তব পথ হিসেবে সাজানো, আর পাতা আপনার সামগ্রিক সম্পূর্ণতা দেখায়।',
        },
      },
      {
        title: { en: 'Keep taka figures as your own estimates', bn: 'টাকার হিসাব নিজের আনুমানিক হিসেবে রাখুন' },
        body: {
          en: 'The cost step lets you plan in taka and marks your figures as estimates you entered. It is arithmetic over your own numbers, not a quotation from anyone.',
          bn: 'খরচের ধাপে আপনি টাকায় পরিকল্পনা করতে পারেন এবং আপনার হিসাবগুলোকে আপনি দেওয়া আনুমানিক হিসেবে চিহ্নিত করবদেন। এটি আপনার নিজের সংখ্যার উপর হিসাব, কোনো উদ্ধৃতি নয়।',
        },
      },
      {
        title: { en: 'Use the step links to go deeper', bn: 'ধাপের লিঙ্ক দিয়ে গভীরে যান' },
        body: {
          en: 'Each journey step can be linked to directly, so a step someone sends you opens on that step rather than the beginning.',
          bn: 'প্রতিটি জার্নির সরাসরি ধাপে লিঙ্ক করা যায়, তাই কেউ পাঠালে সেই ধাপে খোলে — শুরুতে নয়।',
        },
      },
    ],
    fields: [
      {
        name: { en: 'Step workspaces', bn: 'ধাপের কর্মস্থান' },
        meaning: { en: 'Each step is its own form and list.', bn: 'প্রতিটি ধাপ নিজের ফরম ও তালিকা।' },
        example: { en: 'Find & Explore, Eligibility, Documents, Timeline, Costs, Sources, Departure.', bn: 'বৃত্তি খোঁজা, যোগ্যতা, কাগজপত্র, সময়রেখা, খরচ, উৎস, ভ্রমণের পর।' },
      },
    ],
    interpretResult: {
      en: 'Completion is your own bookkeeping, not anything anyone else measures. A step can be complete and still not mean you have applied.',
      bn: 'সম্পূর্ণতা আপনার নিজের হিসাবরক্ষণ, কারো মাপ নয়। একটি ধাপ সম্পূর্ণ হতে পারে তার মানে আপনি আবেদন করেছেন নয়।',
    },
    mistakes: [
      {
        mistake: { en: 'Expecting it to confirm your eligibility', bn: 'এটি আপনার যোগ্যতা নিশ্চিত করবে মনে করা' },
        fix: {
          en: 'The journey helps you organise your own information. Only the provider decides whether you qualify.',
          bn: 'জার্নি আপনাকে নিজের তথ্য সাজাতে করে। আপনি যোগ্য কি না কেবল সরবরাহকারী ঠিক করে।',
        },
      },
      {
        mistake: { en: 'Assuming cost figures are live prices', bn: 'খরচের হিসাব চলমান দাম ধরা' },
        fix: {
          en: 'Every number is your own estimate. Confirm anything real against the provider or the embassy.',
          bn: 'প্রতিটি সংখ্যা আপনার নিজের আনুমানিক। কোনো বাস্তব কিছু সরবরাহকারী বা দূতাবাসের বিপরীতে নিশ্চিত করুন।',
        },
      },
    ],
    recovery: {
      en: 'The journey stores everything in this browser with its own reset, which clears only the journey keys and nothing else. Export before you reset if you want a copy.',
      bn: 'জার্নি সব কিছু এই ব্রাউজারে নিজের রিসেট সহ রাখে, যা কেবল জার্নির কী মুছে ফেলে — অন্য কিছু নয়। কপি চাইলে রিসেট করার আগে রপ্তানি করুন।',
    },
    storage: {
      en: 'Everything you enter is in this browser only, under the journey own storage key. Nothing is uploaded and progress does not follow you to another device.',
      bn: 'আপনি যা লিখেন সব কেবল এই ব্রাউজারে, জার্ণির নিজের স্টোরেজ কী-তে। কিছুই আপলোড হয় না এবং অগ্রগতি অন্য ডিভাইসে যায় না।',
    },
    notGuarantee: {
      en: 'The journey is an organiser. It cannot tell you whether you qualify, whether you will be admitted, whether an award will be given, or whether a visa will be granted. Only the university, provider, authority or embassy decides those.',
      bn: 'জার্নি একটি সাজানোর জায়গা। এটি বলতে পারে না আপনি যোগ্য কি না, ভর্তি হবেন কি না, পুরস্কার পাবেন কি না, বা ভিসা দেওয়া হবে কি না। ওগুলো ঠিক করে কেবল বিশ্ববিদ্যালয়, সরবরাহকারী, কর্তৃত্ব বা দূতাবাস।',
    },
  },

  {
    id: 'account',
    route: '/login',
    // Two routes share one flow, so the audit below lists both.
    routes: ['/login', '/register'],
    navLabel: 'Account',
    category: 'account',
    audience: AUDIENCE.PUBLIC,
    status: FEATURE_STATUS.ENABLED,
    goals: ['seeMyProgress'],
    purpose: {
      en: 'Signing in and creating an account. An account is what lets your applications and saved list follow you across devices, because the browser-only features cannot.',
      bn: 'সাইন ইন করা ও অ্যাকাউন্ট করা। একটি অ্যাকাউন্ট বেশানান্দাক্তি আপনার আবেদন ও সেভ করা তালিকাকে ডিভাইস জুড়ে যেতে দেয়, কারণ ব্রাউজারে-মাত্র ফিচার তা করতে পারে না।',
    },
    whenToUse: {
      en: 'Before you start tracking applications, so the work is held against your account rather than one browser.',
      bn: 'আবেদন অনুসরণ শুরুর আগে, কাজ আপনার অ্যাকাউন্টে রাখা হয় — একটি ব্রাউজারে নয়।',
    },
    steps: [
      {
        title: { en: 'Choose Sign in or Register', bn: 'সাইন ইন বা রেজিস্টার বাছুন' },
        body: {
          en: 'Sign in if you already have an account; Register if you do not. Both open the same form with the mode chosen for you.',
          bn: 'অ্যাকাউন্ট থাকলে সাইন ইন; না থাকলে রেজিস্টার। দুটোই একই ফরম খোলে, আপনার জন্য বেছে দেয়া মোডে ছাড়া।',
        },
      },
      {
        title: { en: 'Complete the form', bn: 'ফরম পূরণ করুন' },
        body: {
          en: 'Enter the details the form asks for. Validation messages tell you what a field needs, so fix what it names rather than guessing.',
          bn: 'ফরম যে তথ্য চায় তা দিন। যাচাই বার্তা বলদেয় একটি ফিল্ডে কী দরকার, তাই মনে হচ্ছে নয় দরকার যা বলছে তায় ঠিক করুন।',
        },
      },
      {
        title: { en: 'Return to what you were doing', bn: 'যা করছিলেন সেখানে ফিরুন' },
        body: {
          en: 'Once signed in, the dashboard and your applications become available. Nothing you did before signing in is lost.',
          bn: 'সাইন ইন করলে ড্যাশবোর্ড ও আপনার আবেদন পেতে পারেন। সাইন ইন করার আগে যা করেছেন কিছুই যায় না।',
        },
      },
    ],
    fields: [
      {
        name: { en: 'Credentials', bn: 'প্রবেশাধিকার' },
        meaning: { en: 'Your email as the identifier, plus the password you chose.', bn: 'চিহ্নকারী হিসেবে আপনার ই-মেইল, সঙ্গে আপনি বেছে নেওয়া পাসওয়ার্ড।' },
        example: { en: 'Register stores an account; the site never emails you unsolicited.', bn: 'রেজিস্টার একটি অ্যাকাউন্ট রাখে; সাইট আপনাকে অনুরোধহীন ই-মেইল করে না।' },
      },
    ],
    interpretResult: {
      en: 'A successful sign-in changes what the navigation offers — Dashboard replaces the sign-in link, because it is now the useful destination.',
      bn: 'সফল সাইন ইন নেভিগেশন যা দেয় তা বদলায় — সাইন-ইন লিঙ্কের জায়গায় Dashboard বসলে, কারণ এখন এটিই কাজের গন্তব্য।',
    },
    mistakes: [
      {
        mistake: { en: 'Expecting account features while signed out', bn: 'সাইন আউট থাকতে অ্যাকাউন্ট ফিচার আশা করা' },
        fix: {
          en: 'Applications, the dashboard and the mentor all need an account. Sign in first; the pages will send you.',
          bn: 'আবেদন, ড্যাশবোর্ড ও মেন্টর সব অ্যাকাউন্ট দরকার। আগে সাইন ইন করুন; পাতাগুলো আপনাকে পাঠিয়ে দেবে।',
        },
      },
      {
        mistake: { en: 'Confusing the browser-only workspaces with account features', bn: 'ব্রাউজারে-মাত্র কর্মস্থানকে অ্যাকাউন্ট ফিচার মনে করা' },
        fix: {
          en: 'Plan and Statement are deliberately in your browser only. An account does not sync them; use their export instead.',
          bn: 'Plan ও Statement ইচ্ছাকৃতভাবে কেবল আপনার ব্রাউজারে। একটি অ্যাকাউন্ট সেগুলো সিঙ্ক করে না; বদলে তাদের রপ্তানি ব্যবহার করুন।',
        },
      },
    ],
    recovery: {
      en: 'The sign-in state is resolved by the server. If it looks stuck, reload once; if the link still says Sign in after you signed in, the session did not carry.',
      bn: 'সাইন-ইন অবস্থা সার্ভার ঠিক করে। আটকে আছে দেখালে, একবার রিলোড করুন; সাইন ইন করার পরেও লিঙ্ক Sign in বললে, সেশনটি বহন হয়নি।',
    },
    storage: {
      en: 'Your automatic state is held against your account on the server. This page itself stores nothing extra.',
      bn: 'আপনার স্বয়ংক্রিয় অবস্থা সার্ভারে আপনার অ্যাকাউন্টে রাখা হয়। এই পাতেটি নিজে কিছু অতিরিক্ত রাখে না।',
    },
    notGuarantee: {
      en: 'Having an account does not affect your eligibility for anything. It stores your own information, and nothing more.',
      bn: 'একটি অ্যাকাউন্ট থাকলে কোনো কিছুর আপনার যোগ্যতা প্রভাবিত হয় না। এটি আপনার নিজের তথ্য রাখে, এর বেশি কিছু নয়।',
    },
  },

  {
    id: 'admin',
    route: '/admin',
    routes: ['/admin', '/admin/verification', '/admin/scholarships'],
    navLabel: 'Admin tools',
    category: 'account',
    audience: AUDIENCE.ADMIN,
    status: FEATURE_STATUS.ENABLED,
    adminOnly: true,
    goals: [],
    purpose: {
      en: 'The moderation tools. Review the queue of records that need a human decision, verify submissions, and manage scholarship records. Access is restricted to staff.',
      bn: 'মধ্যস্থতি করার টুল। যে রেকর্ডে মানুষের সিদ্ধান্ত দরকার তার তালিকা পর্যালোচনা করুন, জমা পড়ে প্রমাণিত করুন, আর বৃত্তির রেকর্ড পরিচালনা করুন। প্রবেশাধিকার কেবল কর্মীদের।',
    },
    whenToUse: {
      en: 'When you are moderating the catalogue. If you are not staff, these routes are not for you and you will not be able to use them.',
      bn: 'যখন আপনি তালিকা মধ্যস্থতি করছেন। আপনি কর্মী নন হলে, এই পথগুলি আপনার জন্য নয় এবং ব্যবহার করতে পারবেন না।',
    },
    steps: [
      {
        title: { en: 'Sign in with a staff account', bn: 'একটি কর্মী অ্যাকাউন্টে সাইন ইন করুন' },
        body: {
          en: 'The tools check your access server-side. A non-staff account will not get in, and that is the intended behaviour.',
          bn: 'টুলগুলো সার্ভার-দিকে আপনার অ্যাক্সেস পরীক্ষা করে। কর্মী-নন অ্যাকাউন্ট ঢুকতে পারবে না, আর এটাই ইচ্ছাকৃত আচরণ।',
        },
      },
      {
        title: { en: 'Work the queue', bn: 'অপেক্ষমাণ তালিকা কাজ করুন' },
        body: {
          en: 'Open a record, decide, and record the decision. Each decision is a record with your actions attached.',
          bn: 'একটি রেকর্ড খুলুন, সিদ্ধান্ত নিন, আর সিদ্ধান্তটি লিখে রাখুন। প্রতিটি সিদ্ধান্ত আপনার কাজ যুক্ত একটি রেকর্ড।',
        },
      },
      {
        title: { en: 'Check the effect before publishing', bn: 'প্রকাশ করার আগে প্রভাব দেখুন' },
        body: {
          en: 'The catalogue changes when records change, so verify the result reads correctly after a decision.',
          bn: 'রেকর্ড বদলালে তালিকা বদলায়, তাই সিদ্ধান্তের পর ফলাফল ঠিকমতো পড়ছে কি না যাচাই করুন।',
        },
      },
    ],
    fields: [],
    interpretResult: {
      en: 'Queue counts are records awaiting a decision, not errors. An empty queue is the healthy state, not a broken one.',
      bn: 'অপেক্ষমাণ তালিকার হিসাব হলো সিদ্ধান্তের অপেক্ষায় থাকা রেকর্ড, ভুল নয়। খালি তালিকা একটি সুস্থ অবস্থা, নষ্ট নয়।',
    },
    mistakes: [
      {
        mistake: { en: 'Publishing a record you have not checked', bn: 'যাচাই না করে রেকর্ড প্রকাশ করা' },
        fix: {
          en: 'Every record points back to the source wording. Confirm against that before publishing, because a wrong record is worse than a missing one.',
          bn: 'প্রতিটি রেকর্ড মূল ভাষায় ফিরে যায়। প্রকাশ করার আগে তার বিপরীতে নিশ্চিত করুন, কারণ একটি ভুল রেকর্ড অনুপস্থিত রেকর্ডের চেয়ে খারাপ।',
        },
      },
    ],
    recovery: {
      en: 'Decisions are held against your account. If a tool does not respond, reload once and re-check the queue rather than re-submitting the same decision.',
      bn: 'সিদ্ধান্ত আপনার অ্যাকাউন্টে রাখা হয়। কোনো টール সাড়া না দিলে, একবার রিলোড করে একই সিদ্ধান্ত আবার জমা দেওয়ার বদলে তালিকা আবার দেখুন।',
    },
    storage: {
      en: 'Admin state is held on the server against your staff account. Actions are logged as the account that took them.',
      bn: 'অ্যাডমিন অবস্থা সার্ভারে আপনার কর্মী অ্যাকাউন্টে রাখা হয়। কাজগুলো যে অ্যাকাউন্ট করেছে তা হিসাব হিসেবে লেখা হয়।',
    },
    notGuarantee: {
      en: 'The tools do not verify a record for you. A human decision is recorded, and the record own source wording remains the authority.',
      bn: 'টুলগুলি আপনার জন্য কোনো বৃত্তি যাচাই করে না। একজন মানুষের সিদ্ধান্ত রেকর্ড হয়, আর বৃত্তির নিজের ভাষাই কর্তৃত্ববান।',
    },
  },
])

/* ── Readers ──────────────────────────────────────────────────────── */

/**
 * Every route a tutorial covers, expanded from `route` and `routes`.
 *
 * A feature reached through two URLs — sign-in and register share one form —
 * is one tutorial, so `routes` exists to say both without duplicating the
 * prose. Two tutorials claiming one route is what this is for catching.
 */
export function routesOf(tutorial) {
  const routes = Array.isArray(tutorial.routes) ? tutorial.routes.slice() : []
  if (typeof tutorial.route === 'string' && !routes.includes(tutorial.route)) {
    routes.push(tutorial.route)
  }
  return routes
}

/** The tutorial for a route, or null. Dynamic segments must match exactly. */
export function tutorialForRoute(route) {
  if (typeof route !== 'string') return null
  return TUTORIALS.find((tutorial) => routesOf(tutorial).includes(route)) || null
}

/** Tutorials a public reader may see, in catalogue order. */
export function publicTutorials() {
  return TUTORIALS.filter(
    (tutorial) => tutorial.status === FEATURE_STATUS.ENABLED && tutorial.audience !== AUDIENCE.ADMIN,
  )
}

/** Admin tutorials, kept apart so they are never shelved next to browsing. */
export function adminTutorials() {
  return TUTORIALS.filter(
    (tutorial) => tutorial.status === FEATURE_STATUS.ENABLED && tutorial.audience === AUDIENCE.ADMIN,
  )
}

/**
 * Tutorials for one goal, used by "start here if you want to…".
 *
 * A disabled tutorial is not reachable from a goal either: a reader who cannot
 * visit a route should not be sent there by the help centre.
 */
export function tutorialsForGoal(goal) {
  return publicTutorials().filter((tutorial) => tutorial.goals.includes(goal))
}

/** The categories that have at least one published tutorial, in order. */
export const CATEGORY_ORDER = Object.freeze([
  'discover',
  'prepare',
  'write',
  'apply',
  'account',
])

/** Tutorials in one category, published only. */
export function tutorialsInCategory(category) {
  return publicTutorials().filter((tutorial) => tutorial.category === category)
}

/**
 * The set of routes the application actually declares, and which are published.
 *
 * Kept as data rather than derived from `App.jsx` at render time, because the
 * router is not importable from here and a test that re-parsed the route file
 * would be testing its own regex rather than the registry. `COVERAGE` below is
 * what makes this honest: a route with no tutorial is a failed assertion, not a
 * silent gap.
 */
export const ROUTES = Object.freeze({
  '/': { tutorial: 'home', audience: AUDIENCE.PUBLIC },
  '/countries': { tutorial: 'countries', audience: AUDIENCE.PUBLIC },
  '/scholarships': { tutorial: 'scholarships', audience: AUDIENCE.PUBLIC },
  '/match': { tutorial: 'match', audience: AUDIENCE.PUBLIC },
  '/scholarships/:id': { tutorial: 'scholarship-details', audience: AUDIENCE.PUBLIC },
  '/login': { tutorial: 'account', audience: AUDIENCE.PUBLIC },
  '/register': { tutorial: 'account', audience: AUDIENCE.PUBLIC },
  '/saved': { tutorial: 'saved', audience: AUDIENCE.PUBLIC },
  '/plan': { tutorial: 'plan', audience: AUDIENCE.PUBLIC },
  '/statement': { tutorial: 'statement', audience: AUDIENCE.PUBLIC },
  '/dashboard': { tutorial: 'dashboard', audience: AUDIENCE.AUTH },
  '/applications': { tutorial: 'applications', audience: AUDIENCE.AUTH },
  '/applications/:applicationId': { tutorial: 'applications', audience: AUDIENCE.AUTH },
  '/mentor': { tutorial: 'mentor', audience: AUDIENCE.AUTH },
  '/compare': { tutorial: 'compare', audience: AUDIENCE.PUBLIC },
  '/bangladesh-journey': { tutorial: 'bangladesh-journey', audience: AUDIENCE.PUBLIC },
  '/bangladesh-journey/:stepId': { tutorial: 'bangladesh-journey', audience: AUDIENCE.PUBLIC },
  '/admin': { tutorial: 'admin', audience: AUDIENCE.ADMIN },
  '/admin/verification': { tutorial: 'admin', audience: AUDIENCE.ADMIN },
  '/admin/scholarships': { tutorial: 'admin', audience: AUDIENCE.ADMIN },
  // Declared in App.jsx but behind the feature's own `enabled` flag, which is
  // committed false. Listed so the audit shows the route exists and is
  // deliberately uncovered while the feature is off.
  '/consistency-review': { tutorial: null, audience: AUDIENCE.PUBLIC, disabled: true },
})

/**
 * Routes with a disabled feature that has no tutorial while it is off.
 *
 * The consistency auditor is the live case: its route renders the not-found page
 * while `enabled` is false, so a tutorial telling a reader to visit it would be
 * telling them something untrue. This list is what a test asserts against, so
 * enabling the flag produces a coverage failure rather than a stale guide.
 */
export const ROUTES_WITHOUT_TUTORIAL = Object.freeze(
  Object.entries(ROUTES)
    .filter(([, entry]) => entry.tutorial === null)
    .map(([route]) => route),
)

/**
 * Validate the registry against itself.
 *
 * Returns a list of problems, empty when the catalogue is sound. Run by the
 * tests rather than at import time, so a mistake breaks a test with a readable
 * list instead of crashing a page a student is reading.
 */
export function validateRegistry() {
  const problems = []

  const ids = new Set()
  const claimedRoutes = new Map()

  for (const tutorial of TUTORIALS) {
    if (!tutorial.id || typeof tutorial.id !== 'string') {
      problems.push(`a tutorial has no id`)
    } else if (ids.has(tutorial.id)) {
      problems.push(`duplicate tutorial id: ${tutorial.id}`)
    } else {
      ids.add(tutorial.id)
    }

    for (const route of routesOf(tutorial)) {
      const owner = claimedRoutes.get(route)
      if (owner && owner !== tutorial.id) {
        problems.push(`route ${route} is claimed by both ${owner} and ${tutorial.id}`)
      }
      claimedRoutes.set(route, tutorial.id)
    }

    // A published tutorial must carry both languages, because a half-translated
    // guide is worse than an English one for a reader who needs the Bangla.
    for (const [field, value] of [
      ['purpose', tutorial.purpose],
      ['whenToUse', tutorial.whenToUse],
      ['interpretResult', tutorial.interpretResult],
      ['recovery', tutorial.recovery],
      ['storage', tutorial.storage],
      ['notGuarantee', tutorial.notGuarantee],
    ]) {
      if (!value || typeof value.en !== 'string' || value.en.trim() === '') {
        problems.push(`${tutorial.id}: ${field}.en is empty`)
      }
      if (!value || typeof value.bn !== 'string' || value.bn.trim() === '') {
        problems.push(`${tutorial.id}: ${field}.bn is empty`)
      }
    }

    if (!Array.isArray(tutorial.steps) || tutorial.steps.length === 0) {
      problems.push(`${tutorial.id}: no guided steps`)
    } else {
      for (const step of tutorial.steps) {
        if (!step.title?.en || !step.title?.bn) {
          problems.push(`${tutorial.id}: a step is missing a title in one language`)
        }
        if (!step.body?.en || !step.body?.bn) {
          problems.push(`${tutorial.id}: a step is missing its body in one language`)
        }
      }
    }

    for (const [field, list] of [
      ['fields', tutorial.fields],
      ['mistakes', tutorial.mistakes],
    ]) {
      if (!Array.isArray(list)) continue
      for (const entry of list) {
        const shape = field === 'fields' ? ['name', 'meaning'] : ['mistake', 'fix']
        for (const part of shape) {
          if (!entry[part]?.en || !entry[part]?.bn) {
            problems.push(`${tutorial.id}: a ${field} entry is missing ${part} in one language`)
          }
        }
      }
    }

    // The rule that matters most: no tutorial may promise an outcome.
    for (const [field, value] of [
      ['notGuarantee', tutorial.notGuarantee],
      ['purpose', tutorial.purpose],
    ]) {
      const text = `${value?.en || ''} ${value?.bn || ''}`.toLowerCase()
      for (const phrase of ['will get you', 'guarantees you', 'ensure you get', 'you will be accepted']) {
        if (text.includes(phrase)) {
          problems.push(`${tutorial.id}: ${field} asserts an outcome ("${phrase}")`)
        }
      }
    }

    // A goal id must exist in the i18n vocabulary, or the goal index renders a
    // bare key.
    for (const goal of tutorial.goals || []) {
      if (!KNOWN_GOALS.includes(goal)) {
        problems.push(`${tutorial.id}: unknown goal id "${goal}"`)
      }
    }
    if (!CATEGORY_ORDER.includes(tutorial.category)) {
      problems.push(`${tutorial.id}: unknown category "${tutorial.category}"`)
    }
  }

  // Every route that has a tutorial id must point at one that exists.
  for (const [route, entry] of Object.entries(ROUTES)) {
    if (entry.tutorial && !ids.has(entry.tutorial)) {
      problems.push(`route ${route} points at missing tutorial "${entry.tutorial}"`)
    }
  }

  return problems
}

/**
 * The goal ids the i18n dictionary defines.
 *
 * Duplicated as data rather than imported from `strings.js` so this module is
 * pure data with no dependency on the React layer. If `strings.js` grows a goal
 * and this list does not, every tutorial using it fails validation loudly,
 * which is the safer failure.
 */
export const KNOWN_GOALS = Object.freeze([
  'findScholarships',
  'understandOne',
  'compareOptions',
  'knowWhatINeed',
  'writeMyStatement',
  'trackDeadlines',
  'planMoney',
  'prepareDocuments',
  'checkMyPapers',
  'learnBangladesh',
  'seeMyProgress',
])
