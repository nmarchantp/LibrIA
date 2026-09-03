import { Navigate, Route, Routes } from 'react-router-dom'
import Layout from './components/Layout'
import BookDetailPage from './pages/BookDetailPage'
import BooksPage from './pages/BooksPage'
import HomePage from './pages/HomePage'
import InsightsPage from './pages/InsightsPage'
import LibraryPage from './pages/LibraryPage'
import LoginPage from './pages/LoginPage'
import ProfilePage from './pages/ProfilePage'
import ReadingPage from './pages/ReadingPage'
import RegisterPage from './pages/RegisterPage'

// App contiene solamente el mapa de URLs del frontend.
export default function App() {
  return <Routes>
    <Route path="/login" element={<LoginPage />} />
    <Route path="/register" element={<RegisterPage />} />
    <Route element={<Layout />}>
      <Route index element={<HomePage />} />
      <Route path="/profile" element={<ProfilePage />} />
      <Route path="/books" element={<BooksPage />} />
      <Route path="/books/:id" element={<BookDetailPage />} />
      <Route path="/library" element={<LibraryPage />} />
      <Route path="/reading/:id" element={<ReadingPage />} />
      <Route path="/insights" element={<InsightsPage />} />
    </Route>
    <Route path="*" element={<Navigate to="/" replace />} />
  </Routes>
}
