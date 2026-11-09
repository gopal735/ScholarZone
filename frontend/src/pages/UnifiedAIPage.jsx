import { useEffect, useRef, useState, useCallback } from 'react'
import { Link } from 'react-router-dom'
import DOMPurify from 'dompurify'
import { 
  askUnifiedAI, 
  getAIStatus, 
  formatUnifiedResponse, 
  setLocalAIEnabled,
  isLocalAIEnabled 
} from '../services/unifiedAI'
import { MentorRateLimitedError, MentorValidationError, MentorUnavailableError } from '../services/mentorService'
import './UnifiedAIPage.css'

const SUGGESTED_PROMPTS = [
  { category: 'Discovery', prompt: "Find fully funded Master's scholarships in Germany", icon: '🔍' },
  { category: 'Discovery', prompt: 'Find PhD scholarships with stipend in Europe', icon: '🔍' },
  { category: 'Comparison', prompt: 'Compare DAAD and Erasmus Mundus funding', icon: '⚖️' },
  { category: 'Comparison', prompt: 'Compare Chevening and Commonwealth scholarships', icon: '⚖️' },
  { category: 'Eligibility', prompt: 'What are the eligibility requirements for Chevening?', icon: '✓' },
  { category: 'Eligibility', prompt: "Can I apply for European master's with IELTS 6.5?", icon: '✓' },
  { category: 'Application', prompt: 'How do I write a strong Statement of Purpose for MEXT?', icon: '📝' },
  { category: 'Application', prompt: 'What documents are needed for Australia Awards?', icon: '📝' },
  { category: 'Deadlines', prompt: 'Which scholarships have deadlines in the next 30 days?', icon: '📅' },
  { category: 'Deadlines', prompt: 'Show me upcoming scholarship opportunities', icon: '📅' },
]

function WelcomeScreen({ onSuggestionClick }) {
  const groupedPrompts = SUGGESTED_PROMPTS.reduce((acc, item) => {
    if (!acc[item.category]) acc[item.category] = []
    acc[item.category].push(item)
    return acc
  }, {})

  return (
    <div className="unified-ai-welcome" role="region" aria-label="Suggested prompts">
      <div className="welcome-content">
        <div className="welcome-icon" aria-hidden="true">🎓</div>
        <h2>How can I help with your scholarship search?</h2>
        <p>Ask me about scholarships, eligibility, deadlines, funding, applications, or anything else.</p>
        
        <div className="suggested-categories">
          {Object.entries(groupedPrompts).map(([category, prompts]) => (
            <div key={category} className="prompt-category">
              <div className="category-header">{category}</div>
              <div className="category-prompts">
                {prompts.map((item, i) => (
                  <button
                    key={`${category}-${i}`}
                    type="button"
                    className="suggested-prompt"
                    onClick={() => onSuggestionClick(item.prompt)}
                    aria-label={item.prompt}
                  >
                    <span className="prompt-icon" aria-hidden="true">{item.icon}</span>
                    <span className="prompt-text">{item.prompt}</span>
                  </button>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

function MessageList({ messages, messagesEndRef }) {
  return (
    <>
      {messages.map((message, index) => (
        <div 
          key={index} 
          className={`message message--${message.role}`}
          role={message.role === 'assistant' ? 'article' : undefined}
          aria-label={message.role === 'assistant' ? 'AI response' : 'Your message'}
          data-testid={`message-${index + 1}`}
        >
          <div className="message-content">
            {message.role === 'assistant' && message.label && (
              <span 
                className="grounded-badge" 
                data-grounded={message.grounded ? 'true' : 'false'}
                aria-label={message.grounded ? 'Grounded in ScholarZone records' : 'AI-generated response'}
              >
                {message.label}
              </span>
            )}
            <div 
              className="message-text" 
              dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(message.content.replace(/\n/g, '<br>')) }} 
            />
            
            {message.sources && message.sources.length > 0 && (
              <div className="message-sources">
                <strong>Sources:</strong>
                <ul>
                  {message.sources.map((source, i) => (
                    <li key={i}>
                      {source.type === 'scholarship' && source.url ? (
                        <a href={source.url} target="_blank" rel="noopener noreferrer">
                          {source.title}
                        </a>
                      ) : (
                        source.title
                      )}
                      {source.type !== 'scholarship' && ` (${source.type})`}
                    </li>
                  ))}
                </ul>
              </div>
            )}
            
            {message.error && (
              <div className="message-error" role="alert">
                <p>{message.error.message}</p>
                {message.error.retryable && (
                  <button 
                    type="button" 
                    className="retry-btn" 
                    onClick={() => window.location.reload()}
                  >
                    Try Again
                  </button>
                )}
              </div>
            )}
          </div>
        </div>
      ))}
      <div ref={messagesEndRef} />
    </>
  )
}

function LoadingIndicator({ activeMode }) {
  return (
    <div className="message message--assistant message--loading" role="status" aria-live="polite" aria-label="AI is responding">
      <div className="message-content">
        <div className="loading-indicator" aria-hidden="true">
          <span></span><span></span><span></span>
        </div>
        <p className="loading-text">
          {activeMode !== 'grounded' ? 'AI is thinking...' : 'Searching ScholarZone records...'}
        </p>
      </div>
    </div>
  )
}

function SettingsPanel({ 
  showSettings, 
  setShowSettings, 
  localAIEnabled, 
  handleLocalAIToggle,
  aiStatus,
  mentorOverview
}) {
  if (!showSettings) return null
  
  return (
    <div 
      className="ai-settings-panel" 
      role="dialog" 
      aria-label="AI Settings"
      aria-modal="true"
    >
      <div className="settings-content">
        <h3>AI Configuration</h3>
        
        <div className="setting-item">
          <label className="setting-label">
            <input
              type="checkbox"
              checked={localAIEnabled}
              onChange={(e) => handleLocalAIToggle(e.target.checked)}
              id="local-ai-toggle"
            />
            <span className="setting-text">
              <strong>Enable Local AI (On-Device)</strong>
              <small>Downloads a quantized model (~60MB) to run inference in your browser. Works offline, no data leaves your device.</small>
            </span>
          </label>
          {localAIEnabled && aiStatus.localAIModelReady ? (
            <div className="setting-status">✓ Model ready</div>
          ) : localAIEnabled ? (
            <div className="setting-status" style={{ color: 'var(--warning)' }}>⚠ Not implemented (placeholder only)</div>
          ) : null}
        </div>

        <div className="setting-item">
          <label className="setting-label">
            <strong>Remote AI (Free Tier)</strong>
            <small>Uses free Hugging Face Inference API (quota-limited). Requires backend proxy.</small>
          </label>
          <div className="setting-status" style={{ color: aiStatus.remoteAI ? 'var(--success)' : 'var(--danger)' }}>
            {aiStatus.remoteAI ? '✓ Available' : '✗ Unavailable (backend proxy not configured)'}
          </div>
        </div>

        <div className="setting-item">
          <label className="setting-label">
            <strong>Grounded Catalogue Mode</strong>
            <small>Always available. Deterministic retrieval from 770+ verified scholarship records.</small>
          </label>
          <div className="setting-status">✓ Always active</div>
        </div>

        <div className="setting-item">
          <label className="setting-label">
            <strong>Personalized Mentor</strong>
            <small>Requires sign-in. Uses your profile, target degrees, saved scholarships, and application workspace.</small>
          </label>
          <div className="setting-status" style={{ color: mentorOverview ? 'var(--success)' : 'var(--danger)' }}>
            {mentorOverview ? '✓ Active' : '✗ Sign in to enable'}
          </div>
        </div>

        <button 
          type="button" 
          className="close-settings" 
          onClick={() => setShowSettings(false)}
        >
          Done
        </button>
      </div>
    </div>
  )
}

function Header({ mentorOverview, aiStatus, showSettings, setShowSettings }) {
  const getModeBadge = useCallback(() => {
    if (aiStatus.activeMode === 'mentor') return { text: 'Grounded Mentor', mode: 'mentor' }
    if (aiStatus.activeMode === 'local_ai') return { text: 'Local AI', mode: 'local_ai' }
    if (aiStatus.activeMode === 'remote_ai') return { text: 'Remote AI', mode: 'remote_ai' }
    return { text: 'Grounded Search', mode: 'grounded' }
  }, [aiStatus.activeMode])

  const badge = getModeBadge()

  return (
    <header className="unified-ai-header">
      <div className="unified-ai-title">
        <h1>ScholarZone AI Assistant</h1>
        <p className="unified-ai-subtitle">
          {mentorOverview 
            ? 'Personalized scholarship guidance from your profile and records'
            : 'Scholarship discovery, comparison, eligibility & application guidance'}
        </p>
      </div>
      <div className="unified-ai-status">
        <span className={`mode-badge`} data-mode={badge.mode} data-testid="mode-badge">
          {badge.text}
        </span>
        {!mentorOverview && (
          <button 
            type="button" 
            className="sign-in-prompt"
            onClick={() => window.location.href = '/login?redirect=/assistant'}
          >
            Sign in for personalized Mentor
          </button>
        )}
        <button 
          type="button" 
          className="settings-btn"
          onClick={() => setShowSettings(!showSettings)}
          aria-expanded={showSettings}
          aria-label="AI Settings"
          aria-controls="ai-settings-panel"
        >
          ⚙️
        </button>
      </div>
    </header>
  )
}

function Disclaimer({ activeMode }) {
  const isGrounded = activeMode === 'grounded'
  
  return (
    <div className="unified-ai-disclaimer" role="note" aria-live="polite">
      <strong>Important:</strong> 
      {isGrounded
        ? 'Running in grounded mode. Answers are composed from verified ScholarZone scholarship records — not generated by an LLM. No AI inference is taking place.'
        : 'This AI assistant uses a large language model. Answers may contain inaccuracies. Always verify scholarship details on official provider websites. Source citations are provided where available.'}
    </div>
  )
}

function ChatArea({ messages, isLoading, activeMode, messagesEndRef, onSuggestionClick }) {
  return (
    <div 
      className="unified-ai-chat" 
      role="log" 
      aria-live="polite" 
      aria-label="Conversation"
    >
      {messages.length === 0 ? (
        <WelcomeScreen onSuggestionClick={onSuggestionClick} />
      ) : (
        <>
          <MessageList messages={messages} messagesEndRef={messagesEndRef} />
          {isLoading && <LoadingIndicator activeMode={activeMode} />}
        </>
      )}
    </div>
  )
}

function InputForm({ input, setInput, isLoading, mentorOverview, onSubmit, inputRef }) {
  const handleKeyDown = useCallback((e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      onSubmit(e)
    }
  }, [onSubmit])

  return (
    <form className="unified-ai-input" onSubmit={onSubmit}>
      <label htmlFor="ai-input" className="visually-hidden">Ask a question</label>
      <textarea
        ref={inputRef}
        id="ai-input"
        data-testid="ai-input"
        value={input}
        onChange={(e) => setInput(e.target.value)}
        placeholder={mentorOverview 
          ? 'Ask about your scholarships, applications, or get personalized guidance...'
          : "Ask about scholarships... (e.g., \"Find fully funded Master's in Germany with October deadlines\")"}
        rows={1}
        disabled={isLoading}
        onKeyDown={handleKeyDown}
        aria-describedby="input-hint"
      />
      <div id="input-hint" className="visually-hidden">Press Enter to send, Shift+Enter for new line</div>
      <button 
        type="submit" 
        disabled={!input.trim() || isLoading}
        className="send-btn"
        aria-label="Send question"
      >
        <svg viewBox="0 0 24 24" aria-hidden="true" width="20" height="20">
          <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z" />
        </svg>
      </button>
    </form>
  )
}

function Footer() {
  return (
    <footer className="unified-ai-footer">
      <p>
        <Link to="/scholarships">Browse Directory</Link> · 
        <Link to="/match">Check Eligibility</Link> · 
        <Link to="/compare">Compare Scholarships</Link> · 
        <Link to="/applications">Application Workspace</Link>
      </p>
      <p className="privacy-note">
        Your questions are processed and discarded. No conversation history is stored.
      </p>
    </footer>
  )
}

export default function UnifiedAIPage() {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [aiStatus, setAiStatus] = useState({ mentor: false, remoteAI: false, localAI: false, localAIEnabled: false, localAIModelReady: false, grounded: true, activeMode: 'grounded' })
  const [showSettings, setShowSettings] = useState(false)
  const [localAIEnabled, setLocalAIEnabledState] = useState(false)
  const [mentorOverview, setMentorOverview] = useState(null)
  const messagesEndRef = useRef(null)
  const inputRef = useRef(null)

  const initializeAI = async () => {
    const status = await getAIStatus()
    setAiStatus(status)
    setLocalAIEnabledState(isLocalAIEnabled())
    
    try {
      const { fetchMentorOverview } = await import('../services/mentorService')
      const overview = await fetchMentorOverview()
      setMentorOverview(overview)
    } catch (err) {
      void err
    }
  }

  useEffect(() => {
    const mounted = { current: true }
    const init = async () => {
      await initializeAI()
      if (!mounted.current) return
    }
    init()
    return () => { mounted.current = false }
  }, [])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!input.trim() || isLoading) return

    const userMessage = input.trim()
    setInput('')
    setIsLoading(true)

    setMessages(prev => [...prev, { 
      role: 'user', 
      content: userMessage,
      timestamp: Date.now()
    }])

    try {
      const response = await askUnifiedAI(userMessage, {
        context: {
          conversationHistory: messages.slice(-6).map(m => ({
            role: m.role,
            content: m.content
          })),
          mentorOverview,
        }
      })

      let responseMode = aiStatus.activeMode
      if (response.grounded) responseMode = 'grounded'

      const formatted = formatUnifiedResponse(response, responseMode)

      setMessages(prev => [...prev, {
        role: 'assistant',
        content: formatted.answer,
        sources: formatted.sources,
        grounded: formatted.grounded,
        model: formatted.model,
        tokensUsed: formatted.tokensUsed,
        sourceType: formatted.sourceType,
        label: formatted.label,
        timestamp: Date.now()
      }])
    } catch (error) {
      let errorMessage = 'An unexpected error occurred.'
      let retryable = false

      if (error instanceof MentorRateLimitedError) {
        errorMessage = `Rate limited. Please wait ${error.retryAfterSeconds} seconds before asking again.`
        retryable = true
      } else if (error instanceof MentorValidationError) {
        errorMessage = error.message
      } else if (error instanceof MentorUnavailableError) {
        errorMessage = 'Mentor service is temporarily unavailable. Using grounded search instead.'
        try {
          const { askAIAssistant } = await import('../services/aiAssistant')
          const fallback = await askAIAssistant({ question: userMessage })
          const formatted = formatUnifiedResponse(fallback, 'grounded')
          setMessages(prev => [...prev, {
            role: 'assistant',
            content: formatted.answer,
            sources: formatted.sources,
            grounded: formatted.grounded,
            sourceType: 'grounded',
            label: '📋 Grounded Search (fallback)',
            timestamp: Date.now()
          }])
          setIsLoading(false)
          inputRef.current?.focus()
          return
        } catch (fallbackErr) {
          void fallbackErr
        }
      } else if (error?.error) {
        errorMessage = error.error
        retryable = error.retryable
      }

      setMessages(prev => [...prev, {
        role: 'assistant',
        content: errorMessage,
        error: { message: errorMessage, retryable },
        timestamp: Date.now()
      }])
    } finally {
      setIsLoading(false)
      inputRef.current?.focus()
    }
  }

  const handleSuggestionClick = (prompt) => {
    setInput(prompt)
    inputRef.current?.focus()
  }

  const handleLocalAIToggle = (enabled) => {
    setLocalAIEnabled(enabled)
    setLocalAIEnabledState(enabled)
    getAIStatus().then(setAiStatus)
  }

  return (
    <div className="unified-ai-page">
      <Header 
        mentorOverview={mentorOverview} 
        aiStatus={aiStatus} 
        showSettings={showSettings}
        setShowSettings={setShowSettings}
      />
      {showSettings && (
        <SettingsPanel 
          showSettings={showSettings}
          setShowSettings={setShowSettings}
          localAIEnabled={localAIEnabled}
          handleLocalAIToggle={handleLocalAIToggle}
          aiStatus={aiStatus}
          mentorOverview={mentorOverview}
        />
      )}
      <Disclaimer activeMode={aiStatus.activeMode} />
      <ChatArea 
        messages={messages} 
        isLoading={isLoading} 
        activeMode={aiStatus.activeMode}
        messagesEndRef={messagesEndRef}
        onSuggestionClick={handleSuggestionClick}
      />
      <InputForm
        input={input}
        setInput={setInput}
        isLoading={isLoading}
        mentorOverview={mentorOverview}
        onSubmit={handleSubmit}
        inputRef={inputRef}
      />
      <Footer />
    </div>
  )
}