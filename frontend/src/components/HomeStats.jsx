import './HomeStats.css'

export default function HomeStats({ stats, isLoading, isUnavailable }) {

  const items = [
    { label: 'Total opportunities', value: stats.total },
    { label: 'Countries covered', value: stats.countries },
    { label: 'Verified active', value: stats.verified_active },
    { label: 'Fully funded', value: stats.fully_funded },
  ]

  return (
    <section className="home-stats" aria-label="ScholarZone coverage">
      <div className="home-stats__inner">
        {items.map((item) => (
          <div key={item.label} className="home-stats__item">
            <strong>
              {isLoading || isUnavailable ? '—' : item.value.toLocaleString()}
            </strong>
            <span>{item.label}</span>
          </div>
        ))}
      </div>
    </section>
  )
}
