import { useEffect, useState } from 'react'

function localGreeting() {
  const hour = new Date().getHours()
  if (hour >= 5 && hour < 12) return 'Buenos días'
  if (hour >= 12 && hour < 20) return 'Buenas tardes'
  return 'Buenas noches'
}

export default function HeaderGreeting({ displayName }) {
  const [greeting, setGreeting] = useState(localGreeting)
  useEffect(() => {
    const update = () => setGreeting(localGreeting())
    const interval = window.setInterval(update, 60_000)
    window.addEventListener('focus', update)
    return () => {
      window.clearInterval(interval)
      window.removeEventListener('focus', update)
    }
  }, [])
  const firstName = typeof displayName === 'string' ? displayName.trim().split(/\s+/)[0] : ''
  return <div className="header-greeting">
    <p className="header-greeting-title">{greeting}{firstName ? `, ${firstName}` : ''}</p>
  </div>
}
