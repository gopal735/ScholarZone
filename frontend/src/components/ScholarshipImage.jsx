import { useState } from 'react'
import './ScholarshipImage.css'

const IMAGE_ASPECT_RATIO_CLASS = 'scholarship-image__ratio'
const RETRY_ATTEMPTS = 2

function ImageContent({ imageUrl, altText, onError }) {
  return (
    <img
      src={imageUrl}
      alt={altText}
      className="scholarship-image__img"
      loading="lazy"
      decoding="async"
      onError={onError}
    />
  )
}

export default function ScholarshipImage({ scholarship, className = '' }) {
  const imageUrl = scholarship?.image_url || scholarship?.imageUrl
  const altText = scholarship?.image_alt_text || `${scholarship?.title ?? 'Scholarship'} official image`
  const sourceType = scholarship?.image_source_type || scholarship?.imageSourceType || null
  const [hasError, setHasError] = useState(false)
  const [retryKey, setRetryKey] = useState(0)

  const handleError = () => {
    if (retryKey < RETRY_ATTEMPTS) {
      setRetryKey((prev) => prev + 1)
    } else {
      setHasError(true)
    }
  }

  if (!imageUrl || typeof imageUrl !== 'string' || imageUrl.trim() === '') {
    return (
      <div className={`scholarship-image scholarship-image--placeholder ${className}`} aria-label="No image available">
        <svg className="scholarship-image__icon" viewBox="0 0 24 24" aria-hidden="true">
          <path d="M21 12v3a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2h3m4 0 3 3 3-3m0 0V5a2 2 0 0 1 2-2h3" />
        </svg>
      </div>
    )
  }

  if (hasError) {
    return (
      <div className={`scholarship-image scholarship-image--broken ${className}`} aria-label="Image failed to load">
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
    <div className={wrapperClasses}>
      <ImageContent
        key={retryKey}
        imageUrl={imageUrl}
        altText={altText}
        sourceType={sourceType}
        onError={handleError}
      />
      {sourceType && (
        <span className="scholarship-image__source-indicator" title={`Source type: ${sourceType}`}>
          {sourceType}
        </span>
      )}
    </div>
  )
}
