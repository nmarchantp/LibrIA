/** Original bell, paired with the themed envelope in the shared header. */
export default function NotificationBellIcon({ size = 21, ...props }) {
  return <svg width={size} height={size} viewBox="0 0 32 32" fill="none" className="notification-bell-icon" focusable="false" {...props}>
    <g className="notification-bell" stroke="var(--primary)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M14 7V5a2 2 0 0 1 4 0v2" fill="var(--secondary)" />
      <path d="M12.5 24a3.5 3.5 0 0 0 7 0" fill="var(--accent)" fillOpacity=".35" />
      <path className="notification-bell-body" d="M16 6a7 7 0 0 0-7 7v4.5c0 1.6-.7 2.9-2 4.2-.8.8-.3 2.3.9 2.3h16.2c1.2 0 1.7-1.5.9-2.3-1.3-1.3-2-2.6-2-4.2V13a7 7 0 0 0-7-7Z" fill="var(--secondary)" />
      <path d="M9 20.5h14l2 2.1c.5.6.1 1.4-.6 1.4H7.6c-.7 0-1.1-.8-.6-1.4Z" fill="var(--accent)" fillOpacity=".35" />
    </g>
  </svg>
}
