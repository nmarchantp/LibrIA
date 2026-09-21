import { CalendarDays, MapPin, Users } from 'lucide-react'

const events = [
  { day: '22', month: 'OCT', title: 'Feria del Libro de Santiago', place: 'Estación Mapocho', kind: 'Feria' },
  { day: '05', month: 'NOV', title: 'Mundos distantes', place: 'Contrapunto', kind: 'Club de lectura' },
  { day: '18', month: 'NOV', title: 'Taller de escritura', place: 'Biblioteca de Santiago', kind: 'Taller' },
]

export default function EventsPage() {
  return <section className="page-width page community-page">
    <span className="kicker">COMUNIDAD LITERARIA</span>
    <h1 className="page-title">Eventos que nos reúnen</h1>
    <p className="page-lead">Descubre ferias, clubes de lectura y encuentros cerca de ti.</p>
    <div className="community-grid">
      {events.map(event => <article className="community-card event-card" key={event.title}>
        <div className="event-date"><strong>{event.day}</strong><span>{event.month}</span></div>
        <div><span className="pill-label">{event.kind}</span><h2>{event.title}</h2><p><MapPin size={15} /> {event.place}</p><p><Users size={15} /> Comunidad LibrIA</p></div>
        <button className="button soft" type="button">Quiero asistir</button>
      </article>)}
    </div>
    <p className="demo-notice"><CalendarDays size={17} /> Eventos de demostración; próximamente se conectarán al backend.</p>
  </section>
}
