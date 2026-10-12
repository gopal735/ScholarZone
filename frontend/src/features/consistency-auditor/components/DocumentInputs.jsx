import { STRINGS } from '../strings.js';

/**
 * The three inputs.
 *
 * Every textarea is fully controlled by the parent's state and its value is
 * exactly what the user typed: no trim-on-change, no normalisation, no
 * transformation. Normalisation happens inside the engine on its own
 * copies, so what is shown back is always the original.
 */
export default function DocumentInputs({ documents, onChange, overLimitId }) {
  const entries = [
    { id: 'sop', ...STRINGS.inputs.sop },
    { id: 'cv', ...STRINGS.inputs.cv },
    { id: 'answers', ...STRINGS.inputs.answers },
  ];

  return (
    <div className="ca-inputs">
      {entries.map((entry) => {
        const document = documents[entry.id];
        const overLimit = overLimitId === entry.id;
        return (
          <div className="ca-field" key={entry.id}>
            <label className="ca-field__label" htmlFor={`ca-${entry.id}`}>
              {entry.label}
            </label>
            <p className="ca-field__hint">{entry.hint}</p>
            <textarea
              id={`ca-${entry.id}`}
              className={`ca-field__input${overLimit ? ' ca-field__input--over' : ''}`}
              value={document.text}
              onChange={(event) => onChange(entry.id, event.target.value)}
              rows={overLimit ? 4 : 8}
              spellCheck={false}
              aria-describedby={`ca-${entry.id}-count`}
              placeholder={entry.hint}
            />
            <p
              className={`ca-field__count${overLimit ? ' ca-field__count--over' : ''}`}
              id={`ca-${entry.id}-count`}
              aria-live="polite"
            >
              {overLimit
                ? STRINGS.states.overLimit
                : STRINGS.inputs.charactersLabel(document.text.length, 20000)}
            </p>
          </div>
        );
      })}
    </div>
  );
}
