import { classifyLifecycle, formatCountdown, formatOpeningCountdown } from '../utils/lifecycle';
import './LifecycleBadge.css';

export function LifecycleBadge({ 
  scholarship, 
  lifecycle, 
  showCountdown = true,
  size = 'default' // 'default' | 'compact' | 'detailed'
}) {
  const displayLifecycle = lifecycle || classifyLifecycle(scholarship);
  
  const deadlineCountdown = showCountdown && displayLifecycle.showCountdown 
    ? formatCountdown(displayLifecycle.daysUntilDeadline, displayLifecycle.isExactDeadline)
    : null;

  const openingCountdown = showCountdown && displayLifecycle.showOpeningDate && displayLifecycle.daysUntilOpening !== null
    ? formatOpeningCountdown(displayLifecycle.daysUntilOpening, displayLifecycle.isExactOpening)
    : null;

  return (
    <div className={`lifecycle-badge-container ${size}`}>
      <span 
        className={`lifecycle-badge ${displayLifecycle.className}`}
        data-lifecycle={displayLifecycle.status}
        data-days-until={displayLifecycle.daysUntilDeadline}
        data-days-until-opening={displayLifecycle.daysUntilOpening}
      >
        {displayLifecycle.label}
      </span>
      
      {deadlineCountdown && size !== 'compact' && (
        <span className={`lifecycle-countdown ${displayLifecycle.className}`}>
          {deadlineCountdown}
        </span>
      )}
      
      {openingCountdown && size !== 'compact' && (
        <span className={`lifecycle-opening-countdown ${displayLifecycle.className}`}>
          {openingCountdown}
        </span>
      )}
      
      {size === 'detailed' && displayLifecycle.deadlineDate && (
        <span className="lifecycle-deadline-date">
          Deadline: {displayLifecycle.deadlineDate.toLocaleDateString('en-GB', { 
            day: 'numeric', 
            month: 'short', 
            year: 'numeric' 
          })}
        </span>
      )}

      {size === 'detailed' && displayLifecycle.openingDate && (
        <span className="lifecycle-opening-date">
          Opens: {displayLifecycle.openingDate.toLocaleDateString('en-GB', { 
            day: 'numeric', 
            month: 'short', 
            year: 'numeric' 
          })}
        </span>
      )}
    </div>
  );
}

export default LifecycleBadge;