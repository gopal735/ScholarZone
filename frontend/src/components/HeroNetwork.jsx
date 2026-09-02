import { useCallback, useEffect, useRef, useState } from 'react'

const NETWORK_NODES = [
  { id: 'scholarship', label: 'Scholarship', x: 50, y: 48, core: true, phase: 0, ring: true },
  { id: 'country', label: 'Country', x: 22, y: 24, phase: 1.1, ring: false },
  { id: 'university', label: 'University', x: 78, y: 22, phase: 2.3, ring: false },
  { id: 'degree', label: 'Degree', x: 16, y: 72, phase: 3.7, ring: false },
  { id: 'funding', label: 'Funding', x: 82, y: 74, phase: 4.9, ring: false },
  { id: 'deadline', label: 'Deadline', x: 36, y: 90, phase: 5.4, ring: false },
  { id: 'verified', label: 'Verified', x: 64, y: 14, phase: 0.6, ring: false },
]

const NETWORK_CONNECTIONS = [
  { from: 'scholarship', to: 'country', strength: 1 },
  { from: 'scholarship', to: 'university', strength: 1 },
  { from: 'scholarship', to: 'degree', strength: 0.8 },
  { from: 'scholarship', to: 'funding', strength: 0.8 },
  { from: 'scholarship', to: 'deadline', strength: 0.6 },
  { from: 'scholarship', to: 'verified', strength: 0.9 },
  { from: 'country', to: 'university', strength: 0.5 },
  { from: 'degree', to: 'funding', strength: 0.5 },
  { from: 'deadline', to: 'verified', strength: 0.4 },
]

const POINTER_LERP = 0.06
const DRIFT_AMPLITUDE = 0.6
const DRIFT_SPEED = 8000
const POINTER_INFLUENCE = 0.04
const ACTIVATION_THRESHOLD = 14

function getNode(id) {
  return NETWORK_NODES.find((node) => node.id === id)
}

function getDistance(nodeA, nodeB) {
  const dx = nodeA.x - nodeB.x
  const dy = nodeA.y - nodeB.y
  return Math.sqrt(dx * dx + dy * dy)
}

function findClosestNode(x, y, nodes) {
  let closest = nodes[0]
  let minDist = Infinity
  for (const node of nodes) {
    const dx = node.x - x
    const dy = node.y - y
    const dist = dx * dx + dy * dy
    if (dist < minDist) {
      minDist = dist
      closest = node
    }
  }
  return closest
}

function getInitialReducedMotion() {
  if (typeof window === 'undefined') return true
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches
}

export default function HeroNetwork() {
  const containerRef = useRef(null)
  const [activeNode, setActiveNode] = useState(null)
  const [reducedMotion, setReducedMotion] = useState(getInitialReducedMotion)
  const animFrameRef = useRef(0)
  const pointerRef = useRef({ x: 50, y: 50, targetX: 50, targetY: 50 })
  const activeNodeRef = useRef(null)
  const pointerRafRef = useRef(0)

  useEffect(() => {
    const mq = window.matchMedia('(prefers-reduced-motion: reduce)')
    const handler = (e) => setReducedMotion(e.matches)
    mq.addEventListener('change', handler)
    return () => mq.removeEventListener('change', handler)
  }, [])

  useEffect(() => {
    if (reducedMotion) return

    const container = containerRef.current
    if (!container) return

    const svg = container.querySelector('svg')
    if (!svg) return

    const nodeGroups = svg.querySelectorAll('.sz-network__node')
    const nodeCircles = svg.querySelectorAll('.sz-network__node-circle')
    const pulses = svg.querySelectorAll('.sz-network__pulse')

    const animate = (timestamp) => {
      const pointer = pointerRef.current
      pointer.x += (pointer.targetX - pointer.x) * POINTER_LERP
      pointer.y += (pointer.targetY - pointer.y) * POINTER_LERP

      nodeCircles.forEach((node, i) => {
        const baseY = NETWORK_NODES[i].y
        const phase = NETWORK_NODES[i].phase
        const drift = Math.sin(timestamp / DRIFT_SPEED + phase) * DRIFT_AMPLITUDE
        node.setAttribute('cy', baseY + drift)
      })

      if (nodeGroups.length > 0) {
        const dx = (pointer.x - 50) * POINTER_INFLUENCE
        const dy = (pointer.y - 50) * POINTER_INFLUENCE
        nodeGroups.forEach((group, i) => {
          const depth = NETWORK_NODES[i].core ? 0.3 : 1
          group.style.transform = `translate(${dx * depth}px, ${dy * depth}px)`
        })
      }

      pulses.forEach((pulse, i) => {
        const progress = ((timestamp / 9000 + i * 0.28) % 1)
        const connection = NETWORK_CONNECTIONS[i % NETWORK_CONNECTIONS.length]
        const from = getNode(connection.from)
        const to = getNode(connection.to)
        if (!from || !to) return

        const x = from.x + (to.x - from.x) * progress
        const y = from.y + (to.y - from.y) * progress
        pulse.setAttribute('cx', x)
        pulse.setAttribute('cy', y)
        pulse.style.opacity = (1 - progress) * 0.7
      })

      animFrameRef.current = requestAnimationFrame(animate)
    }

    animFrameRef.current = requestAnimationFrame(animate)
    return () => cancelAnimationFrame(animFrameRef.current)
  }, [reducedMotion])

  const handlePointerMove = useCallback((event) => {
    if (reducedMotion) return
    const container = containerRef.current
    if (!container) return

    const rect = container.getBoundingClientRect()
    const x = ((event.clientX - rect.left) / rect.width) * 100
    const y = ((event.clientY - rect.top) / rect.height) * 100

    pointerRef.current.targetX = x
    pointerRef.current.targetY = y

    if (pointerRafRef.current) return

    pointerRafRef.current = requestAnimationFrame(() => {
      const pointer = pointerRef.current
      const closest = findClosestNode(pointer.x, pointer.y, NETWORK_NODES)
      const distance = getDistance(closest, { x: pointer.x, y: pointer.y })

      const newActiveId = distance < ACTIVATION_THRESHOLD ? closest.id : null
      if (newActiveId !== activeNodeRef.current) {
        activeNodeRef.current = newActiveId
        setActiveNode(newActiveId)
      }
      pointerRafRef.current = null
    })
  }, [reducedMotion])

  const handlePointerLeave = useCallback(() => {
    pointerRef.current.targetX = 50
    pointerRef.current.targetY = 50
    if (activeNodeRef.current !== null) {
      activeNodeRef.current = null
      setActiveNode(null)
    }
  }, [])

  return (
    <div
      ref={containerRef}
      className="sz-network"
      aria-hidden="true"
      onPointerMove={handlePointerMove}
      onPointerLeave={handlePointerLeave}
    >
      <svg
        viewBox="0 0 100 100"
        className="sz-network__svg"
        preserveAspectRatio="xMidYMid slice"
      >
        <defs>
          <radialGradient id="sz-network-glow-core" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor="var(--sz-gold)" stopOpacity="0.35" />
            <stop offset="60%" stopColor="var(--sz-gold)" stopOpacity="0.08" />
            <stop offset="100%" stopColor="var(--sz-gold)" stopOpacity="0" />
          </radialGradient>
          <radialGradient id="sz-network-glow-node" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor="var(--sz-gold)" stopOpacity="0.2" />
            <stop offset="100%" stopColor="var(--sz-gold)" stopOpacity="0" />
          </radialGradient>
          <filter id="sz-network-blur" x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur in="SourceGraphic" stdDeviation="0.3" />
          </filter>
        </defs>

        {NETWORK_CONNECTIONS.map((connection, i) => {
          const from = getNode(connection.from)
          const to = getNode(connection.to)
          if (!from || !to) return null
          return (
            <line
              key={`line-${i}`}
              className="sz-network__line"
              x1={from.x}
              y1={from.y}
              x2={to.x}
              y2={to.y}
              strokeOpacity={connection.strength * 0.35}
            />
          )
        })}

        {!reducedMotion && NETWORK_CONNECTIONS.slice(0, 6).map((_, i) => (
          <circle
            key={`pulse-${i}`}
            className="sz-network__pulse"
            cx="50"
            cy="50"
            r="0.4"
            fill="var(--sz-gold)"
          />
        ))}

        {NETWORK_NODES.map((node) => {
          const distance = activeNode && !reducedMotion
            ? getDistance(node, NETWORK_NODES.find((n) => n.id === activeNode) || node)
            : Infinity
          const isActive = node.id === activeNode
          const isNeighbor = activeNode && distance < 28 && !isActive
          const isDimmed = activeNode && !isActive && !isNeighbor
          const className = [
            'sz-network__node',
            node.core ? 'sz-network__node--core' : '',
            isActive ? 'is-active' : '',
            isNeighbor ? 'is-neighbor' : '',
            isDimmed ? 'is-dimmed' : '',
          ].filter(Boolean).join(' ')

          return (
            <g key={node.id} className={className}>
              {node.core && (
                <circle
                  className="sz-network__node-glow"
                  cx={node.x}
                  cy={node.y}
                  r="5"
                  fill="url(#sz-network-glow-core)"
                />
              )}
              {!node.core && (
                <circle
                  className="sz-network__node-glow"
                  cx={node.x}
                  cy={node.y}
                  r="2.5"
                  fill="url(#sz-network-glow-node)"
                />
              )}
              <circle
                className="sz-network__node-circle"
                cx={node.x}
                cy={node.y}
                r={node.core ? 1.6 : 1.0}
                fill={node.core ? 'var(--sz-gold)' : 'var(--sz-ink)'}
              />
              {node.core && (
                <circle
                  className="sz-network__node-ring"
                  cx={node.x}
                  cy={node.y}
                  r="2.8"
                  fill="none"
                  stroke="var(--sz-gold)"
                  strokeWidth="0.08"
                  strokeOpacity="0.4"
                />
              )}
              <text
                className="sz-network__node-label"
                x={node.x}
                y={node.y - 3.2}
                textAnchor="middle"
              >
                {node.label}
              </text>
            </g>
          )
        })}
      </svg>
    </div>
  )
}
