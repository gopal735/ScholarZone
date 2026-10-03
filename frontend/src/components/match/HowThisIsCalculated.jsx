/**
 * "How this is calculated".
 *
 * This is a trust feature, not a help article. It has to make three things
 * legible: the weights, which dimensions were actually evaluated for the result
 * being looked at, and the fact that an unevaluated dimension is excluded from
 * the average rather than counted as zero.
 */

const COMPONENT_LABELS = {
  academic: 'Academic fit',
  field: 'Field / programme fit',
  funding: 'Funding / budget fit',
  requirement: 'Requirement fit',
  language: 'Language fit',
  preference: 'Preference fit',
  timing: 'Timing fit',
}

function PercentLabel({ component }) {
  const isEvaluated = component.status === 'EVALUATED'

  return (
    <li className={isEvaluated ? 'how-calc__component' : 'how-calc__component is-unevaluated'}>
      <span className="how-calc__name">{COMPONENT_LABELS[component.name] ?? component.name}</span>
      <span className="how-calc__weight">{Math.round(component.weight * 100)}%</span>
      <span className="how-calc__value">
        {isEvaluated ? Math.round(component.score) : 'Not evaluated'}
      </span>
      <p className="how-calc__detail">{component.detail}</p>
    </li>
  )
}

export default function HowThisIsCalculated({ explanation, results }) {
  if (!explanation) return null

  const topResult = results?.[0]
  const weights = explanation.weights ?? {}

  return (
    <details className="how-calc">
      <summary>How this is calculated</summary>

      <div className="how-calc__body">
        <section>
          <h3>The fit score formula</h3>
          <p className="how-calc__formula">{explanation.formula}</p>
          <p>
            A dimension that cannot be evaluated is <strong>excluded from both halves</strong> of that
            fraction. It is never treated as zero, and it never drags the score down. This is why a
            scholarship with sparse published data can still show a high fit score alongside a lower
            confidence: there was simply less to measure.
          </p>
        </section>

        <section>
          <h3>Component weights</h3>
          <ul className="how-calc__weights">
            {Object.entries(weights).map(([name, weight]) => (
              <li key={name}>
                <span>{COMPONENT_LABELS[name] ?? name}</span>
                <span>{Math.round(weight * 100)}%</span>
              </li>
            ))}
          </ul>
        </section>

        {topResult && (
          <section>
            <h3>Dimensions evaluated for the top result</h3>
            <p className="how-calc__subject">{topResult.scholarship_name}</p>
            <ul className="how-calc__components">
              {topResult.score_breakdown.map((component) => (
                <PercentLabel key={component.name} component={component} />
              ))}
            </ul>
            <p className="how-calc__coverage">
              {topResult.data_coverage}% of the total weight could be evaluated for this scholarship. The
              remainder belongs to dimensions with no published data behind them.
            </p>
          </section>
        )}

        <section>
          <h3>How your grades are read</h3>
          <p>{explanation.normalisation_note}</p>
        </section>

        <section>
          <h3>How confidence is calculated</h3>
          <p className="how-calc__formula">{explanation.confidence_formula}</p>
          <p>
            Confidence describes the scholarship record, not the applicant. A scholarship can match you
            strongly while its own published details are thin, and the interface will show a high fit with
            a medium or low confidence rather than hiding the gap.
          </p>
        </section>

        <section>
          <h3>How the Academic Profile Index is calculated</h3>
          <p className="how-calc__formula">{explanation.profile_index_formula}</p>
          <p>
            The index summarises the academic evidence you supplied. It is not a measure of ability, worth
            or admission likelihood, and the bands are ScholarZone&rsquo;s own classification of the data
            you provided.
          </p>
        </section>

        <section className="how-calc__versions">
          <h3>Versions</h3>
          <dl>
            <div>
              <dt>Fit engine</dt>
              <dd>{explanation.engine_version}</dd>
            </div>
            <div>
              <dt>Field taxonomy</dt>
              <dd>{explanation.field_taxonomy_version}</dd>
            </div>
            <div>
              <dt>Requirement reader</dt>
              <dd>{explanation.requirement_reader_version}</dd>
            </div>
            <div>
              <dt>Calculated as of</dt>
              <dd>{explanation.as_of}</dd>
            </div>
          </dl>
          <p>
            The same profile, the same scholarship data and the same versions produce the same result.
            There is no model-generated score anywhere in this calculation.
          </p>
        </section>
      </div>
    </details>
  )
}