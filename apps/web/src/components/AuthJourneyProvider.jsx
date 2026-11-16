import { useEffect, useRef, useState } from 'react'
import { AuthJourneyContext } from '../context/AuthJourneyContext'
import './AuthJourney.css'

// Lives above route guards, so successful authentication cannot cut off the scene.
export default function AuthJourneyProvider({ children }) {
  const [journey, setJourney] = useState(null)
  const [motionEnabled, setMotionEnabled] = useState(true)
  const locked = useRef(false)
  const wait = useRef(null)
  const mounted = useRef(true)
  useEffect(() => {
    mounted.current = true
    return () => { mounted.current = false; if (wait.current) { clearTimeout(wait.current.timer); wait.current.resolve() } }
  }, [])
  const run = async (scene, operation, navigate) => {
    if (locked.current) return
    locked.current = true
    setJourney({ scene, phase: 'pending' })
    try {
      const result = await operation?.()
      if (result === false) return
      if (!mounted.current) return
      const reduced = !motionEnabled
      setJourney({ scene, phase: 'playing', reduced })
      await new Promise(resolve => { wait.current = { resolve, timer: setTimeout(resolve, reduced ? 450 : 1100) } })
      if (mounted.current) navigate()
    } finally {
      locked.current = false; wait.current = null
      if (mounted.current) setJourney(null)
    }
  }
  return <AuthJourneyContext.Provider value={{ holding: Boolean(journey), motionEnabled, setMotionEnabled, run }}>
    <div className="auth-journey-content" inert={journey?.phase === 'playing' || undefined} data-auth-journey={journey?.phase || 'idle'}>{children}</div>
    {journey?.phase === 'playing' && <div className="auth-journey" data-scene={journey.scene} data-reduced={journey.reduced} aria-hidden="true">
      <div className="auth-journey-landscape" /><div className="auth-journey-library" /><div className="auth-journey-light" />
    </div>}
  </AuthJourneyContext.Provider>
}
