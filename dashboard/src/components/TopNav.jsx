import { useEffect, useRef, useState } from 'react'
import { NavLink, useLocation } from 'react-router-dom'
import MaterialIcon from './MaterialIcon'

const TABS = [
  { to: '/activity', label: 'Activity', icon: 'analytics' },
  { to: '/security', label: 'Security', icon: 'shield' },
  { to: '/containers', label: 'Containers', icon: 'grid_view' },
  { to: '/settings', label: 'Settings', icon: 'settings' },
]

export default function TopNav() {
  const location = useLocation()
  const linkRefs = useRef({})
  const [indicator, setIndicator] = useState({ left: 0, width: 0 })

  useEffect(() => {
    const active = TABS.find((t) => location.pathname.startsWith(t.to))
    const el = active && linkRefs.current[active.to]
    if (el) {
      setIndicator({ left: el.offsetLeft, width: el.offsetWidth })
    }
  }, [location.pathname])

  return (
    <>
      <header className="fixed top-0 w-full z-50 bg-background/80 backdrop-blur-md border-b border-white/10">
        <div className="flex justify-between items-center h-16 px-gutter max-w-[1440px] mx-auto">
          <div className="flex items-center gap-8">
            <span className="font-headline-sm text-headline-sm font-bold tracking-tighter text-on-surface">
              SENTINEL
            </span>
            <nav className="hidden md:flex items-center gap-6 relative">
              {TABS.map((tab) => (
                <NavLink
                  key={tab.to}
                  ref={(el) => {
                    linkRefs.current[tab.to] = el
                  }}
                  to={tab.to}
                  className={({ isActive }) =>
                    `font-label-caps text-label-caps pb-1 transition-colors duration-200 ${
                      isActive ? 'text-primary font-bold' : 'text-on-surface-variant font-medium hover:text-on-surface'
                    }`
                  }
                >
                  {tab.label}
                </NavLink>
              ))}
              <span
                className="absolute bottom-0 h-[2px] bg-primary transition-all duration-200 ease-out"
                style={{ left: indicator.left, width: indicator.width }}
              />
            </nav>
          </div>
          <div className="flex items-center gap-4">
            <button className="p-2 rounded-full hover:bg-white/5 transition-all duration-200 active:scale-90">
              <MaterialIcon name="search" className="text-on-surface-variant" />
            </button>
            <button className="p-2 rounded-full hover:bg-white/5 transition-all duration-200 active:scale-90">
              <MaterialIcon name="account_circle" className="text-on-surface-variant" />
            </button>
          </div>
        </div>
      </header>

      <footer className="md:hidden glass-panel h-16 border-t border-white/10 fixed bottom-0 w-full flex justify-around items-center px-4 z-50">
        {TABS.map((tab) => (
          <NavLink
            key={tab.to}
            to={tab.to}
            className={({ isActive }) =>
              `flex flex-col items-center gap-1 ${isActive ? 'text-primary' : 'text-on-surface-variant'}`
            }
          >
            {({ isActive }) => (
              <>
                <MaterialIcon name={tab.icon} filled={isActive} />
                <span className="font-label-caps text-[9px]">{tab.label.toUpperCase()}</span>
              </>
            )}
          </NavLink>
        ))}
      </footer>
    </>
  )
}
