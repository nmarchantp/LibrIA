import { useId } from 'react'
import CandleFlameShape from './CandleFlameShape'

// One proportional coordinate system keeps the moving flame on the image wick.
export default function SidebarCandle({ animated }) {
  const id = useId().replaceAll(':', '')
  return <span className="sidebar-candle-reactor" data-animated={animated ? 'true' : 'false'} aria-hidden="true">
    <svg viewBox="0 0 1200 1300" preserveAspectRatio="xMidYMax meet" className="sidebar-candle-art" focusable="false">
      <defs>
        <mask id={`${id}-mask`} maskUnits="userSpaceOnUse" x="0" y="0" width="1200" height="1300">
          <rect width="1200" height="1300" fill="white" />
          <ellipse cx="890" cy="118" rx="78" ry="110" fill="black" />
        </mask>
        <linearGradient id={`${id}-fire`} x1="0" y1="1" x2="0" y2="0">
          <stop offset="0" stopColor="#F79429" /><stop offset=".45" stopColor="#FFC64E" /><stop offset="1" stopColor="#FFF4BA" />
        </linearGradient>
        <radialGradient id={`${id}-glow`}><stop stopColor="#FFCE6F" stopOpacity=".35" /><stop offset="1" stopColor="#FFAE40" stopOpacity="0" /></radialGradient>
      </defs>
      <image href="/images/blood-universe/candle-books-v1.webp" width="1200" height="1300" mask={`url(#${id}-mask)`} />
      <g className="sidebar-candle-flame">
        <rect x="790" y="0" width="200" height="255" fill="transparent" className="sidebar-candle-hit" />
        <CandleFlameShape fireId={`${id}-fire`} glowId={`${id}-glow`} />
      </g>
    </svg>
  </span>
}
