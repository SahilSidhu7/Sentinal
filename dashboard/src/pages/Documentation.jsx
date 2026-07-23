import { useMemo } from 'react'
import { marked } from 'marked'
import readmeSource from '../../../README.md?raw'
import MaterialIcon from '../components/MaterialIcon'

export default function Documentation() {
  const html = useMemo(() => marked.parse(readmeSource), [])

  return (
    <main className="pt-24 pb-20 px-gutter max-w-[1000px] mx-auto min-h-screen custom-scrollbar">
      <header className="mb-12 flex items-center gap-3">
        <MaterialIcon name="menu_book" className="text-primary text-[32px]" />
        <div>
          <h1 className="font-headline-md text-headline-md text-on-surface mb-1">Documentation</h1>
          <p className="text-on-surface-variant font-body-md text-body-sm">Rendered from the project's README.md</p>
        </div>
      </header>

      <section className="glass-panel p-6 md:p-10 rounded-xl">
        <div className="sentinel-markdown" dangerouslySetInnerHTML={{ __html: html }} />
      </section>
    </main>
  )
}
