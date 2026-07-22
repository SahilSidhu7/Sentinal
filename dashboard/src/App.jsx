import { Outlet } from 'react-router-dom'
import TopNav from './components/TopNav'

export default function App() {
  return (
    <div className="bg-background text-on-surface font-body-md min-h-screen">
      <TopNav />
      <Outlet />
    </div>
  )
}
