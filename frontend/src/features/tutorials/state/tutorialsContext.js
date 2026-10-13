import { createContext, useContext } from 'react'

/**
 * The context object for the tutorials feature's shared state.
 *
 * Separate from the provider file because the provider is a component and the
 * eslint rule for fast refresh wants a file to export only components. The hook
 * imports this and the provider file offers the one component.
 */
const TutorialsContext = createContext(null)

/** The shared state, or null when no provider is mounted. */
export function useSharedTutorialState() {
  return useContext(TutorialsContext)
}

export { TutorialsContext }
