// Canonical Pacto de Sangre flame: geometry, proportions, core, and local glow.
export default function CandleFlameShape({ fireId, glowId, className='sidebar-candle-flame-shape' }) {
  return <g className={className}>
    <ellipse cx="890" cy="135" rx="110" ry="145" fill={`url(#${glowId})`} />
    <path d="M890 210 C840 191 845 150 865 111 C878 85 891 54 891 31 C899 64 925 107 931 141 C938 177 924 202 890 210Z" fill={`url(#${fireId})`} />
    <path d="M891 207 C874 193 875 169 883 146 C889 129 892 114 892 99 C902 131 912 157 909 178 C907 194 901 204 891 207Z" fill="#FFF9D9" />
  </g>
}
