import { useState } from 'react'

// Mount on the first visit, then preserve panel state and pending edits.
// The URL remains the only source of selection, including browser history.
export default function ProfilePanels({ active, renderPanel }) {
  const [visited, setVisited] = useState([active])
  const panels = visited.includes(active) ? visited : [...visited, active]
  if (panels !== visited) setVisited(panels)
  return panels.map(value => <div key={value} data-profile-panel={value}
    className="profile-content reader-profile-content" hidden={value !== active} inert={value !== active}>
    {renderPanel(value, value === active)}
  </div>)
}
