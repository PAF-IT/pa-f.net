import React, { useState, useEffect, useMemo } from 'react'
import MDEditor from '@uiw/react-md-editor'
import { Search, Plus, Menu, X, Trash2 } from 'lucide-react'

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
  const [searchTerm, setSearchTerm] = useState('')
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [showAddPageDialog, setShowAddPageDialog] = useState(false)
  const [newPagePath, setNewPagePath] = useState('')

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

  const updatePage = (field: keyof PageData, value: string | string[]) => {
    if (!selectedPage) return
    
    setSitemap(prev => ({
      ...prev,
      [selectedPage]: {
        ...prev[selectedPage],
        [field]: value
      }
    }))
  }

  const addPage = () => {
    if (!newPagePath.trim()) return
    
    let path = newPagePath.trim()
    if (!path.endsWith('.html')) {
      path += '.html'
    }
    
    if (sitemap[path]) {
      alert('Page already exists!')
      return
    }
    
    const newPage: PageData = {
      title: path.replace('.html', '').replace(/[/_-]/g, ' '),
      md: '# New Page\n\nStart editing your content here...',
      date: new Date().toISOString().split('T')[0],
      image: '',
      links: []
    }
    
    setSitemap(prev => ({
      ...prev,
      [path]: newPage
    }))
    
    setSelectedPage(path)
    setNewPagePath('')
    setShowAddPageDialog(false)
  }

  const deletePage = (path: string, e: React.MouseEvent) => {
    e.stopPropagation()
    
    if (!confirm(`Are you sure you want to delete "${sitemap[path]?.title}"?`)) {
      return
    }
    
    setSitemap(prev => {
      const newSitemap = { ...prev }
      delete newSitemap[path]
      return newSitemap
    })
    
    if (selectedPage === path) {
      const remainingPages = Object.keys(sitemap).filter(p => p !== path)
      setSelectedPage(remainingPages[0] || '')
    }
  }

  // Filter pages based on search term
  const filteredPages = useMemo(() => {
    if (!searchTerm.trim()) {
      return Object.entries(sitemap)
    }
    
    const term = searchTerm.toLowerCase()
    return Object.entries(sitemap).filter(([path, page]) => 
      page.title.toLowerCase().includes(term) ||
      path.toLowerCase().includes(term) ||
      page.md.toLowerCase().includes(term)
    )
  }, [sitemap, searchTerm])

  const currentPage = selectedPage ? sitemap[selectedPage] : null

  const toggleSidebar = () => {
    setSidebarOpen(!sidebarOpen)
  }

  if (loading) {
    return <div className="loading">Loading sitemap...</div>
  }

  if (error && Object.keys(sitemap).length === 0) {
    return <div className="error">Error: {error}</div>
  }

  return (
    <div className="app">
      <button className="mobile-toggle" onClick={toggleSidebar}>
        {sidebarOpen ? <X size={20} /> : <Menu size={20} />}
      </button>

      <div className={`sidebar ${sidebarOpen ? 'open' : ''}`}>
        <div className="sidebar-header">
          <h2>
            Pages ({filteredPages.length})
            <span style={{ fontSize: '0.8rem', fontWeight: 'normal' }}>
              of {Object.keys(sitemap).length}
            </span>
          </h2>
          
          <div className="sidebar-controls">
            <input
              type="text"
              placeholder="Search pages..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="search-input"
            />
            <button
              className="add-page-button"
              onClick={() => setShowAddPageDialog(true)}
              title="Add new page"
            >
              <Plus size={16} />
              Add
            </button>
          </div>
        </div>

        <div className="page-list-container">
          {filteredPages.length === 0 ? (
            <div className="no-pages">
              {searchTerm ? 'No pages match your search' : 'No pages found'}
            </div>
          ) : (
            <ul className="page-list">
              {filteredPages.map(([path, page]) => (
                <li
                  key={path}
                  className={`page-item ${selectedPage === path ? 'active' : ''}`}
                  onClick={() => {
                    setSelectedPage(path)
                    setSidebarOpen(false)
                  }}
                  title={`${page.title} - ${path}`}
                >
                  <div className="page-item-title">{page.title}</div>
                  <div className="page-item-path">{path}</div>
                  {page.date && (
                    <div className="page-item-meta">
                      {page.date} • {page.md.length} chars
                    </div>
                  )}
                  <button
                    className="delete-page-button"
                    onClick={(e) => deletePage(path, e)}
                    title="Delete page"
                  >
                    <Trash2 size={12} />
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      <div className="main-content">
        <div className="editor-header">
          <h1>PAF Site Editor</h1>
          <div className="header-actions">
            <button
              className="save-button"
              onClick={saveSitemap}
              disabled={saving}
            >
              {saving ? 'Saving...' : 'Save & Regenerate Site'}
            </button>
          </div>
        </div>

        {error && <div className="error">Error: {error}</div>}

        {currentPage ? (
          <div className="editor-container">
            <div className="form-row">
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
                <label htmlFor="date">Date:</label>
                <input
                  id="date"
                  type="date"
                  value={currentPage.date || ''}
                  onChange={(e) => updatePage('date', e.target.value)}
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
            </div>

            <div className="markdown-editor-container">
              <label>Content (Markdown):</label>
              <MDEditor
                value={currentPage.md}
                onChange={(value) => updatePage('md', value || '')}
                preview="edit"
                hideToolbar={false}
                visibleDragBar={false}
                data-color-mode="light"
              />
            </div>
          </div>
        ) : (
          <div className="editor-container">
            <div style={{ textAlign: 'center', padding: '4rem 2rem', color: '#666' }}>
              <h2>No page selected</h2>
              <p>Select a page from the sidebar to start editing, or create a new page.</p>
              <button
                className="add-page-button"
                onClick={() => setShowAddPageDialog(true)}
                style={{ marginTop: '1rem', padding: '0.75rem 1.5rem' }}
              >
                <Plus size={16} />
                Create New Page
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Add Page Dialog */}
      {showAddPageDialog && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          backgroundColor: 'rgba(0, 0, 0, 0.5)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 1001
        }}>
          <div style={{
            backgroundColor: 'white',
            padding: '2rem',
            borderRadius: '8px',
            width: '90%',
            maxWidth: '500px',
            boxShadow: '0 4px 6px rgba(0, 0, 0, 0.1)'
          }}>
            <h3 style={{ margin: '0 0 1rem 0' }}>Add New Page</h3>
            <div className="form-group">
              <label htmlFor="newPagePath">Page Path:</label>
              <input
                id="newPagePath"
                type="text"
                value={newPagePath}
                onChange={(e) => setNewPagePath(e.target.value)}
                placeholder="e.g., new-page.html or folder/page.html"
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    addPage()
                  } else if (e.key === 'Escape') {
                    setShowAddPageDialog(false)
                    setNewPagePath('')
                  }
                }}
                autoFocus
              />
            </div>
            <div style={{ display: 'flex', gap: '0.5rem', justifyContent: 'flex-end', marginTop: '1.5rem' }}>
              <button
                onClick={() => {
                  setShowAddPageDialog(false)
                  setNewPagePath('')
                }}
                style={{
                  padding: '0.5rem 1rem',
                  border: '1px solid #ddd',
                  borderRadius: '4px',
                  backgroundColor: 'white',
                  cursor: 'pointer'
                }}
              >
                Cancel
              </button>
              <button
                onClick={addPage}
                disabled={!newPagePath.trim()}
                className="add-page-button"
                style={{ padding: '0.5rem 1rem' }}
              >
                Create Page
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default App
