import { Routes, Route } from 'react-router-dom'
import Layout from './components/layout/Layout'
import HomePage from './pages/HomePage'
import EventPage from './pages/EventPage'
import FightPage from './pages/FightPage'
import UpsetsPage from './pages/UpsetsPage'
import PerformancePage from './pages/PerformancePage'
import ParlayPage from './pages/ParlayPage'
import BetHistoryPage from './pages/BetHistoryPage'
import FighterPage from './pages/FighterPage'

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<HomePage />} />
        <Route path="/events/:id" element={<EventPage />} />
        <Route path="/fights/:id" element={<FightPage />} />
        <Route path="/upsets" element={<UpsetsPage />} />
        <Route path="/parlays" element={<ParlayPage />} />
        <Route path="/bets" element={<BetHistoryPage />} />
        <Route path="/fighters/:id" element={<FighterPage />} />
        <Route path="/performance" element={<PerformancePage />} />
      </Route>
    </Routes>
  )
}
