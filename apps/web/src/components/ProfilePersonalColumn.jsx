import { BookHeart, Flower2, Quote, Target } from 'lucide-react'

export default function ProfilePersonalColumn({ biography }) {
  return <aside className="reader-personal-column" aria-label="Tu espacio personal">
    <section className="reader-personal-card reader-about"><h2><Flower2 size={19} aria-hidden="true" />Sobre mí</h2><p className={biography ? 'reader-biography' : 'reader-module-empty'}>{biography || 'Tu biografía aún no está disponible. Este espacio está reservado para tu historia como lector.'}</p></section>
    <section className="reader-personal-card"><h2><Target size={19} aria-hidden="true" />Mi reto de lectura</h2><div className="reader-empty-emblem" aria-hidden="true"><BookHeart size={32} strokeWidth={1.25} /></div><h3>Tu próxima aventura</h3><p className="reader-module-empty">Todavía no hay un reto configurado. Aquí podrás encontrar tu meta cuando esta función esté disponible.</p></section>
    <section className="reader-personal-card"><h2><BookHeart size={19} aria-hidden="true" />Mis géneros favoritos</h2><p className="reader-module-empty">Aún no has elegido géneros favoritos. Este espacio está preparado para tus preferencias, sin deducirlas de tu biblioteca.</p></section>
    <section className="reader-personal-card reader-favorite-quote"><h2><Quote size={19} aria-hidden="true" />Frase favorita</h2><div className="reader-quote-placeholder"><Quote size={26} strokeWidth={1.25} aria-hidden="true" /><p>Hay palabras que se quedan contigo.</p><small>Aún no hay una frase guardada. La selección personal estará disponible más adelante.</small></div></section>
  </aside>
}
