/** Original envelope drawing; no external image assets. */
export default function MessageBubbleIcon({ size = 21, ...props }) {
  return <svg width={size} height={size} viewBox="0 0 32 32" fill="none" className="message-bubble-icon" focusable="false" {...props}>
    <g className="message-envelope message-envelope--closed" stroke="var(--primary)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <rect x="4" y="8" width="24" height="17" rx="2.2" fill="var(--secondary)" />
      <path d="m4.8 23.8 9.1-7h4.2l9.1 7" fill="var(--accent)" fillOpacity=".35" />
      <path d="M6.2 8h19.6A2.2 2.2 0 0 1 28 10.2v.3l-10.7 8a2.2 2.2 0 0 1-2.6 0L4 10.5v-.3A2.2 2.2 0 0 1 6.2 8Z" fill="var(--secondary)" />
    </g>
    <g className="message-envelope message-envelope--open" stroke="var(--primary)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M4 12 14.6 3.7a2.2 2.2 0 0 1 2.8 0L28 12v11a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2Z" fill="var(--secondary)" />
      <path d="m4 12 12 8 12-8v11a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2Z" fill="var(--secondary)" />
      <path d="m4.8 24 9.8-7a2.4 2.4 0 0 1 2.8 0l9.8 7" fill="var(--accent)" fillOpacity=".35" />
    </g>
  </svg>
}
