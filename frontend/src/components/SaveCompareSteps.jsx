import { Link } from 'react-router-dom'
import './SaveCompareSteps.css'

/* The decision loop, in the order a student actually walks it. Each
   step links to the real route so the section works as an entry point
   rather than only describing one. */
const STEPS = [
  {
    title: 'Find',
    note: 'Search or filter the directory by field, level, funding and location.',
    to: '/scholarships',
    action: 'Open the directory',
  },
  {
    title: 'Save',
    note: 'Keep the ones worth a real application somewhere you will find them again.',
    to: '/saved',
    action: 'View saved',
  },
  {
    title: 'Compare',
    note: 'Put up to three side by side — funding, level, location and deadline.',
    to: '/compare',
    action: 'Compare',
  },
  {
    title: 'Decide',
    note: 'Open the full listing and apply with the awarding body directly.',
    to: '/scholarships',
    action: 'Review listings',
  },
]

export default function SaveCompareSteps() {
  return (
    <ol className="sz-decision">
      {STEPS.map((step, index) => (
        <li className="sz-decision__step" key={step.title} style={{ '--sz-step-index': index }}>
          <span className="sz-decision__index">{String(index + 1).padStart(2, '0')}</span>
          <span className="sz-decision__title">{step.title}</span>
          <span className="sz-decision__note">{step.note}</span>
          <Link to={step.to} className="sz-decision__link">
            {step.action}
            <span aria-hidden="true">&rarr;</span>
          </Link>
        </li>
      ))}
    </ol>
  )
}
