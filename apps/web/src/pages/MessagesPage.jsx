import { MessageCircle, Search } from 'lucide-react'

const conversations = [
  { initials: 'CF', name: 'Club Fantasía', text: '¿Qué les pareció el último capítulo?', time: '10:42', unread: 2 },
  { initials: 'MA', name: 'María Aguilera', text: 'Gracias por la recomendación ✨', time: 'Ayer' },
  { initials: 'LC', name: 'Lectores de ciencia ficción', text: 'La próxima reunión será el viernes.', time: 'Lun' },
]

export default function MessagesPage() {
  return <section className="page-width page community-page">
    <span className="kicker">CONVERSACIONES</span><h1 className="page-title">Mensajes</h1>
    <label className="search-box compact-search"><Search size={19} /><input placeholder="Buscar conversaciones" /></label>
    <div className="conversation-list">
      {conversations.map(item => <article className="conversation" key={item.name}>
        <span className="person-avatar message-avatar">{item.initials}</span>
        <div><h2>{item.name}</h2><p>{item.text}</p></div><time>{item.time}</time>
        {item.unread && <span className="unread-count">{item.unread}</span>}
      </article>)}
    </div>
    <p className="demo-notice"><MessageCircle size={17} /> Conversaciones de demostración; el envío de mensajes aún no está habilitado.</p>
  </section>
}
