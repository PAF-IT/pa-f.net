import React, { useState, useRef, useEffect } from 'react'
import { Link, Plus } from 'lucide-react'
import Fuse from 'fuse.js'

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

interface LinkSearchWidgetProps {
  sitemap: Sitemap
  onLinkSelect: (link: string, insertAtCursor?: boolean) => void
  onCreatePage: (path: string) => void
  editorRef?: React.RefObject<any>
}

interface SearchResult {
  item: {
    path: string
    title: string
  }
  score?: number
}

const LinkSearchWidget: React.FC<LinkSearchWidgetProps> = ({
  sitemap,
  onLinkSelect,
  onCreatePage
}) => {
  const [isOpen, setIsOpen] = useState(false)
  const [searchTerm, setSearchTerm] = useState('')
  const [results, setResults] = useState<SearchResult[]>([])
  const dropdownRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  // Create Fuse instance for fuzzy search
  const fuse = new Fuse(
    Object.entries(sitemap).map(([path, page]) => ({
      path,
      title: page.title
    })),
    {
      keys: ['title', 'path'],
      threshold: 0.3,
      includeScore: true
    }
  )

  useEffect(() => {
    if (searchTerm.trim()) {
      const searchResults = fuse.search(searchTerm)
      setResults(searchResults)
    } else {
      // Show all pages when no search term
      setResults(
        Object.entries(sitemap)
          .slice(0, 10)
          .map(([path, page]) => ({
            item: { path, title: page.title }
          }))
      )
    }
  }, [searchTerm, sitemap])

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false)
      }
    }

    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside)
      return () => document.removeEventListener('mousedown', handleClickOutside)
    }
  }, [isOpen])

  const handleOpen = () => {
    setIsOpen(true)
    setSearchTerm('')
    setTimeout(() => {
      inputRef.current?.focus()
    }, 100)
  }

  const handleLinkSelect = (path: string) => {
    const link = path.replace('.html', '')
    onLinkSelect(`[${sitemap[path]?.title || path}](/${link})`)
    setIsOpen(false)
    setSearchTerm('')
  }

  const handleCreatePage = () => {
    if (searchTerm.trim()) {
      let newPath = searchTerm.trim().toLowerCase()
        .replace(/[^a-z0-9\s-]/g, '')
        .replace(/\s+/g, '-')
      
      if (!newPath.endsWith('.html')) {
        newPath += '.html'
      }
      
      onCreatePage(newPath)
      setIsOpen(false)
      setSearchTerm('')
    }
  }

  const shouldShowCreateOption = searchTerm.trim() && 
    !Object.keys(sitemap).some(path => 
      path.toLowerCase().includes(searchTerm.toLowerCase()) ||
      sitemap[path].title.toLowerCase().includes(searchTerm.toLowerCase())
    )

  return (
    <div className="link-search-widget" ref={dropdownRef}>
      <button
        className="link-search-button"
        onClick={handleOpen}
        title="Insert link to page"
      >
        <Link size={14} />
        Link
      </button>

      {isOpen && (
        <div className="link-search-dropdown">
          <input
            ref={inputRef}
            type="text"
            className="link-search-input"
            placeholder="Search pages to link..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Escape') {
                setIsOpen(false)
                setSearchTerm('')
              }
            }}
          />

          <div className="link-search-results">
            {results.length === 0 && !shouldShowCreateOption ? (
              <div className="link-search-no-results">
                No pages found
              </div>
            ) : (
              results.slice(0, 8).map(({ item }) => (
                <div
                  key={item.path}
                  className="link-search-result"
                  onClick={() => handleLinkSelect(item.path)}
                >
                  <div className="link-search-result-title">
                    {item.title}
                  </div>
                  <div className="link-search-result-path">
                    {item.path}
                  </div>
                </div>
              ))
            )}

            {shouldShowCreateOption && (
              <div
                className="link-search-create"
                onClick={handleCreatePage}
              >
                <Plus size={14} />
                Create page "{searchTerm}"
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

export default LinkSearchWidget
