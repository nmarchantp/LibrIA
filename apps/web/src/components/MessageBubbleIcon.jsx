import { Mail, MailOpen } from 'lucide-react'
import { useLocation } from 'react-router-dom'

export default function MessageBubbleIcon({ size=22, ...props }) {
  const {pathname}=useLocation()
  const Icon=pathname.startsWith('/messages') ? MailOpen : Mail
  return <Icon size={size} strokeWidth={1.75} className="message-bubble-icon message-envelope" focusable="false" {...props} />
}
