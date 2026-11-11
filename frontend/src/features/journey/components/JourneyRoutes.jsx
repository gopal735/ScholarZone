import { Outlet } from 'react-router-dom'
import { JourneyProvider } from '../state/JourneyProvider.jsx'

/**
 * Route wrapper that mounts JourneyProvider around journey child routes.
 *
 * The provider must be inside the React Router context so useLocation()
 * works correctly. This component is rendered as a parent route element
 * with an Outlet for the actual journey pages.
 */
export function JourneyRoutes() {
  return (
    <JourneyProvider>
      <Outlet />
    </JourneyProvider>
  )
}

export default JourneyRoutes