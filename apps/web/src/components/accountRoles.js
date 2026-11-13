import { BookHeart, BookOpen, Crown, Feather, Sparkles, Store } from 'lucide-react'

export const roleLabels = { lector: 'Lector', influencer: 'Influencer', autor: 'Autor', libreria: 'Librería', editorial: 'Editorial', admin: 'Administrador' }

// Describes only what the backend allows each role to do; keep in sync with the publication rules.
const readerPerk = ['Lectura', 'Funciones de lector', 'Conservas tu biblioteca, reseñas, notas y análisis lector.']
export const roleDetails = {
  lector: { icon: BookHeart, nav: 'Solicitar Influencer', summary: 'Registra tus lecturas y comparte reseñas, notas y teorías.', perks: [
    ['Lectura', 'Biblioteca personal', 'Registra tu avance, calificaciones y reseñas de cada libro.'],
    ['Comunidad', 'Notas y teorías', 'Comenta en el mural los libros que estás leyendo.'],
    ['Crecimiento', 'Perfil Influencer', 'Si creas contenido literario, puedes solicitar este perfil.'],
  ] },
  influencer: { icon: Sparkles, nav: 'Publicaciones y eventos', summary: 'Creas contenido literario para tu comunidad.', perks: [
    ['Comunidad', 'Publicaciones', 'Comparte anuncios, promociones y lanzamientos en el mural.'],
    ['Agenda', 'Eventos', 'Crea eventos y revisa cuántas personas están interesadas.'],
    readerPerk,
  ] },
  autor: { icon: Feather, nav: 'Publicaciones y eventos', summary: 'Compartes tu obra con la comunidad lectora.', perks: [
    ['Comunidad', 'Novedades de tu obra', 'Publica anuncios y lanzamientos de tus libros.'],
    ['Agenda', 'Encuentros', 'Crea eventos para conversar con tus lectores.'],
    readerPerk,
  ] },
  libreria: { icon: Store, nav: 'Publicaciones y eventos', summary: 'Representas una librería dentro de LibrIA.', perks: [
    ['Comunidad', 'Promociones', 'Comparte ofertas y novedades de tu catálogo.'],
    ['Agenda', 'Actividades', 'Crea eventos como presentaciones o clubes de lectura.'],
    readerPerk,
  ] },
  editorial: { icon: BookOpen, nav: 'Publicaciones y eventos', summary: 'Representas una editorial dentro de LibrIA.', perks: [
    ['Comunidad', 'Lanzamientos', 'Anuncia nuevos títulos y promociones editoriales.'],
    ['Agenda', 'Eventos', 'Crea presentaciones y encuentros con la comunidad.'],
    readerPerk,
  ] },
  admin: { icon: Crown, nav: 'Administración', summary: 'Acceso completo a la gestión comunitaria.', perks: [
    ['Comunidad', 'Publicación oficial', 'Crea anuncios y eventos para toda la comunidad.'],
    ['Curaduría', 'Moderación activa', 'Revisa reportes, reseñas y publicaciones marcadas.'],
    ['Usuarios', 'Gestión de roles', 'Asigna perfiles de autor, editorial, librería e influencer.'],
  ] },
}
