import { Navigate, Route, Routes } from 'react-router-dom'
import Layout from './components/Layout'
import BookDetailPage from './pages/BookDetailPage'
import BooksPage from './pages/BooksPage'
import HomePage from './pages/HomePage'
import LoginPage from './pages/LoginPage'
import ProfilePage from './pages/ProfilePage'
import ReadingPage from './pages/ReadingPage'
import RegisterPage from './pages/RegisterPage'
import SessionGate from './components/SessionGate'
import EventsPage from './pages/EventsPage'
import MessagesPage from './pages/MessagesPage'
import NotificationsPage from './pages/NotificationsPage'
import RecommendationsPage from './pages/RecommendationsPage'

// App contiene solamente el mapa de URLs del frontend.
export default function App() {
  return <Routes>
    <Route element={<SessionGate guest />}>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
    </Route>
    <Route element={<SessionGate />}>
    <Route element={<Layout />}>
      <Route index element={<HomePage />} />
      <Route path="/profile" element={<ProfilePage />} />
      <Route path="/books" element={<BooksPage />} />
      <Route path="/books/:id" element={<BookDetailPage />} />
      <Route path="/library" element={<Navigate to="/profile?tab=library" replace />} />
      <Route path="/reading/:id" element={<ReadingPage />} />
      <Route path="/insights" element={<Navigate to="/profile?tab=analysis" replace />} />
      <Route path="/events" element={<EventsPage />} />
      <Route path="/messages" element={<MessagesPage />} />
      <Route path="/notifications" element={<NotificationsPage />} />
      <Route path="/recommendations" element={<RecommendationsPage />} />
    </Route>
    </Route>
    <Route path="*" element={<Navigate to="/" replace />} />
  </Routes>
}
