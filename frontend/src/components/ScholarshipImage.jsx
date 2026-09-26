import { useState } from 'react'
import './ScholarshipImage.css'

const IMAGE_ASPECT_RATIO_CLASS = 'scholarship-image__ratio'
const RETRY_ATTEMPTS = 2

/* The API returns an enum such as "official_scholarship". Rendering it
   raw put OFFICIAL_SCHOLARSHIP in the pill. This only reformats the
   existing value; the untouched value stays in the title attribute. */
function formatSourceType(sourceType) {
  if (typeof sourceType !== 'string' || !sourceType.trim()) return sourceType
  return sourceType.trim().replace(/[_-]+/g, ' ')
}

function ImageContent({ imageUrl, altText, onError, onLoad }) {
  return (
    <img
      src={imageUrl}
      alt={altText}
      className="scholarship-image__img"
      loading="lazy"
      decoding="async"
      onError={onError}
      onLoad={onLoad}
    />
  )
}

export default function ScholarshipImage({ scholarship, className = '' }) {
  const imageUrl = scholarship?.image_url || scholarship?.imageUrl
  const altText = scholarship?.image_alt_text || `${scholarship?.title ?? 'Scholarship'} official image`
  const sourceType = scholarship?.image_source_type || scholarship?.imageSourceType || null
  const [hasError, setHasError] = useState(false)
  const [retryKey, setRetryKey] = useState(0)
  const [isLoaded, setIsLoaded] = useState(false)

  const handleError = () => {
    if (retryKey < RETRY_ATTEMPTS) {
      setIsLoaded(false)
      setRetryKey((prev) => prev + 1)
    } else {
      setHasError(true)
    }
  }

  const handleLoad = () => {
    setIsLoaded(true)
  }

  if (!imageUrl || typeof imageUrl !== 'string' || imageUrl.trim() === '') {
    return (
      <div
        className={`scholarship-image scholarship-image--placeholder ${IMAGE_ASPECT_RATIO_CLASS} ${className}`.trim()}
        aria-label="No image available"
      >
        <svg className="scholarship-image__icon" viewBox="0 0 24 24" aria-hidden="true">
          <path d="M21 12v3a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2h3m4 0 3 3 3-3m0 0V5a2 2 0 0 1 2-2h3" />
        </svg>
      </div>
    )
  }

  if (hasError) {
    return (
      <div
        className={`scholarship-image scholarship-image--broken ${IMAGE_ASPECT_RATIO_CLASS} ${className}`.trim()}
        aria-label="Image failed to load"
      >
        <svg className="scholarship-image__icon" viewBox="0 0 24 24" aria-hidden="true">
          <path d="M21 12v3a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2h3m4 0 3 3 3-3m0 0V5a2 2 0 0 1 2-2h3" />
        </svg>
      </div>
    )
  }

  const wrapperClasses = [
    'scholarship-image',
    IMAGE_ASPECT_RATIO_CLASS,
    className,
  ].filter(Boolean).join(' ')

  return (
    <div className={wrapperClasses} data-loaded={isLoaded || undefined}>
      <ImageContent
        key={retryKey}
        imageUrl={imageUrl}
        altText={altText}
        onError={handleError}
        onLoad={handleLoad}
      />
      {sourceType && (
        <span className="scholarship-image__source-indicator" title={`Source type: ${sourceType}`}>
          {formatSourceType(sourceType)}
        </span>
      )}
    </div>
  )
}
