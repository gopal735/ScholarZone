import { useState } from 'react'

const QUICK_STEPS = [
  { id: 'identity', title: 'Your nationality', hint: 'Nationality rules are checked before anything else.' },
  { id: 'goal', title: 'Your target field', hint: 'We compare your field with the programme each scholarship publishes.' },
  { id: 'degree', title: 'Your target degree', hint: 'A published degree restriction is a hard gate, not a preference.' },
  { id: 'academic', title: 'Your academic result', hint: 'Used for like-for-like comparison. Leave blank if you are unsure.' },
  { id: 'language', title: 'Your language test', hint: 'Only the same test is ever compared. No conversions.' },
  { id: 'funding', title: 'Your funding need', hint: 'Decines funding match, and never your eligibility.' },
]

/**
 * Progressive disclosure with an explicit step count.
 *
 * Quick Match asks only the six fields that change the answer most, one step at a
 * time. Deep Match adds everything else the engine understands, and every field
 * in it is optional: a missing optional field lowers coverage honestly and is
 * never treated as a zero.
 */
export function MatchProfileForm({
  mode,
  onModeChange,
  profile,
  options,
  onChange,
  onToggleCountry,
  onSubmit,
  isBusy,
  fieldErrors = {},
  profileStrength = null,
  children = null,
}) {
  const [stepIndex, setStepIndex] = useState(0)
  const [showAllQuick, setShowAllQuick] = useState(false)
  const isDeep = mode === 'deep'

  const field = (name) => profile[name] ?? ''
  const err = (name) => fieldErrors[name]

  const countryOptions = options?.countries ?? []
  const languageTests = options?.language_tests ?? []
  const fieldOptions = options?.fields ?? []
  const degreeLevels = options?.degree_levels ?? []
  const studyModes = options?.study_modes ?? []
  const fundingRequirements = options?.funding_requirements ?? []
  const gradingScales = options?.grading_scales ?? []

  const step = QUICK_STEPS[Math.min(stepIndex, QUICK_STEPS.length - 1)]
  const isLastStep = stepIndex >= QUICK_STEPS.length - 1
  const progressText = isDeep
    ? 'Deep Match'
    : `Step ${stepIndex + 1} of ${QUICK_STEPS.length}: ${step.title}`

  const idPrefix = 'match-field'

  return (
    <form
      className="match-form"
      onSubmit={onSubmit}
      aria-label="Build your match profile"
      data-testid="match-form"
    >
      <div className="match-form__intro">
        <h2>Find the scholarships you can actually apply for</h2>
        <p>
          ScholarZone checks every published eligibility rule before it scores anything,
          so a scholarship you cannot apply for is never shown as a strong match.
        </p>
      </div>

      <div className="match-sections" role="tablist" aria-label="How much detail to give">
        <button
          type="button"
          role="tab"
          id="match-mode-quick"
          aria-selected={!isDeep}
          aria-controls="match-mode-panel"
          className={`match-sections__tab${!isDeep ? ' is-active' : ''}`}
          onClick={() => onModeChange('quick')}
          data-testid="mode-quick"
        >
          Quick Match
        </button>
        <button
          type="button"
          role="tab"
          id="match-mode-deep"
          aria-selected={isDeep}
          aria-controls="match-mode-panel"
          className={`match-sections__tab${isDeep ? ' is-active' : ''}`}
          onClick={() => onModeChange('deep')}
          data-testid="mode-deep"
        >
          Deep Match
        </button>
      </div>

      <div
        className="match-section-panel"
        id="match-mode-panel"
        role="tabpanel"
        aria-labelledby={isDeep ? 'match-mode-deep' : 'match-mode-quick'}
      >
        {children}

        {!isDeep ? (
          <p className="match-section-panel__hint" data-testid="quick-progress">
            {showAllQuick ? 'All quick questions' : progressText}
          </p>
        ) : (
          <p className="match-section-panel__hint">
            Every field below is optional. Anything you leave blank is reported as
            &ldquo;not evaluated&rdquo; rather than counted as zero.
          </p>
        )}

        {/* ---------------------------------------------------------- quick */}
        {!isDeep ? (
          <>
            {showAllQuick ? (
              <div className="match-field-grid">
                <div className="match-field">
                  <label className="match-field__label" htmlFor={`${idPrefix}-citizenship`}>
                    Nationality
                  </label>
                  <input
                    className="match-control"
                    id={`${idPrefix}-citizenship`}
                    name="citizenship"
                    list={`${idPrefix}-countries`}
                    value={field('citizenship')}
                    aria-invalid={err('citizenship') ? 'true' : undefined}
                    aria-describedby={err('citizenship') ? `${idPrefix}-citizenship-error` : undefined}
                    onChange={(e) => onChange('citizenship', e.target.value)}
                    data-testid="field-citizenship"
                  />
                  <datalist id={`${idPrefix}-countries`}>
                    {countryOptions.map((name) => (
                      <option key={name} value={name} />
                    ))}
                  </datalist>
                  {err('citizenship') ? (
                    <p className="match-form__error" id={`${idPrefix}-citizenship-error`} role="alert">
                      {err('citizenship')}
                    </p>
                  ) : null}
                </div>

                <div className="match-field">
                  <label className="match-field__label" htmlFor={`${idPrefix}-field`}>
                    Target field
                  </label>
                  <select
                    className="match-control"
                    id={`${idPrefix}-field`}
                    value={field('intendedField')}
                    onChange={(e) => onChange('intendedField', e.target.value)}
                    data-testid="field-intendedField"
                  >
                    <option value="">Not decided yet</option>
                    {fieldOptions.map((option) => (
                      <option key={option.key} value={option.key}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="match-field">
                  <label className="match-field__label" htmlFor={`${idPrefix}-degree`}>
                    Target degree
                  </label>
                  <select
                    className="match-control"
                    id={`${idPrefix}-degree`}
                    value={field('intendedDegreeLevel')}
                    onChange={(e) => onChange('intendedDegreeLevel', e.target.value)}
                    data-testid="field-intendedDegreeLevel"
                  >
                    <option value="">Not decided yet</option>
                    {degreeLevels.map((level) => (
                      <option key={level} value={level}>
                        {level.replace(/_/g, ' ')}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="match-field">
                  <label className="match-field__label" htmlFor={`${idPrefix}-scale`}>
                    Academic result
                  </label>
                  <select
                    className="match-control"
                    id={`${idPrefix}-scale`}
                    value={field('resultScale')}
                    onChange={(e) => onChange('resultScale', e.target.value)}
                    data-testid="field-resultScale"
                  >
                    <option value="">Not sure yet</option>
                    {gradingScales.map((scale) => (
                      <option key={scale} value={scale}>
                        {scale.replace(/_/g, ' ')}
                      </option>
                    ))}
                  </select>
                  <label className="match-visually-hidden" htmlFor={`${idPrefix}-result`}>
                    Academic result value
                  </label>
                  <input
                    className="match-control"
                    id={`${idPrefix}-result`}
                    inputMode="decimal"
                    placeholder="Your result"
                    value={field('resultValue')}
                    aria-invalid={err('resultValue') ? 'true' : undefined}
                    aria-describedby={err('resultValue') ? `${idPrefix}-result-error` : undefined}
                    onChange={(e) => onChange('resultValue', e.target.value)}
                    data-testid="field-resultValue"
                  />
                  {err('resultValue') ? (
                    <p className="match-form__error" id={`${idPrefix}-result-error`} role="alert">
                      {err('resultValue')}
                    </p>
                  ) : null}
                </div>

                <div className="match-field">
                  <label className="match-field__label" htmlFor={`${idPrefix}-language`}>
                    Language test
                  </label>
                  <select
                    className="match-control"
                    id={`${idPrefix}-language`}
                    value={field('languageTest')}
                    onChange={(e) => onChange('languageTest', e.target.value)}
                    data-testid="field-languageTest"
                  >
                    <option value="">No test yet</option>
                    {languageTests.map((test) => (
                      <option key={test} value={test}>
                        {test}
                      </option>
                    ))}
                  </select>
                  <label className="match-visually-hidden" htmlFor={`${idPrefix}-score`}>
                    Language score
                  </label>
                  <input
                    className="match-control"
                    id={`${idPrefix}-score`}
                    inputMode="decimal"
                    placeholder="Score"
                    value={field('languageScore')}
                    onChange={(e) => onChange('languageScore', e.target.value)}
                    data-testid="field-languageScore"
                  />
                </div>

                <div className="match-field">
                  <label className="match-field__label" htmlFor={`${idPrefix}-funding`}>
                    Funding need
                  </label>
                  <select
                    className="match-control"
                    id={`${idPrefix}-funding`}
                    value={field('fundingRequirement')}
                    onChange={(e) => onChange('fundingRequirement', e.target.value)}
                    data-testid="field-fundingRequirement"
                  >
                    <option value="">No preference</option>
                    {fundingRequirements.map((item) => (
                      <option key={item} value={item}>
                        {item.replace(/_/g, ' ').toLowerCase()}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
            ) : (
              <div className="match-step">
                <p className="match-step__hint">{step.hint}</p>
                {step.id === 'identity' ? (
                  <div className="match-field">
                    <label className="match-field__label" htmlFor={`${idPrefix}-citizenship`}>
                      Nationality
                    </label>
                    <input
                      className="match-control"
                      id={`${idPrefix}-citizenship`}
                      list={`${idPrefix}-countries`}
                      value={field('citizenship')}
                      onChange={(e) => onChange('citizenship', e.target.value)}
                      data-testid="field-citizenship"
                    />
                    <datalist id={`${idPrefix}-countries`}>
                      {countryOptions.map((name) => (
                        <option key={name} value={name} />
                      ))}
                    </datalist>
                  </div>
                ) : null}

                {step.id === 'goal' ? (
                  <div className="match-field">
                    <label className="match-field__label" htmlFor={`${idPrefix}-field`}>
                      Target field
                    </label>
                    <select
                      className="match-control"
                      id={`${idPrefix}-field`}
                      value={field('intendedField')}
                      onChange={(e) => onChange('intendedField', e.target.value)}
                      data-testid="field-intendedField"
                    >
                      <option value="">Not decided yet</option>
                      {fieldOptions.map((option) => (
                        <option key={option.key} value={option.key}>
                          {option.label}
                        </option>
                      ))}
                    </select>
                  </div>
                ) : null}

                {step.id === 'degree' ? (
                  <div className="match-field">
                    <label className="match-field__label" htmlFor={`${idPrefix}-degree`}>
                      Target degree
                    </label>
                    <select
                      className="match-control"
                      id={`${idPrefix}-degree`}
                      value={field('intendedDegreeLevel')}
                      onChange={(e) => onChange('intendedDegreeLevel', e.target.value)}
                      data-testid="field-intendedDegreeLevel"
                    >
                      <option value="">Not decided yet</option>
                      {degreeLevels.map((level) => (
                        <option key={level} value={level}>
                          {level.replace(/_/g, ' ')}
                        </option>
                      ))}
                    </select>
                  </div>
                ) : null}

                {step.id === 'academic' ? (
                  <div className="match-field">
                    <label className="match-field__label" htmlFor={`${idPrefix}-scale`}>
                      Academic result
                    </label>
                    <select
                      className="match-control"
                      id={`${idPrefix}-scale`}
                      value={field('resultScale')}
                      onChange={(e) => onChange('resultScale', e.target.value)}
                      data-testid="field-resultScale"
                    >
                      <option value="">Not sure yet</option>
                      {gradingScales.map((scale) => (
                        <option key={scale} value={scale}>
                          {scale.replace(/_/g, ' ')}
                        </option>
                      ))}
                    </select>
                    <label className="match-visually-hidden" htmlFor={`${idPrefix}-result`}>
                      Academic result value
                    </label>
                    <input
                      className="match-control"
                      id={`${idPrefix}-result`}
                      inputMode="decimal"
                      placeholder="Your result"
                      value={field('resultValue')}
                      aria-invalid={err('resultValue') ? 'true' : undefined}
                      onChange={(e) => onChange('resultValue', e.target.value)}
                      data-testid="field-resultValue"
                    />
                    {err('resultValue') ? (
                      <p className="match-form__error" role="alert">
                        {err('resultValue')}
                      </p>
                    ) : null}
                  </div>
                ) : null}

                {step.id === 'language' ? (
                  <div className="match-field">
                    <label className="match-field__label" htmlFor={`${idPrefix}-language`}>
                      Language test
                    </label>
                    <select
                      className="match-control"
                      id={`${idPrefix}-language`}
                      value={field('languageTest')}
                      onChange={(e) => onChange('languageTest', e.target.value)}
                      data-testid="field-languageTest"
                    >
                      <option value="">No test yet</option>
                      {languageTests.map((test) => (
                        <option key={test} value={test}>
                          {test}
                        </option>
                      ))}
                    </select>
                    <label className="match-visually-hidden" htmlFor={`${idPrefix}-score`}>
                      Language score
                    </label>
                    <input
                      className="match-control"
                      id={`${idPrefix}-score`}
                      inputMode="decimal"
                      placeholder="Score"
                      value={field('languageScore')}
                      onChange={(e) => onChange('languageScore', e.target.value)}
                      data-testid="field-languageScore"
                    />
                  </div>
                ) : null}

                {step.id === 'funding' ? (
                  <div className="match-field">
                    <label className="match-field__label" htmlFor={`${idPrefix}-funding`}>
                      Funding need
                    </label>
                    <select
                      className="match-control"
                      id={`${idPrefix}-funding`}
                      value={field('fundingRequirement')}
                      onChange={(e) => onChange('fundingRequirement', e.target.value)}
                      data-testid="field-fundingRequirement"
                    >
                      <option value="">No preference</option>
                      {fundingRequirements.map((item) => (
                        <option key={item} value={item}>
                          {item.replace(/_/g, ' ').toLowerCase()}
                        </option>
                      ))}
                    </select>
                  </div>
                ) : null}

                <div className="match-step__nav">
                  <button
                    type="button"
                    className="match-step__back"
                    onClick={() => setStepIndex((index) => Math.max(0, index - 1))}
                    disabled={stepIndex === 0}
                  >
                    Back
                  </button>
                  <button
                    type="button"
                    className="match-step__all"
                    onClick={() => setShowAllQuick(true)}
                  >
                    Show all questions
                  </button>
                  {isLastStep ? null : (
                    <button
                      type="button"
                      className="match-step__next"
                      onClick={() => setStepIndex((index) => index + 1)}
                    >
                      Next
                    </button>
                  )}
                </div>
              </div>
            )}
          </>
        ) : null}

        {/* ----------------------------------------------------------- deep */}
        {isDeep ? (
          <div className="match-field-grid">
            <div className="match-field">
              <label className="match-field__label" htmlFor={`${idPrefix}-citizenship`}>
                Nationality
              </label>
              <input
                className="match-control"
                id={`${idPrefix}-citizenship`}
                list={`${idPrefix}-countries`}
                value={field('citizenship')}
                onChange={(e) => onChange('citizenship', e.target.value)}
                data-testid="field-citizenship"
              />
              <datalist id={`${idPrefix}-countries`}>
                {countryOptions.map((name) => (
                  <option key={name} value={name} />
                ))}
              </datalist>
            </div>

            <div className="match-field">
              <label className="match-field__label" htmlFor={`${idPrefix}-residence`}>
                Country of residence
              </label>
              <input
                className="match-control"
                id={`${idPrefix}-residence`}
                list={`${idPrefix}-countries`}
                value={field('countryOfResidence')}
                onChange={(e) => onChange('countryOfResidence', e.target.value)}
                data-testid="field-countryOfResidence"
              />
            </div>

            <div className="match-field">
              <label className="match-field__label" htmlFor={`${idPrefix}-age`}>
                Age
              </label>
              <input
                className="match-control"
                id={`${idPrefix}-age`}
                type="number"
                inputMode="numeric"
                value={field('age')}
                aria-invalid={err('age') ? 'true' : undefined}
                aria-describedby={err('age') ? `${idPrefix}-age-error` : undefined}
                onChange={(e) => onChange('age', e.target.value)}
                data-testid="field-age"
              />
              {err('age') ? (
                <p className="match-form__error" id={`${idPrefix}-age-error`} role="alert">
                  {err('age')}
                </p>
              ) : null}
            </div>

            <div className="match-field">
              <label className="match-field__label" htmlFor={`${idPrefix}-study-mode`}>
                Study mode
              </label>
              <select
                className="match-control"
                id={`${idPrefix}-study-mode`}
                value={field('studyMode')}
                onChange={(e) => onChange('studyMode', e.target.value)}
                data-testid="field-studyMode"
              >
                <option value="">Not sure yet</option>
                {studyModes.map((modeOption) => (
                  <option key={modeOption} value={modeOption}>
                    {modeOption.replace(/_/g, ' ').toLowerCase()}
                  </option>
                ))}
              </select>
            </div>

            <div className="match-field">
              <label className="match-field__label" htmlFor={`${idPrefix}-field`}>
                Target field
              </label>
              <select
                className="match-control"
                id={`${idPrefix}-field`}
                value={field('intendedField')}
                onChange={(e) => onChange('intendedField', e.target.value)}
                data-testid="field-intendedField"
              >
                <option value="">Not decided yet</option>
                {fieldOptions.map((option) => (
                  <option key={option.key} value={option.key}>
                    {option.label}
                  </option>
                ))}
              </select>
            </div>

            <div className="match-field">
              <label className="match-field__label" htmlFor={`${idPrefix}-degree`}>
                Target degree
              </label>
              <select
                className="match-control"
                id={`${idPrefix}-degree`}
                value={field('intendedDegreeLevel')}
                onChange={(e) => onChange('intendedDegreeLevel', e.target.value)}
                data-testid="field-intendedDegreeLevel"
              >
                <option value="">Not decided yet</option>
                {degreeLevels.map((level) => (
                  <option key={level} value={level}>
                    {level.replace(/_/g, ' ')}
                  </option>
                ))}
              </select>
            </div>

            <div className="match-field">
              <label className="match-field__label" htmlFor={`${idPrefix}-scale`}>
                Academic scale
              </label>
              <select
                className="match-control"
                id={`${idPrefix}-scale`}
                value={field('resultScale')}
                onChange={(e) => onChange('resultScale', e.target.value)}
                data-testid="field-resultScale"
              >
                <option value="">Not sure yet</option>
                {gradingScales.map((scale) => (
                  <option key={scale} value={scale}>
                    {scale.replace(/_/g, ' ')}
                  </option>
                ))}
              </select>
              <label className="match-visually-hidden" htmlFor={`${idPrefix}-result`}>
                Academic result value
              </label>
              <input
                className="match-control"
                id={`${idPrefix}-result`}
                inputMode="decimal"
                placeholder="Your result"
                value={field('resultValue')}
                onChange={(e) => onChange('resultValue', e.target.value)}
                data-testid="field-resultValue"
              />
              {err('resultValue') ? (
                <p className="match-form__error" role="alert">
                  {err('resultValue')}
                </p>
              ) : null}
            </div>

            <div className="match-field">
              <label className="match-field__label" htmlFor={`${idPrefix}-graduation`}>
                Graduation year
              </label>
              <input
                className="match-control"
                id={`${idPrefix}-graduation`}
                type="number"
                inputMode="numeric"
                value={field('graduationYear')}
                onChange={(e) => onChange('graduationYear', e.target.value)}
                data-testid="field-graduationYear"
              />
            </div>

            <div className="match-field">
              <label className="match-field__label" htmlFor={`${idPrefix}-language`}>
                Language test
              </label>
              <select
                className="match-control"
                id={`${idPrefix}-language`}
                value={field('languageTest')}
                onChange={(e) => onChange('languageTest', e.target.value)}
                data-testid="field-languageTest"
              >
                <option value="">No test yet</option>
                {languageTests.map((test) => (
                  <option key={test} value={test}>
                    {test}
                  </option>
                ))}
              </select>
              <label className="match-visually-hidden" htmlFor={`${idPrefix}-score`}>
                Language score
              </label>
              <input
                className="match-control"
                id={`${idPrefix}-score`}
                inputMode="decimal"
                placeholder="Score"
                value={field('languageScore')}
                onChange={(e) => onChange('languageScore', e.target.value)}
                data-testid="field-languageScore"
              />
            </div>

            <div className="match-field">
              <label className="match-field__label" htmlFor={`${idPrefix}-funding`}>
                Funding need
              </label>
              <select
                className="match-control"
                id={`${idPrefix}-funding`}
                value={field('fundingRequirement')}
                onChange={(e) => onChange('fundingRequirement', e.target.value)}
                data-testid="field-fundingRequirement"
              >
                <option value="">No preference</option>
                {fundingRequirements.map((item) => (
                  <option key={item} value={item}>
                    {item.replace(/_/g, ' ').toLowerCase()}
                  </option>
                ))}
              </select>
            </div>

            <div className="match-field">
              <label className="match-field__label" htmlFor={`${idPrefix}-intake`}>
                Intended intake year
              </label>
              <input
                className="match-control"
                id={`${idPrefix}-intake`}
                type="number"
                inputMode="numeric"
                value={field('intendedIntakeYear')}
                onChange={(e) => onChange('intendedIntakeYear', e.target.value)}
                data-testid="field-intendedIntakeYear"
              />
            </div>

            <div className="match-field">
              <label className="match-field__label" htmlFor={`${idPrefix}-contribution`}>
                Maximum you can contribute (per year)
              </label>
              <input
                className="match-control"
                id={`${idPrefix}-contribution`}
                type="number"
                inputMode="decimal"
                value={field('maxSelfContribution')}
                onChange={(e) => onChange('maxSelfContribution', e.target.value)}
                data-testid="field-maxSelfContribution"
              />
            </div>

            <div className="match-field match-field--countries">
              <span className="match-field__label" id={`${idPrefix}-countries-label`}>
                Preferred countries or regions
              </span>
              <p className="match-field__hint">
                A preference never affects eligibility. It only changes how strongly a
                scholarship matches your goal.
              </p>
              <div
                className="match-control match-control--multi"
                role="group"
                aria-labelledby={`${idPrefix}-countries-label`}
              >
                {countryOptions.map((name) => {
                  const selected = (profile.preferredCountries ?? []).includes(name)
                  return (
                    <label className="match-checkbox" key={name}>
                      <input
                        type="checkbox"
                        checked={selected}
                        onChange={() => onToggleCountry(name)}
                        data-testid={`country-${name}`}
                      />
                      <span>{name}</span>
                    </label>
                  )
                })}
              </div>
            </div>
          </div>
        ) : null}

        {profileStrength ? (
          <div className="match-form__strength">
            <p className="match-section-panel__hint">
              {profileStrength.label ?? 'Profile'}:{' '}
              {typeof profileStrength.score === 'number'
                ? `${Math.round(profileStrength.score)} of 100`
                : 'not enough information yet'}
            </p>
          </div>
        ) : null}
      </div>

      <button
        type="submit"
        className="match-submit"
        disabled={isBusy}
        data-testid="match-submit"
      >
        {isBusy ? 'Calculating…' : 'Calculate My Matches'}
      </button>

      <p className="match-form__footnote">
        Your profile is used for this calculation only. It is not stored on ScholarZone
       &rsquo;s servers and no account is required.
      </p>
    </form>
  )
}

export default MatchProfileForm