import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import { AuthServiceUnavailableError } from '../services/authService'
import './AuthForm.css'

const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

function validateForm(mode, values) {
  const errors = {}

  if (!values.email.trim()) {
    errors.email = 'Enter your email address.'
  } else if (!emailPattern.test(values.email.trim())) {
    errors.email = 'Enter a valid email address.'
  }

  if (!values.password) {
    errors.password = 'Enter your password.'
  } else if (values.password.length < 8 || !/\d/.test(values.password)) {
    errors.password = 'Use at least 8 characters, including a number.'
  }

  if (mode === 'register' && !values.confirmPassword) {
    errors.confirmPassword = 'Confirm your password.'
  } else if (mode === 'register' && values.confirmPassword !== values.password) {
    errors.confirmPassword = 'Passwords do not match.'
  }

  return errors
}

function PasswordField({ id, label, value, onChange, error, showPassword, onToggle, autoComplete, hint }) {
  const errorId = `${id}-error`

  return (
    <div className="auth-form__field">
      <div className="auth-form__label-row">
        <label htmlFor={id}>{label}</label>
        {hint && <span>{hint}</span>}
      </div>
      <div className="auth-form__password-wrap">
        <input
          id={id}
          type={showPassword ? 'text' : 'password'}
          autoComplete={autoComplete}
          value={value}
          onChange={onChange}
          aria-invalid={Boolean(error)}
          aria-describedby={error ? errorId : undefined}
          minLength="8"
          maxLength="128"
          required
        />
        <button type="button" onClick={onToggle} aria-label={showPassword ? `Hide ${label.toLowerCase()}` : `Show ${label.toLowerCase()}`}>
          {showPassword ? 'Hide' : 'Show'}
        </button>
      </div>
      {error && <p id={errorId} className="auth-form__field-error">{error}</p>}
    </div>
  )
}

export default function AuthForm({ mode }) {
  const isRegister = mode === 'register'
  const { login, register } = useAuth()
  const [values, setValues] = useState({ email: '', password: '', confirmPassword: '' })
  const [errors, setErrors] = useState({})
  const [showPassword, setShowPassword] = useState(false)
  const [showConfirmPassword, setShowConfirmPassword] = useState(false)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [notice, setNotice] = useState(null)

  const title = isRegister ? 'Create your ScholarZone account' : 'Welcome back to ScholarZone'
  const description = isRegister
    ? 'Create an account when secure account services become available.'
    : 'Sign in to manage your scholarships across devices when account services are connected.'

  function updateValue(field, value) {
    setValues((currentValues) => ({ ...currentValues, [field]: value }))
    setErrors((currentErrors) => {
      if (!currentErrors[field]) {
        return currentErrors
      }

      const nextErrors = { ...currentErrors }
      delete nextErrors[field]
      return nextErrors
    })
    setNotice(null)
  }

  async function handleSubmit(event) {
    event.preventDefault()
    const nextErrors = validateForm(mode, values)

    if (Object.keys(nextErrors).length > 0) {
      setErrors(nextErrors)
      setNotice(null)
      return
    }

    setIsSubmitting(true)
    setNotice(null)

    try {
      if (isRegister) {
        await register({ email: values.email.trim(), password: values.password })
        setNotice({ type: 'success', message: 'Your account has been created. You can now sign in.' })
      } else {
        await login({ email: values.email.trim(), password: values.password })
        setNotice({ type: 'success', message: 'You are signed in.' })
      }

      setValues({ email: values.email.trim(), password: '', confirmPassword: '' })
    } catch (error) {
      if (error instanceof AuthServiceUnavailableError) {
        setNotice({
          type: 'info',
          message: 'Account services are not connected yet. Your password was not stored or sent anywhere.',
        })
      } else {
        setNotice({ type: 'error', message: 'We could not complete that request. Please try again later.' })
      }
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <section className="auth-page">
      <div className="auth-page__intro">
        <p className="auth-page__eyebrow">ScholarZone account</p>
        <h1>{title}</h1>
        <p>{description}</p>

        <div className="auth-page__trust">
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <path d="m9 12 2 2 4-4m5-4v6c0 5-3.4 8.7-8 10-4.6-1.3-8-5-8-10V6l8-3 8 3Z" />
          </svg>
          <p><strong>Privacy by design.</strong><span>Passwords stay in this form only until a secure server connection is implemented.</span></p>
        </div>
      </div>

      <div className="auth-form-card">
        <div className="auth-form-card__heading">
          <h2>{isRegister ? 'Create an account' : 'Sign in'}</h2>
          <p>{isRegister ? 'Start with your email and a strong password.' : 'Use your ScholarZone email and password.'}</p>
        </div>

        <form className="auth-form" onSubmit={handleSubmit} noValidate aria-busy={isSubmitting}>
          <div className="auth-form__field">
            <label htmlFor="auth-email">Email address</label>
            <input
              id="auth-email"
              type="email"
              autoComplete="email"
              value={values.email}
              onChange={(event) => updateValue('email', event.target.value)}
              aria-invalid={Boolean(errors.email)}
              aria-describedby={errors.email ? 'auth-email-error' : undefined}
              maxLength="254"
              required
            />
            {errors.email && <p id="auth-email-error" className="auth-form__field-error">{errors.email}</p>}
          </div>

          <PasswordField
            id="auth-password"
            label="Password"
            value={values.password}
            onChange={(event) => updateValue('password', event.target.value)}
            error={errors.password}
            showPassword={showPassword}
            onToggle={() => setShowPassword((currentValue) => !currentValue)}
            autoComplete={isRegister ? 'new-password' : 'current-password'}
            hint={isRegister ? '8+ characters with a number' : undefined}
          />

          {isRegister && (
            <PasswordField
              id="auth-confirm-password"
              label="Confirm password"
              value={values.confirmPassword}
              onChange={(event) => updateValue('confirmPassword', event.target.value)}
              error={errors.confirmPassword}
              showPassword={showConfirmPassword}
              onToggle={() => setShowConfirmPassword((currentValue) => !currentValue)}
              autoComplete="new-password"
            />
          )}

          {notice && (
            <p className={`auth-form__notice auth-form__notice--${notice.type}`} role="status">
              {notice.message}
            </p>
          )}

          <button className="auth-form__submit" type="submit" disabled={isSubmitting}>
            {isSubmitting ? 'Please wait…' : isRegister ? 'Create account' : 'Sign in'}
          </button>
        </form>

        <p className="auth-form-card__switch">
          {isRegister ? 'Already have an account?' : 'New to ScholarZone?'}
          <Link to={isRegister ? '/login' : '/register'}>{isRegister ? 'Sign in' : 'Create an account'}</Link>
        </p>
      </div>
    </section>
  )
}
