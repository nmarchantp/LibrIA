import { Clock, CloudRain, Flame, Ghost, Heart, Search, Smile, Sparkles, Swords, Zap } from 'lucide-react'

const icons = { heart: Heart, flame: Flame, ghost: Ghost, swords: Swords, 'cloud-rain': CloudRain, smile: Smile, search: Search, zap: Zap, sparkles: Sparkles, clock: Clock }

export default function TasteIcon({ name, ...props }) {
  const Icon = icons[name] || Sparkles
  return <Icon {...props} />
}
