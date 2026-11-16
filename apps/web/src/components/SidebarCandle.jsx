import { useId } from 'react'

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
        <g className="sidebar-candle-flame-shape">
          <ellipse cx="890" cy="135" rx="110" ry="145" fill={`url(#${id}-glow)`} />
          <path d="M890 210 C840 191 845 150 865 111 C878 85 891 54 891 31 C899 64 925 107 931 141 C938 177 924 202 890 210Z" fill={`url(#${id}-fire)`} />
          <path d="M891 207 C874 193 875 169 883 146 C889 129 892 114 892 99 C902 131 912 157 909 178 C907 194 901 204 891 207Z" fill="#FFF9D9" />
        </g>
      </g>
    </svg>
  </span>
}
