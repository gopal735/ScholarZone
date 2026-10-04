/**
 * The profile snapshot and its completeness measure.
 *
 * "Profile strength" here is the completeness of the student's own input, not a
 * fit score and not a prediction. The server computed it from the matching
 * engine's locked weights and sends the score, the band, each component's own
 * contribution, and the list of groups that are still incomplete - this
 * component draws those and invents nothing.
 *
 * When nothing has been supplied the server sends `score: null`, not `0`. There
 * is deliberately no "0% complete" rendering here: a student who has not told us
 * anything has not scored zero on completeness, and a progress bar reading empty
 * next to the word "complete" would say they had.
 */

import { strengthPercent } from '../../services/dashboardPresentation'

function StrengthMeter({ score, label }) {
  const percent = strengthPercent(score)

  if (percent === null) {
    return (
      <div className="profile-snapshot__strength-unmeasured">
        <p className="profile-snapshot__strength-value">Not measured yet</p>
        <p className="profile-snapshot__strength-note">
          Completeness is measured from what you have supplied, so there is nothing to measure until the
          profile has some content.
        </p>
      </div>
    )
  }

  return (
    <div className="profile-snapshot__strength">
      <p className="profile-snapshot__strength-value">
        <span className="profile-snapshot__strength-number">{percent}%</span>
        {label ? <span className="profile-snapshot__strength-label">{label}</span> : null}
      </p>
      <div
        className="profile-snapshot__meter"
        role="progressbar"
        aria-valuenow={percent}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label="Profile completeness"
      >
        <span className="profile-snapshot__meter-fill" style={{ width: `${percent}%` }} />
      </div>
    </div>
  )
}

export default function ProfileSnapshot({ profile, strength, onEditProfile }) {
  const supplied = profile.fields.filter((field) => field.is_supplied)
  const missing = profile.fields.filter((field) => !field.is_supplied)

  return (
    <section className="dashboard-section" aria-labelledby="profile-snapshot-heading">
      <div className="dashboard-section__header">
        <div>
          <p className="page-eyebrow">Your profile</p>
          <h2 className="dashboard-section__title" id="profile-snapshot-heading">
            Profile snapshot
          </h2>
        </div>
        <button type="button" className="sz-btn sz-btn--secondary" onClick={onEditProfile}>
          Complete profile
        </button>
      </div>

      <div className="profile-snapshot">
        <div className="profile-snapshot__measure">
          <StrengthMeter score={strength.score} label={strength.label} />
          {strength.detail ? <p className="profile-snapshot__detail">{strength.detail}</p> : null}
        </div>

        <div className="profile-snapshot__groups">
          {strength.components.map((component) => {
            const percent = strengthPercent(component.score)
            return (
              <div className="profile-snapshot__group" key={component.name}>
                <div className="profile-snapshot__group-head">
                  <span className="profile-snapshot__group-label">{component.label}</span>
                  <span className="profile-snapshot__group-score">
                    {percent === null ? 'Not evaluated' : `${percent}%`}
                  </span>
                </div>
                <div className="profile-snapshot__group-track" aria-hidden="true">
                  <span
                    className="profile-snapshot__group-fill"
                    style={{ width: `${percent === null ? 0 : percent}%` }}
                  />
                </div>
                <p className="profile-snapshot__group-detail">{component.detail}</p>
              </div>
            )
          })}
        </div>
      </div>

      <div className="profile-snapshot__fields">
        {supplied.length === 0 ? (
          <p className="profile-snapshot__none">No profile details saved yet.</p>
        ) : (
          <dl className="profile-snapshot__list">
            {supplied.map((field) => (
              <div className="profile-snapshot__row" key={field.key}>
                <dt className="profile-snapshot__row-label">{field.label}</dt>
                <dd className="profile-snapshot__row-value">{field.value}</dd>
              </div>
            ))}
          </dl>
        )}
      </div>

      {missing.length > 0 ? (
        <details className="profile-snapshot__missing">
          <summary className="profile-snapshot__missing-summary">
            Not supplied yet ({missing.length})
          </summary>
          <ul className="profile-snapshot__missing-list">
            {missing.map((field) => (
              <li key={field.key}>{field.label}</li>
            ))}
          </ul>
        </details>
      ) : null}
    </section>
  )
}