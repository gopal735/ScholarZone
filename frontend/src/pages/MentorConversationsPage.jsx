import { useCallback, useEffect, useRef, useState } from 'react'
import {
  fetchMentorConversations,
  createMentorConversation,
  fetchMentorConversationMessages,
  deleteMentorConversation,
  renameMentorConversation,
  streamMentorConversationMessage,
  cancelMentorMessage,
  retryMentorMessage,
  fetchMentorDiscovery,
} from '../services/mentorService'
import MentorDiscoveryResults from '../components/mentor/MentorDiscoveryResults'

export default function MentorConversationsPage() {
  const [conversations, setConversations] = useState([])
  const [selectedId, setSelectedId] = useState(null)
  const [messages, setMessages] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [input, setInput] = useState('')
  const [streaming, setStreaming] = useState(false)
  const [partial, setPartial] = useState('')
  const [streamingStatus, setStreamingStatus] = useState('')
  const [discoveryOverrides, setDiscoveryOverrides] = useState({})
  const [discoveryLoadingId, setDiscoveryLoadingId] = useState(null)
  const abortRef = useRef(null)
  const activeAssistantIdRef = useRef(null)

  const loadConversations = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const list = await fetchMentorConversations()
      setConversations(Array.isArray(list) ? list : [])
    } catch (e) {
      setError(e?.message || 'Failed to load conversations')
    } finally {
      setLoading(false)
    }
  }, [])

  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { void loadConversations() }, [loadConversations])

  const openConversation = useCallback(async (id) => {
    setSelectedId(id)
    setMessages([])
    setPartial('')
    setError(null)
    try {
      const msgs = await fetchMentorConversationMessages(id)
      setMessages(Array.isArray(msgs) ? msgs : [])
    } catch (e) {
      setError(e?.message || 'Failed to load messages')
    }
  }, [])

  const handleCreate = useCallback(async () => {
    setError(null)
    try {
      const conv = await createMentorConversation('New conversation')
      setConversations((prev) => [conv, ...prev])
      await openConversation(conv.id)
    } catch (e) {
      setError(e?.message || 'Failed to create conversation')
    }
  }, [openConversation])

  const handleDelete = useCallback(async (id) => {
    if (!window.confirm('Delete this conversation?')) return
    setError(null)
    try {
      await deleteMentorConversation(id)
      setConversations((prev) => prev.filter((c) => c.id !== id))
      if (selectedId === id) {
        setSelectedId(null)
        setMessages([])
      }
    } catch (e) {
      setError(e?.message || 'Failed to delete conversation')
    }
  }, [selectedId])

  const handleRename = useCallback(async (id, title) => {
    setError(null)
    try {
      const updated = await renameMentorConversation(id, title)
      setConversations((prev) => prev.map((c) => (c.id === id ? updated : c)))
    } catch (e) {
      setError(e?.message || 'Failed to rename conversation')
    }
  }, [])

  const handleSend = useCallback(async () => {
    if (!selectedId || !input.trim() || streaming) return
    const text = input.trim()
    setInput('')
    setStreaming(true)
    setPartial('')
    setStreamingStatus('streaming')
    setError(null)
    const controller = new AbortController()
    abortRef.current = controller
    try {
      for await (const evt of streamMentorConversationMessage(selectedId, text, { signal: controller.signal })) {
        if (evt.event === 'message_start') {
          activeAssistantIdRef.current = evt.data?.assistant_message_id
        } else if (evt.event === 'token') {
          setPartial((p) => p + (evt.data?.content || ''))
        } else if (evt.event === 'message_complete') {
          setPartial('')
          setStreamingStatus('completed')
        } else if (evt.event === 'message_cancelled') {
          setStreamingStatus('cancelled')
        } else if (evt.event === 'message_error') {
          setStreamingStatus('failed')
          setError(evt.data?.detail || 'Stream failed')
        }
      }
    } catch (e) {
      if (e?.name !== 'AbortError') setError(e?.message || 'Stream failed')
      setStreamingStatus('failed')
    } finally {
      setStreaming(false)
      abortRef.current = null
      // refresh history
      try {
        const msgs = await fetchMentorConversationMessages(selectedId)
        setMessages(Array.isArray(msgs) ? msgs : [])
      } catch { /* ignore */ }
      setPartial('')
    }
  }, [selectedId, input, streaming])

  const handleCancel = useCallback(async () => {
    const aid = activeAssistantIdRef.current
    if (selectedId && aid) {
      try { await cancelMentorMessage(selectedId, aid) } catch { /* ignore */ }
    }
    if (abortRef.current) abortRef.current.abort()
  }, [selectedId])

  const loadDiscoveryPage = useCallback(async (messageId, page) => {
    if (!selectedId) return
    setDiscoveryLoadingId(messageId)
    try {
      const payload = await fetchMentorDiscovery(selectedId, messageId, { page, pageSize: 20 })
      setDiscoveryOverrides((prev) => ({ ...prev, [messageId]: payload }))
    } catch (e) {
      setError(e?.message || 'Failed to load discovery results')
    } finally {
      setDiscoveryLoadingId(null)
    }
  }, [selectedId])
    const handleRetry = useCallback(async (messageId) => {
    if (!selectedId) return
    setError(null)
    try {
      await retryMentorMessage(selectedId, messageId)
      const msgs = await fetchMentorConversationMessages(selectedId)
      setMessages(Array.isArray(msgs) ? msgs : [])
    } catch (e) {
      setError(e?.message || 'Retry failed')
    }
  }, [selectedId])

  return (
    <div className="mentor-page" data-testid="mentor-conversations-page">
      <div className="mentor-page__inner">
        <header className="mentor-page__masthead">
          <h1 className="mentor-page__title">Dream AI Mentor 2</h1>
        </header>
        {error && <div role="alert" data-testid="conversation-error">{error}</div>}
        <div style={{ display: 'flex', gap: '16px' }}>
          <aside style={{ width: 260 }}>
            <button data-testid="new-conversation" onClick={handleCreate}>New conversation</button>
            <ul data-testid="conversation-list">
              {loading && <li data-testid="conversations-loading">Loading…</li>}
              {conversations.map((c) => (
                <li key={c.id} data-testid={`conversation-item-${c.id}`}>
                  <button onClick={() => openConversation(c.id)}>{c.title}</button>
                  <button data-testid={`rename-conversation-${c.id}`} onClick={() => {
                    const t = window.prompt('New title', c.title)
                    if (t) handleRename(c.id, t)
                  }}>Rename</button>
                  <button data-testid={`delete-conversation-${c.id}`} onClick={() => handleDelete(c.id)}>Delete</button>
                </li>
              ))}
            </ul>
          </aside>
          <main style={{ flex: 1 }}>
            {selectedId ? (
              <>
                <ul data-testid="message-list">
                   {messages.map((m) => (
                     <li key={m.id} data-testid={`message-${m.id}`} data-status={m.status}>
                       <strong>{m.role}</strong>: {m.content}
                       {(m.discovery_payload || discoveryOverrides[m.id]) && (
                         <MentorDiscoveryResults
                           payload={discoveryOverrides[m.id] || m.discovery_payload}
                           loading={discoveryLoadingId === m.id}
                           onPageChange={(page) => loadDiscoveryPage(m.id, page)}
                         />
                       )}
                       {m.status === 'failed' || m.status === 'cancelled' ? (
                         <button data-testid={`retry-message-${m.id}`} onClick={() => handleRetry(m.id)}>Retry</button>
                       ) : null}
                     </li>
                   ))}
                  {partial && <li data-testid="streaming-token">{partial}</li>}
                </ul>
                <div className="mentor-composer">
                  <textarea
                    data-testid="message-input"
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    disabled={streaming}
                  />
                  <button data-testid="send-button" onClick={handleSend} disabled={streaming || !input.trim()}>Send</button>
                  {streaming && <button data-testid="cancel-button" onClick={handleCancel}>Cancel</button>}
                </div>
                <div data-testid="streaming-status" aria-live="polite">{streamingStatus}</div>
              </>
            ) : (
              <div data-testid="empty-state">Select or create a conversation</div>
            )}
          </main>
        </div>
      </div>
    </div>
  )
}