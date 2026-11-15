import { useEffect, useRef } from 'react'

const stars = Array.from({ length: 120 }, (_, index) => ({
  left: `${(index * 37.73 + 3) % 100}%`, top: `${(index * 61.37 + 7) % 100}%`,
  '--size': `${index % 3 === 0 ? 3 : 1.7}px`, '--duration': `${1.5 + (index % 11) / 4}s`, '--delay': `${-index * .47}s`,
}))

export default function LoginUniverse({ motionEnabled = true }) {
  const shooting = useRef(null)
  useEffect(() => {
    if (!motionEnabled) return
    let timer, animation
    let first = true
    const schedule = () => {
      clearTimeout(timer)
      if (document.hidden) return
      timer = setTimeout(() => {
        const element = shooting.current
        if (!element) return
        element.style.left = `${Math.random() > .5 ? 72 + Math.random() * 24 : 18 + Math.random() * 20}%`
        element.style.top = `${4 + Math.random() * 25}%`
        element.style.width = `${140 + Math.random() * 90}px`
        animation = element.animate([
          { transform: 'rotate(-35deg) translateX(0)', opacity: 0 },
          { opacity: 1, offset: .15 },
          { transform: 'rotate(-35deg) translateX(-420px)', opacity: 0 },
        ], { duration: 1500 + Math.random() * 500, easing: 'ease-out' })
        schedule()
      }, first ? 1500 : 12000 + Math.random() * 13000)
      first = false
    }
    const reset = () => { animation?.cancel(); schedule() }
    schedule()
    document.addEventListener('visibilitychange', reset)
    return () => { clearTimeout(timer); animation?.cancel(); document.removeEventListener('visibilitychange', reset) }
  }, [motionEnabled])
  return <div className="login-universe" aria-hidden="true">
    <div className="login-nebula login-nebula-one" /><div className="login-nebula login-nebula-two" />
    <div className="login-stars">{stars.map((style, index) => <span className="login-star" key={index} style={style}><span className="login-star-diagonals" /></span>)}</div>
    {Array.from({ length: 14 }, (_, index) => <span key={index} className="login-lucero" style={{ left: `${8 + (index * 31) % 87}%`, top: `${10 + (index * 19) % 77}%`, '--duration': `${6 + index % 7}s`, '--delay': `${-index * 1.7}s` }}><span className="login-lucero-diagonals" /></span>)}
    <span className="login-shooting-star" ref={shooting}><span className="login-shooting-head"><span className="login-shooting-diagonals" /></span></span>
  </div>
}
