import { useEffect, useRef } from 'react'
import { Terminal } from '@xterm/xterm'
import { FitAddon } from '@xterm/addon-fit'
import '@xterm/xterm/css/xterm.css'

// Encodes a resize as the APC control frame the in-container ptybroker
// intercepts (a real keyboard never emits this), so we can piggyback resize on
// the same byte pipe as keystrokes.
const resizeFrame = (cols, rows) => `\x1b_RESIZE:${cols}:${rows}\x1b\\`

// One xterm pane bridged to a project-environment PTY over a websocket. `onData`
// (optional) mirrors every output chunk to the caller — the workspace uses it on
// the server pane so what you see is exactly what the monitor scores.
export default function TerminalPane({ url, onOutput }) {
  const hostRef = useRef(null)

  useEffect(() => {
    const term = new Terminal({
      convertEol: false,
      fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace',
      fontSize: 13,
      theme: { background: '#0a0a0f', foreground: '#e6e6ea' },
    })
    const fit = new FitAddon()
    term.loadAddon(fit)
    term.open(hostRef.current)

    const ws = new WebSocket(url)
    ws.binaryType = 'arraybuffer'

    const sendResize = () => {
      if (ws.readyState === WebSocket.OPEN) ws.send(resizeFrame(term.cols, term.rows))
    }

    const safeFit = () => {
      // Only fit once the host box has a real size — fitting a 0-height box on
      // first paint is what let the terminal overflow onto the alerts below.
      const el = hostRef.current
      if (!el || el.clientHeight < 20 || el.clientWidth < 20) return
      try {
        fit.fit()
        sendResize()
      } catch {
        /* xterm not ready */
      }
    }
    // Fit after layout settles, and again whenever the box resizes.
    requestAnimationFrame(safeFit)
    const ro = new ResizeObserver(safeFit)
    ro.observe(hostRef.current)

    ws.onopen = () => {
      term.focus()
      safeFit()
    }
    ws.onmessage = (ev) => {
      const bytes = new Uint8Array(ev.data)
      term.write(bytes)
      if (onOutput) onOutput(bytes)
    }
    ws.onclose = () => term.write('\r\n\x1b[2m[disconnected]\x1b[0m\r\n')

    const dataSub = term.onData((d) => {
      if (ws.readyState === WebSocket.OPEN) ws.send(d)
    })

    window.addEventListener('resize', safeFit)

    return () => {
      window.removeEventListener('resize', safeFit)
      ro.disconnect()
      dataSub.dispose()
      ws.close()
      term.dispose()
    }
  }, [url, onOutput])

  return <div ref={hostRef} className="h-full w-full overflow-hidden rounded-lg bg-[#0a0a0f] p-2" />
}
