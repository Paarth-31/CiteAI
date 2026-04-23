"use client"

import React, { useState, useEffect } from 'react';
import { AuthProvider } from '@/components/contexts/AuthContext';
import Navbar from '@/components/Navbar';
import PrivacyBanner from '@/components/PrivacyBanner';
import AuthModal from '@/components/AuthModal';
import { Search, Loader2, FileText, ExternalLink, ChevronLeft, ChevronRight, Filter, Download, X, Calendar, Building2, FileCode, Tag, Users, Scale, Database } from 'lucide-react';
import { useDebounce } from '@/hooks/useDebounce';

interface SearchResult {
  tid: number;
  title: string;
  headline?: string;
  docsource?: string;
  publishdate?: string;
  author?: string;
  numcites?: number;
  numcitedby?: number;
  citation?: string;
  docsize?: number;
}

interface CategoryItem {
  value: string;
  formInput: string;
  selected?: boolean;
}

interface Category {
  name: string;
  items: CategoryItem[];
}

export default function SearchPage() {
  const [searchQuery, setSearchQuery] = useState('');
  const [results, setResults] = useState<SearchResult[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [foundText, setFoundText] = useState<string>('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [currentPage, setCurrentPage] = useState(0);
  const [hasSearched, setHasSearched] = useState(false);
  const [showFilters, setShowFilters] = useState(false);
  const [selectedDocument, setSelectedDocument] = useState<SearchResult | null>(null);
  const [documentDetails, setDocumentDetails] = useState<any>(null);
  const [loadingDetails, setLoadingDetails] = useState(false);
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  
  const debouncedSearchQuery = useDebounce(searchQuery, 500);

  useEffect(() => {
    if (debouncedSearchQuery.trim().length >= 3) {
      performSearch(debouncedSearchQuery, currentPage);
    } else if (debouncedSearchQuery.trim().length === 0) {
      setResults([]);
      setCategories([]);
      setFoundText('');
      setHasSearched(false);
      setError(null);
    }
  }, [debouncedSearchQuery, currentPage]);

  const performSearch = async (query: string, page: number) => {
    try {
      setLoading(true);
      setError(null);
      setHasSearched(true);

      const response = await fetch('/api/indian-kanoon/search', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          formInput: query,
          pagenum: page,
        }),
      });

      if (!response.ok) {
        throw new Error('Failed to fetch search results');
      }

      const data = await response.json();
      
      // Parse categories
      if (data.categories && Array.isArray(data.categories)) {
        const parsedCategories: Category[] = data.categories.map((cat: any) => ({
          name: cat[0],
          items: cat[1] || [],
        }));
        setCategories(parsedCategories);
      }

      // Set results
      if (data.docs && Array.isArray(data.docs)) {
        setResults(data.docs);
      } else {
        setResults([]);
      }

      // Set found text
      if (data.found) {
        setFoundText(data.found);
      }
    } catch (err) {
      console.error('Search error:', err);
      setError('Failed to search. Please try again.');
      setResults([]);
      setCategories([]);
    } finally {
      setLoading(false);
    }
  };

  const handleCategoryClick = (categoryName: string, item: CategoryItem) => {
    setSearchQuery(item.value);
    setCurrentPage(0);
    performSearch(item.formInput, 0);
  };

  const handlePageChange = (newPage: number) => {
    if (newPage >= 0) {
      setCurrentPage(newPage);
      window.scrollTo({ top: 0, behavior: 'smooth' });
    }
  };

  const handleDocumentClick = async (result: SearchResult) => {
    setSelectedDocument(result);
    setLoadingDetails(true);
    
    try {
      const response = await fetch(`/api/indian-kanoon/document/${result.tid}`);
      if (response.ok) {
        const data = await response.json();
        setDocumentDetails(data);
      }
    } catch (err) {
      console.error('Error fetching document details:', err);
    } finally {
      setLoadingDetails(false);
    }
  };

  const handleDownloadDocument = (docId: number, format: 'pdf' | 'txt') => {
    if (format === 'pdf') {
      window.open(`https://indiankanoon.org/origdoc/${docId}/`, '_blank', 'noopener,noreferrer');
    } else {
      window.open(`https://indiankanoon.org/doc/${docId}/`, '_blank', 'noopener,noreferrer');
    }
  };

  const stripHtmlTags = (html: string) => {
    return html?.replace(/<[^>]*>/g, '').replace(/&nbsp;/g, ' ').trim() || '';
  };

  const getCategoryIcon = (categoryName: string) => {
    if (categoryName.includes('AI Tags')) return <Tag size={16} className="text-[#29b6f6]" />;
    if (categoryName.includes('Court') || categoryName.includes('Law')) return <Building2 size={16} className="text-[#a78bfa]" />;
    if (categoryName.includes('Author') || categoryName.includes('Bench')) return <Users size={16} className="text-[#fb923c]" />;
    if (categoryName.includes('Year')) return <Calendar size={16} className="text-[#34d399]" />;
    if (categoryName.includes('Document')) return <FileText size={16} className="text-[#29b6f6]" />;
    return <Scale size={16} className="text-[#81d4fa]" />;
  };

  return (
    <AuthProvider>
      <div className="min-h-screen bg-[#0f1117] relative overflow-x-hidden">
        <Navbar />
        <PrivacyBanner />
        <AuthModal />

        {/* Ambient glow blobs */}
        <div className="hero-blob w-[600px] h-[600px] bg-[#29b6f6] opacity-[0.03] top-[-200px] left-[-150px]" />
        <div className="hero-blob w-[400px] h-[400px] bg-[#1a6fa3] opacity-[0.05] top-[100px] right-[-100px]" />

        <div className="relative z-10 w-full px-4 sm:px-6 md:px-10 py-10">
          <div className="max-w-7xl mx-auto">
            {/* ── Search Header Card ── */}
            <div className="glass-card rounded-3xl p-6 sm:p-10 mb-8 border border-[#242c3a] shadow-soft animate-fade-up">
              <div className="flex items-center gap-4 mb-6">
                <div className="w-12 h-12 bg-[#1a6fa3]/20 border border-[#1a6fa3]/40 rounded-xl flex items-center justify-center shadow-[0_0_20px_rgba(41,182,246,0.1)]">
                  <Database size={24} className="text-[#29b6f6]" />
                </div>
                <div>
                  <h1 className="text-2xl sm:text-3xl font-bold text-[#f0f4f8] font-[var(--font-heading)] tracking-tight mb-1">
                    Global Search
                  </h1>
                  <p className="text-[#6b7a8d] text-sm font-[var(--font-sans)]">
                    Search through the comprehensive universal database for cases, judgments, and documents.
                  </p>
                </div>
              </div>

              {/* Search Input with Filter Button */}
              <div className="flex flex-col sm:flex-row gap-4">
                <div className="relative flex-1">
                  <div className="absolute inset-y-0 left-0 pl-5 flex items-center pointer-events-none">
                    <Search className="text-[#6b7a8d]" size={20} />
                  </div>
                  <input
                    type="text"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    placeholder="Enter your search query (minimum 3 characters)..."
                    className="w-full bg-[#0b0e15] border border-[#242c3a] text-[#f0f4f8] placeholder-[#6b7a8d] rounded-2xl pl-12 pr-4 py-4 focus:outline-none focus:ring-1 focus:ring-[#29b6f6] focus:border-[#29b6f6] font-[var(--font-sans)] text-base transition-all shadow-inner"
                  />
                </div>
                <button
                  onClick={() => setShowFilters(!showFilters)}
                  className={`px-6 py-4 rounded-2xl transition-colors flex items-center justify-center gap-2 font-[var(--font-heading)] font-bold text-sm tracking-wide shadow-soft border ${
                    showFilters 
                      ? 'bg-[rgba(41,182,246,0.1)] border-[rgba(41,182,246,0.3)] text-[#29b6f6] shadow-[0_0_15px_rgba(41,182,246,0.15)]' 
                      : 'bg-[#161b25] border-[#242c3a] text-[#f0f4f8] hover:bg-[#1e2433]'
                  }`}
                >
                  <Filter size={18} className={showFilters ? "text-[#29b6f6]" : "text-[#6b7a8d]"} />
                  <span className="hidden sm:inline">Filters</span>
                </button>
              </div>

              {/* Search Info */}
              <div className="mt-5 flex items-center justify-between text-[#6b7a8d] text-xs font-[var(--font-mono)] tracking-widest uppercase">
                <span>
                  {loading ? (
                    <span className="flex items-center gap-2 text-[#29b6f6]">
                      <span className="w-2 h-2 rounded-full bg-[#29b6f6] animate-ping" />
                      Querying database...
                    </span>
                  ) : foundText ? (
                    <span className="text-[#c9d1dc]">{stripHtmlTags(foundText)}</span>
                  ) : hasSearched ? (
                    <span className="text-[#c9d1dc]">{results.length} RESULT{results.length !== 1 ? 'S' : ''} FOUND</span>
                  ) : (
                    'READY TO SEARCH'
                  )}
                </span>
                {searchQuery.length > 0 && searchQuery.length < 3 && (
                  <span className="text-[#f43f5e]">Min 3 characters required</span>
                )}
              </div>
            </div>

            {/* 2-Column Layout: Categories Sidebar + Results */}
            <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
              {/* Categories Sidebar */}
              {showFilters && categories.length > 0 && (
                <div className="lg:col-span-1 space-y-4 animate-fade-up">
                  {categories.map((category, idx) => (
                    <div key={idx} className="glass-card rounded-2xl p-5 border border-[#242c3a] shadow-soft">
                      <h3 className="text-sm font-bold text-[#f0f4f8] mb-4 flex items-center gap-2.5 font-[var(--font-heading)] border-b border-[#242c3a] pb-3">
                        <div className="bg-[#1e2433] p-1.5 rounded-lg border border-[#242c3a]">
                          {getCategoryIcon(category.name)}
                        </div>
                        {category.name}
                      </h3>
                      <div className="space-y-1.5">
                        {category.items.slice(0, 10).map((item, itemIdx) => (
                          <button
                            key={itemIdx}
                            onClick={() => handleCategoryClick(category.name, item)}
                            className={`w-full text-left px-3 py-2.5 rounded-xl text-xs transition-all font-[var(--font-sans)] ${
                              item.selected
                                ? 'bg-[rgba(41,182,246,0.1)] border border-[rgba(41,182,246,0.3)] text-[#29b6f6] font-bold shadow-[0_0_10px_rgba(41,182,246,0.1)]'
                                : 'bg-transparent border border-transparent text-[#c9d1dc] hover:bg-[#1e2433] hover:border-[#242c3a]'
                            }`}
                          >
                            {stripHtmlTags(item.value)}
                          </button>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {/* Results Column */}
              <div className={showFilters && categories.length > 0 ? 'lg:col-span-3' : 'lg:col-span-4'}>
                {/* Loading State */}
                {loading && (
                  <div className="flex flex-col items-center justify-center py-20">
                    <div className="w-14 h-14 border-4 border-[#242c3a] border-t-[#29b6f6] rounded-full animate-spin mb-5 shadow-[0_0_15px_rgba(41,182,246,0.2)]" />
                    <h3 className="text-lg font-bold text-[#f0f4f8] font-[var(--font-heading)] tracking-wide mb-2">Scanning Index</h3>
                  </div>
                )}

                {/* Error State */}
                {error && !loading && (
                  <div className="glass-card rounded-2xl p-6 text-center border border-[#f43f5e]/30 bg-[#f43f5e]/5">
                    <p className="text-[#f43f5e] font-medium font-[var(--font-sans)]">{error}</p>
                  </div>
                )}

                {/* No Results */}
                {!loading && !error && hasSearched && results.length === 0 && (
                  <div className="glass-card rounded-3xl p-12 text-center border border-[#242c3a]">
                    <Search className="mx-auto text-[#242c3a] mb-5" size={56} />
                    <h3 className="text-xl font-bold text-[#f0f4f8] mb-2 font-[var(--font-heading)] tracking-wide">No matches found</h3>
                    <p className="text-[#6b7a8d] text-sm font-[var(--font-sans)]">Try adjusting your search query or relaxing active filters.</p>
                  </div>
                )}

                {/* Results List */}
                {!loading && results.length > 0 && (
                  <div className="animate-fade-up animate-fade-up-delay-1">
                    <div className="space-y-4 mb-8">
                      {results.map((result, index) => (
                        <div
                          key={result.tid || index}
                          className="glass-card rounded-2xl p-6 border border-[#242c3a] hover:border-[#1a6fa3] transition-all group shadow-soft relative overflow-hidden"
                        >
                          {/* Subtle hover accent line */}
                          <div className="absolute top-0 left-0 w-1 h-full bg-[#29b6f6] opacity-0 group-hover:opacity-100 transition-opacity"></div>

                          <div className="flex items-start justify-between gap-4 mb-4">
                            <h3 
                              className="text-lg font-bold text-[#f0f4f8] group-hover:text-[#29b6f6] transition-colors flex-1 line-clamp-2 cursor-pointer font-[var(--font-heading)] leading-snug"
                              onClick={() => handleDocumentClick(result)}
                            >
                              {stripHtmlTags(result.title || 'Untitled Document')}
                            </h3>
                            <div className="flex items-center gap-2 flex-shrink-0 text-[#6b7a8d]">
                              <button
                                onClick={() => handleDocumentClick(result)}
                                className="p-2 hover:bg-[#1e2433] hover:text-[#f0f4f8] rounded-lg transition-colors border border-transparent hover:border-[#242c3a]"
                                title="View Details"
                              >
                                <FileCode size={18} />
                              </button>
                              <button
                                onClick={() => handleDownloadDocument(result.tid, 'pdf')}
                                className="p-2 hover:bg-[#1e2433] hover:text-[#f0f4f8] rounded-lg transition-colors border border-transparent hover:border-[#242c3a]"
                                title="Download PDF"
                              >
                                <Download size={18} />
                              </button>
                              <button
                                onClick={() => window.open(`https://indiankanoon.org/doc/${result.tid}/`, '_blank', 'noopener,noreferrer')}
                                className="p-2 hover:bg-[#1e2433] hover:text-[#29b6f6] rounded-lg transition-colors border border-transparent hover:border-[#242c3a]"
                                title="Open in Indian Kanoon"
                              >
                                <ExternalLink size={18} />
                              </button>
                            </div>
                          </div>

                          {result.citation && (
                            <p className="text-xs text-[#29b6f6] mb-3 font-bold font-[var(--font-mono)] tracking-wider">
                              {result.citation}
                            </p>
                          )}

                          {result.headline && (
                            <div 
                              className="text-sm text-[#c9d1dc] line-clamp-3 mb-5 font-[var(--font-sans)] leading-relaxed bg-[#0b0e15] p-4 rounded-xl border border-[#242c3a]"
                              dangerouslySetInnerHTML={{ __html: result.headline }}
                            />
                          )}

                          <div className="flex flex-wrap items-center gap-2.5">
                            {result.docsource && (
                              <span className="bg-[#1e2433] border border-[#242c3a] text-[#81d4fa] text-[11px] px-3 py-1.5 rounded-lg font-[var(--font-mono)] tracking-wide font-bold">
                                {result.docsource}
                              </span>
                            )}
                            {result.publishdate && (
                              <span className="bg-[#1e2433] border border-[#242c3a] text-[#e8edf2] text-[11px] px-3 py-1.5 rounded-lg font-[var(--font-mono)] tracking-wide font-bold">
                                {result.publishdate}
                              </span>
                            )}
                            {result.author && (
                              <span className="bg-[#1e2433] border border-[#242c3a] text-[#a78bfa] text-[11px] px-3 py-1.5 rounded-lg font-[var(--font-mono)] tracking-wide font-bold">
                                {result.author}
                              </span>
                            )}
                            {result.numcites !== undefined && (
                              <span className={`text-[11px] px-3 py-1.5 rounded-lg font-[var(--font-mono)] tracking-wide font-bold border ${
                                result.numcites > 0 
                                  ? 'bg-[rgba(41,182,246,0.1)] border-[rgba(41,182,246,0.3)] text-[#29b6f6]' 
                                  : 'bg-[#161b25] border-[#242c3a] text-[#6b7a8d]'
                              }`}>
                                {result.numcites} citations
                              </span>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>

                    {/* Pagination */}
                    <div className="glass-card rounded-2xl p-4 flex items-center justify-between border border-[#242c3a]">
                      <button
                        onClick={() => handlePageChange(currentPage - 1)}
                        disabled={currentPage === 0}
                        className="flex items-center gap-2 px-5 py-2.5 text-xs font-bold text-[#f0f4f8] bg-[#161b25] border border-[#242c3a] rounded-xl hover:bg-[#1e2433] disabled:opacity-50 disabled:cursor-not-allowed transition-all font-[var(--font-mono)] uppercase tracking-wider"
                      >
                        <ChevronLeft size={16} />
                        Prev
                      </button>

                      <span className="text-xs text-[#29b6f6] font-bold font-[var(--font-mono)] tracking-widest uppercase bg-[rgba(41,182,246,0.1)] border border-[rgba(41,182,246,0.2)] px-4 py-1.5 rounded-lg">
                        Page {currentPage + 1}
                      </span>

                      <button
                        onClick={() => handlePageChange(currentPage + 1)}
                        disabled={results.length < 10}
                        className="flex items-center gap-2 px-5 py-2.5 text-xs font-bold text-[#f0f4f8] bg-[#161b25] border border-[#242c3a] rounded-xl hover:bg-[#1e2433] disabled:opacity-50 disabled:cursor-not-allowed transition-all font-[var(--font-mono)] uppercase tracking-wider"
                      >
                        Next
                        <ChevronRight size={16} />
                      </button>
                    </div>
                  </div>
                )}

                {/* Initial State */}
                {!hasSearched && !loading && (
                  <div className="glass-card rounded-3xl p-12 text-center border border-[#242c3a] animate-fade-up">
                    <div className="w-20 h-20 bg-[#161b25] border border-[#242c3a] rounded-2xl flex items-center justify-center mx-auto mb-6 shadow-inner">
                      <Search className="text-[#6b7a8d]" size={32} />
                    </div>
                    <h3 className="text-2xl font-bold text-[#f0f4f8] mb-3 font-[var(--font-heading)] tracking-tight">
                      Initiate Global Search
                    </h3>
                    <p className="text-[#6b7a8d] text-sm max-w-md mx-auto mb-8 font-[var(--font-sans)] leading-relaxed">
                      Query the universal database index. Access high-fidelity metadata, extract raw OCR documents, and download sources instantly.
                    </p>
                    <div className="flex flex-wrap justify-center gap-4 text-xs font-bold text-[#c9d1dc] font-[var(--font-mono)] tracking-wider uppercase">
                      <div className="flex items-center gap-2 bg-[#0b0e15] border border-[#242c3a] px-3 py-1.5 rounded-lg">
                        <Building2 size={14} className="text-[#a78bfa]" />
                        <span>Filter by Entity</span>
                      </div>
                      <div className="flex items-center gap-2 bg-[#0b0e15] border border-[#242c3a] px-3 py-1.5 rounded-lg">
                        <Calendar size={14} className="text-[#34d399]" />
                        <span>Time Scoped</span>
                      </div>
                      <div className="flex items-center gap-2 bg-[#0b0e15] border border-[#242c3a] px-3 py-1.5 rounded-lg">
                        <Download size={14} className="text-[#29b6f6]" />
                        <span>Export Ready</span>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* ── Document Details Modal ── */}
        {selectedDocument && (
          <div className="fixed inset-0 bg-[#050a0e]/80 backdrop-blur-md z-50 flex items-center justify-center p-4">
            <div className="bg-[#0b0e15] rounded-3xl max-w-5xl w-full max-h-[90vh] overflow-hidden shadow-[0_8px_32px_rgba(0,0,0,0.8)] border border-[#242c3a] flex flex-col animate-fade-up">
              
              {/* Modal Header */}
              <div className="bg-[#161b25] border-b border-[#242c3a] p-6 sm:px-8 flex items-start justify-between shrink-0">
                <div className="flex-1 pr-4">
                  <h2 className="text-xl sm:text-2xl font-bold text-[#f0f4f8] mb-2 font-[var(--font-heading)] leading-snug">
                    {stripHtmlTags(selectedDocument.title)}
                  </h2>
                  {selectedDocument.citation && (
                    <p className="text-[11px] font-bold text-[#29b6f6] font-[var(--font-mono)] tracking-widest uppercase">{selectedDocument.citation}</p>
                  )}
                </div>
                <button
                  onClick={() => {
                    setSelectedDocument(null);
                    setDocumentDetails(null);
                  }}
                  className="p-2 text-[#6b7a8d] hover:text-[#f43f5e] hover:bg-[#f43f5e]/10 rounded-xl transition-colors border border-transparent hover:border-[#f43f5e]/30"
                >
                  <X size={24} />
                </button>
              </div>

              {/* Modal Body */}
              <div className="p-6 sm:px-8 overflow-y-auto flex-1 scrollbar-thin bg-[#0b0e15]">
                {loadingDetails ? (
                  <div className="flex flex-col items-center justify-center py-20">
                    <div className="w-12 h-12 border-4 border-[#242c3a] border-t-[#29b6f6] rounded-full animate-spin mb-4" />
                    <p className="text-[#29b6f6] text-xs font-bold font-[var(--font-mono)] tracking-widest uppercase">Fetching Document Body...</p>
                  </div>
                ) : documentDetails ? (
                  <div className="space-y-8">
                    {/* Metadata Badges */}
                    <div className="flex flex-wrap gap-2.5">
                      {selectedDocument.docsource && (
                        <span className="bg-[#1e2433] border border-[#242c3a] text-[#81d4fa] px-3 py-1.5 rounded-lg text-xs font-bold font-[var(--font-mono)] tracking-wider">
                          {selectedDocument.docsource}
                        </span>
                      )}
                      {selectedDocument.publishdate && (
                        <span className="bg-[#1e2433] border border-[#242c3a] text-[#e8edf2] px-3 py-1.5 rounded-lg text-xs font-bold font-[var(--font-mono)] tracking-wider">
                          {selectedDocument.publishdate}
                        </span>
                      )}
                    </div>

                    {/* Raw Document Content */}
                    <div className="prose prose-sm max-w-none text-[#c9d1dc] font-[var(--font-sans)] leading-relaxed prose-headings:text-[#f0f4f8] prose-headings:font-[var(--font-heading)] prose-a:text-[#29b6f6] prose-strong:text-[#f0f4f8]">
                      {documentDetails.doc && (
                        <div dangerouslySetInnerHTML={{ __html: documentDetails.doc }} />
                      )}
                    </div>
                  </div>
                ) : (
                  <div className="text-center py-20">
                    <FileText className="mx-auto text-[#242c3a] mb-4" size={48} />
                    <p className="text-[#6b7a8d] font-[var(--font-sans)]">No raw document body available for this entry.</p>
                  </div>
                )}
              </div>

              {/* Modal Footer */}
              <div className="bg-[#161b25] border-t border-[#242c3a] p-6 sm:px-8 flex flex-col sm:flex-row gap-3 shrink-0">
                <button
                  onClick={() => handleDownloadDocument(selectedDocument.tid, 'pdf')}
                  className="flex-1 btn-primary py-3 justify-center"
                >
                  <Download size={18} />
                  Download PDF
                </button>
                <button
                  onClick={() => handleDownloadDocument(selectedDocument.tid, 'txt')}
                  className="flex-1 bg-[#0b0e15] hover:bg-[#1e2433] text-[#f0f4f8] font-bold px-4 py-3 rounded-xl transition-all border border-[#242c3a] flex items-center justify-center gap-2 text-sm font-[var(--font-heading)]"
                >
                  <FileText size={18} className="text-[#a78bfa]" />
                  Raw Text
                </button>
                <button
                  onClick={() => window.open(`https://indiankanoon.org/doc/${selectedDocument.tid}/`, '_blank', 'noopener,noreferrer')}
                  className="flex-1 bg-[#0b0e15] hover:bg-[#1e2433] text-[#f0f4f8] font-bold px-4 py-3 rounded-xl transition-all border border-[#242c3a] flex items-center justify-center gap-2 text-sm font-[var(--font-heading)]"
                >
                  <ExternalLink size={18} className="text-[#34d399]" />
                  Open Source
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </AuthProvider>
  );
}