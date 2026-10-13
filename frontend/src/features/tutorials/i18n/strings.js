/**
 * Translation dictionary for the Tutorials & Help Center.
 *
 * Follows the convention `features/journey/i18n/strings.js` established:
 * `LANGUAGE_MODES = ['bn', 'en', 'both']`, a flat key → string object per
 * language, and `translate(mode, key)` for lookup. `both` renders Bangla as the
 * primary line and English underneath it.
 *
 * This file holds the UI chrome — buttons, labels, empty and error states. The
 * tutorials themselves live in `lib/registry.js`, where each piece of content is
 * already authored in both languages rather than translated at render time.
 *
 * The Bangla below is written as plain instruction rather than a literal gloss
 * of the English, because a literal translation of UI copy reads as machine
 * output and is harder to follow.
 *
 * Provider names, URLs and technical terms a student will see on an official
 * page are deliberately not translated: a scholarship provider's name is a
 * proper noun and rendering it in Bangla would misattribute it to a different
 * body.
 */

export const LANGUAGE_MODES = ['bn', 'en', 'both']

const en = {
  'app.title': 'Tutorials & Help Center',
  'app.tagline': 'Learn how any ScholarZone feature works, in plain language',

  'nav.openHelp': 'Help & tutorials',
  'nav.openHelpFull': 'Open the Tutorials & Help Center',
  'nav.skipToContent': 'Skip to main content',

  'button.howToUse': 'How to use this',
  'button.howToUseLong': 'How to use this feature',
  'button.readTutorial': 'Read the full tutorial',
  'button.openHelpCenter': 'Open the Help Center',
  'button.next': 'Next',
  'button.previous': 'Previous',
  'button.done': 'Done',
  'button.close': 'Close',
  'button.dismiss': 'Hide this for now',
  'button.showAgain': 'Show the quick guide again',
  'button.showAll': 'Show every quick guide',
  'button.hideAll': 'Hide every quick guide',
  'button.backToHelp': 'Back to the Help Center',
  'button.clearSearch': 'Clear the search',
  'button.resetPrefs': 'Reset tutorial preferences',
  'button.setEnglish': 'English',
  'button.setBangla': 'বাংলা',
  'button.setBoth': 'Both',

  'language.label': 'Language',
  'language.en': 'English only',
  'language.bn': 'Bangla only',
  'language.both': 'Bangla and English',

  'search.label': 'Search tutorials',
  'search.placeholder': 'Search by feature or by what you want to do',
  'search.resultsCount': 'tutorials found',
  'search.noResults': 'Nothing matches that search.',
  'search.noResultsHint': 'Try a simpler word, or browse the categories below.',

  'category.label': 'Categories',
  'category.all': 'Everything',
  'category.discover': 'Find scholarships',
  'category.prepare': 'Get organised',
  'category.write': 'Write your documents',
  'category.apply': 'Apply and track',
  'category.account': 'Your account',

  'goal.label': 'I want to',
  'goal.findScholarships': 'Find scholarships that fit me',
  'goal.understandOne': 'Understand one scholarship properly',
  'goal.compareOptions': 'Compare two or more scholarships',
  'goal.knowWhatINeed': 'Know what an application needs',
  'goal.writeMyStatement': 'Write my statement of purpose',
  'goal.trackDeadlines': 'Keep track of deadlines',
  'goal.planMoney': 'Work out what it will cost me',
  'goal.prepareDocuments': 'Get my documents ready',
  'goal.checkMyPapers': 'Check my own papers agree with each other',
  'goal.learnBangladesh': 'Find the steps for applying from Bangladesh',
  'goal.seeMyProgress': 'See what I have done so far',

  'section.whatItDoes': 'What this feature does',
  'section.whenToUse': 'When to use it',
  'section.steps': 'Step-by-step',
  'section.fields': 'What to type in each box',
  'section.interpret': 'How to read the result',
  'section.mistakes': 'Common mistakes and how to recover',
  'section.storage': 'Where your information is kept',
  'section.notGuarantee': 'What this does not guarantee',
  'section.relatedGoals': 'Start here if you want to',

  'panel.localOnly': 'This guide is stored in this browser only.',
  'panel.localOnlyBody':
    'No analytics, no server, nothing follows you to another browser. A copy of ' +
    'what you dismiss is kept so the guide does not reappear every time.',
  'panel.storageFailed': 'This browser refused to store your preference.',
  'panel.storageFailedBody':
    'Your choice still works until you close the tab, but it will not be ' +
    'remembered. Private browsing modes and some privacy settings do this.',
  'panel.noNetwork': 'No data leaves your device to show these guides.',

  'help.intro': 'Every ScholarZone feature, explained from the beginning.',
  'help.introBody':
    'Pick a feature, or start from what you are trying to do. Each guide says ' +
    'what the feature does, what to type into each box, how to read what comes ' +
    'back, what usually goes wrong and how to fix it, and what the feature ' +
    'cannot promise you.',
  'help.coverageTitle': 'Coverage',

  'tutorial.empty': 'This tutorial has not been written yet.',
  'tutorial.loading': 'Opening the guide…',
  'tutorial.stepOf': 'Step',
  'tutorial.of': 'of',
  'tutorial.dismissedNote': 'You hid this quick guide. It is here again because you asked.',

  'route.admin': 'Admin tools',
  'route.auth': 'Account',
  'route.error': 'Page not found',
}

const bn = {
  'app.title': 'টিউটোরিয়াল ও সহায়তা কেন্দ্র',
  'app.tagline': 'ScholarZone এর যে কোনো ফিচার সহজ ভাষায় জানুন',

  'nav.openHelp': 'সহায়তা ও টিউটোরিয়াল',
  'nav.openHelpFull': 'টিউটোরিয়াল ও সহায়তা কেন্দ্র খুলুন',
  'nav.skipToContent': 'মুখ্য অংশে যান',

  'button.howToUse': 'কীভাবে ব্যবহার করবেন?',
  'button.howToUseLong': 'এই ফিচারটি কীভাবে ব্যবহার করবেন',
  'button.readTutorial': 'পুরো টিউটোরিয়াল পড়ুন',
  'button.openHelpCenter': 'সহায়তা কেন্দ্র খুলুন',
  'button.next': 'পরবর্তী',
  'button.previous': 'পূর্ববর্তী',
  'button.done': 'শেষ',
  'button.close': 'বন্ধ করুন',
  'button.dismiss': 'এখন ছিপিয়ে রাখুন',
  'button.showAgain': 'আবার দ্রান্ত গাইড দেখান',
  'button.showAll': 'সব দ্রান্ত গাইড দেখান',
  'button.hideAll': 'সব দ্রান্ত গাইড ছিপিয়ে রাখুন',
  'button.backToHelp': 'সহায়তা কেন্দ্রে ফিরুন',
  'button.clearSearch': 'খোঁজ মুছুন',
  'button.resetPrefs': 'টিউটোরিয়ালের পছন্দ রিসেট করুন',
  'button.setEnglish': 'English',
  'button.setBangla': 'বাংলা',
  'button.setBoth': 'দুটোই',

  'language.label': 'ভাষা',
  'language.en': 'শুধু ইংরেজি',
  'language.bn': 'শুধু বাংলা',
  'language.both': 'বাংলা ও ইংরেজি',

  'search.label': 'টিউটোরিয়াল খুঁজুন',
  'search.placeholder': 'ফিচার বা আপনি কী করতে চান খুঁজুন',
  'search.resultsCount': 'টি টিউটোরিয়াল পাওয়া গেছে',
  'search.noResults': 'এই খোঁজে কিছু মেলেনি।',
  'search.noResultsHint': 'একটি সহজ শব্দ দিয়ে দেখুন, বা নিচের বিভাগগুলো দেখুন।',

  'category.label': 'বিভাগ',
  'category.all': 'সব',
  'category.discover': 'বৃত্তি খুঁজুন',
  'category.prepare': 'প্রস্তুতি নিন',
  'category.write': 'নিজের দলিল লিখুন',
  'category.apply': 'আবেদন করুন ও দেখুন',
  'category.account': 'আপনার অ্যাকাউন্ট',

  'goal.label': 'আমি চাই',
  'goal.findScholarships': 'নিজের সঙ্গে মেলে এমন বৃত্তি খুঁজতে',
  'goal.understandOne': 'একটি বৃত্তি ভালোভাবে বুঝতে',
  'goal.compareOptions': 'দুই বা তার বেশি বৃত্তি তুলনা করতে',
  'goal.knowWhatINeed': 'আবেদনে কী লাগে জানতে',
  'goal.writeMyStatement': 'স্টেটমেন্ট অফ পারপাস লিখতে',
  'goal.trackDeadlines': 'শেষ সময়ের হিসাব রাখতে',
  'goal.planMoney': 'খরচ কত হবে বের করতে',
  'goal.prepareDocuments': 'কাগজপত্র প্রস্তুত করতে',
  'goal.checkMyPapers': 'নিজের কাগজগুলো একে অন্যের সঙ্গে মেলে কিনা দেখতে',
  'goal.learnBangladesh': 'বাংলাদেশ থেকে আবেদনের ধাপ জানতে',
  'goal.seeMyProgress': 'এ পর্যন্ত কী করেছি দেখতে',

  'section.whatItDoes': 'এই ফিচার কী করে',
  'section.whenToUse': 'কখন ব্যবহার করবেন',
  'section.steps': 'ধাপে ধাপে',
  'section.fields': 'প্রতিটি ঘরে কী লিখবেন',
  'section.interpret': 'ফলাফল কীভাবে পড়বেন',
  'section.mistakes': 'সাধারণ ভুল ও সারানোর উপায়',
  'section.storage': 'আপনার তথ্য কোথায় থাকে',
  'section.notGuarantee': 'এটি কী গ্যারান্টি করে না',
  'section.relatedGoals': 'এটি করতে চাইলে শুরু করুন',

  'panel.localOnly': 'এই গাইড শুধু এই ব্রাউজারে রাখা আছে।',
  'panel.localOnlyBody':
    'কোনো ট্র্যাকিং নেই, কোনো সার্ভার নেই, অন্য ব্রাউজারে কিছু ফলো করে না। ' +
    'যা ছিপিয়েছেন তা রাখা হয় যেন গাইড বার বার না ওঠে।',
  'panel.storageFailed': 'এই ব্রাউজার আপনার পছন্দ রাখতে রাজি হয়নি।',
  'panel.storageFailedBody':
    'ট্যাব বন্ধ করার আগে আপনার পছন্দ কাজ করে, কিন্তু মনে রাখা হবে না। ' +
    'প্রাইভেট ব্রাউজিং মোড ও কিছু privacy সেটিং এটা করে।',
  'panel.noNetwork': 'এই গাইড দেখাতে আপনার ডিভাইস থেকে কোনো তথ্য যায় না।',

  'help.intro': 'ScholarZone এর প্রতিটি ফিচার, শুরু থেকে বোঝানো হলো।',
  'help.introBody':
    'একটি ফিচার বেছে নিন, বা আপনি কী করতে চান সেটি থেকে শুরু করুন। প্রতি ' +
    'গাইডে থাকে — ফিচারটি কী করে, প্রতিটি ঘরে কী লিখবেন, কী ফিরে আসে তা ' +
      'কীভাবে পড়বেন, কী ভুল হয় ও কীভাবে ঠিক করবেন, এবং ফিচারটি কী ' +
      'গ্যারান্টি করতে পারে না।',
  'help.coverageTitle': 'কভারেজ',

  'tutorial.empty': 'এই টিউটোরিয়াল এখনো লেখা হয়নি।',
  'tutorial.loading': 'গাইড খোলা হচ্ছে…',
  'tutorial.stepOf': 'ধাপ',
  'tutorial.of': '/',
  'tutorial.dismissedNote': 'আপনি এই দ্রান্ত গাইড ছিপিয়েছিলেন। আপনি চেয়েছেন, তাই আবার দেখানো হলো।',

  'route.admin': 'অ্যাডমিন টুল',
  'route.auth': 'অ্যাকাউন্ট',
  'route.error': 'পেজ পাওয়া যায়নি',
}

/**
 * Look up a string in the requested language.
 *
 * Falls back to English, then to the key itself. A missing key renders as its
 * own name rather than throwing: a help page that crashes on a typo would be a
 * worse failure than a help page that shows a label nobody can read.
 */
export function translate(mode, key) {
  const dict = mode === 'bn' ? bn : en
  const value = dict[key] ?? en[key]
  return typeof value === 'string' ? value : key
}

export { en, bn }
