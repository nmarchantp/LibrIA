import { Bell } from 'lucide-react'

export default function NotificationBellIcon({ size=22, ...props }) {
  return <Bell size={size} strokeWidth={1.75} className="notification-bell-icon notification-bell" focusable="false" {...props} />
}
