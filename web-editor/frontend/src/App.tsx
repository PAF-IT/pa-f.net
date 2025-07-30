import React, { useState, useEffect } from 'react'
import CodeMirror from '@uiw/react-codemirror'
import { markdown } from '@codemirror/lang-markdown'

interface PageData {
  title: string
  md: string
  date?: string
  image?: string
  links: string[]
}

interface Sitemap {
  [key: string]: PageData
}

function App() {
  const [sitemap, setSitemap] = useState<Sitemap>({})
  const [selectedPage, setSelectedPage] = useState<string>('')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string>('')

  // Load sitemap on component mount
  useEffect(() => {
    loadSitemap()
  }, [])

  const loadSitemap = async () => {
    try {
      setLoading(true)
      const response = await fetch('/api/sitemap')
      if (!response.ok) {
        throw new Error('Failed to load sitemap')
      }
      const data = await response.json()
      setSitemap(data)
      
      // Select first page by default
      const firstPage = Object.keys(data)[0]
      if (firstPage) {
        setSelectedPage(firstPage)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load sitemap')
    } finally {
      setLoading(false)
    }
  }

  const saveSitemap = async () => {
    try {
      setSaving(true)
      setError('')
      
      const response = await fetch('/api/sitemap', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(sitemap),
      })
      
      if (!response.ok) {
        throw new Error('Failed to save sitemap')
      }
      
      alert('Site saved and regenerated successfully!')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save sitemap')
    } finally {
      setSaving(false)
    }
  }

  const updatePage = (field: keyof PageData, value: string) => {
    if (!selectedPage) return
    
    setSitemap(prev => ({
      ...prev,
      [selectedPage]: {
        ...prev[selectedPage],
        [field]: value
      }
    }))
  }

  const currentPage = selectedPage ? sitemap[selectedPage] : null

  if (loading) {
    return <div className="loading">Loading sitemap...</div>
  }

  if (error && Object.keys(sitemap).length === 0) {
    return <div className="error">Error: {error}</div>
  }

  return (
    <div className="app">
      <div className="sidebar">
        <h2>Pages ({Object.keys(sitemap).length})</h2>
        <ul className="page-list">
          {Object.entries(sitemap).map(([path, page]) => (
            <li
              key={path}
              className={`page-item ${selectedPage === path ? 'active' : ''}`}
              onClick={() => setSelectedPage(path)}
              title={page.title}
            >
              <div style={{ fontWeight: 'bold', marginBottom: '2px' }}>
                {page.title}
              </div>
              <div style={{ fontSize: '0.8rem', opacity: 0.7 }}>
                {path}
              </div>
            </li>
          ))}
        </ul>
      </div>

      <div className="main-content">
        <div className="editor-header">
          <h1>PAF Site Editor</h1>
          <button
            className="save-button"
            onClick={saveSitemap}
            disabled={saving}
          >
            {saving ? 'Saving...' : 'Save & Regenerate Site'}
          </button>
        </div>

        {error && <div className="error">Error: {error}</div>}

        {currentPage ? (
          <div className="editor-container">
            <div className="form-group">
              <label htmlFor="title">Title:</label>
              <input
                id="title"
                type="text"
                value={currentPage.title}
                onChange={(e) => updatePage('title', e.target.value)}
              />
            </div>

            <div className="form-group">
              <label htmlFor="date">Date (YYYY-MM-DD):</label>
              <input
                id="date"
                type="text"
                value={currentPage.date || ''}
                onChange={(e) => updatePage('date', e.target.value)}
                placeholder="2024-01-01"
              />
            </div>

            <div className="form-group">
              <label htmlFor="image">Image Path:</label>
              <input
                id="image"
                type="text"
                value={currentPage.image || ''}
                onChange={(e) => updatePage('image', e.target.value)}
                placeholder="sites/pa-f.net/files/image.jpg"
              />
            </div>

            <div className="form-group" style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
              <label htmlFor="content">Content (Markdown):</label>
              <CodeMirror
                value={currentPage.md}
                height="100%"
                extensions={[markdown()]}
                onChange={(value) => updatePage('md', value)}
                className="markdown-editor"
              />
            </div>
          </div>
        ) : (
          <div className="editor-container">
            <p>Select a page from the sidebar to edit</p>
          </div>
        )}
      </div>
    </div>
  )
}

export default App
