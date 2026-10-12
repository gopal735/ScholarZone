/**
 * How the shortlist is being synced, said out loud.
 *
 * `SavedScholarshipsContext` has always computed this state and has always
 * exposed it, and nothing ever read it. The consequence was that a signed-in
 * student whose shortlist had not yet reconciled from the server saw a number
 * with no indication of whether it was current. It is a state the context
 * already knows, so it belongs where a student can see it.
 *
 * `idle` renders nothing: an anonymous visitor has nothing to be told, and a
 * permanent line explaining a sync that is not happening is noise.
 */
export function SyncNotice({ state }) {
  if (state === 'idle') {
    return null
  }

  const copy = {
    syncing: 'Syncing your shortlist…',
    synced: 'Your shortlist is up to date.',
    error: 'Your shortlist could not be synced — showing what this device last had. It will retry when you come back.',
  }[state]

  if (!copy) {
    return null
  }

  return (
    <p
      className="sync-notice"
      role="status"
      data-sync-state={state}
    >
      {copy}
    </p>
  )
}
