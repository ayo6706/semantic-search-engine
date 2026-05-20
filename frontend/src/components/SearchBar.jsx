import { useEffect, useRef, useState } from 'react';
import './SearchBar.css';

export default function SearchBar({ value, onChange, isLoading, resultCount }) {
  const inputRef = useRef(null);
  const [isFocused, setIsFocused] = useState(false);

  useEffect(() => {
    const handleKeyDown = (e) => {
      // If user presses '/' and we're not focusing an input/textarea
      if (e.key === '/' && document.activeElement !== inputRef.current && document.activeElement.tagName !== 'INPUT' && document.activeElement.tagName !== 'TEXTAREA') {
        e.preventDefault();
        inputRef.current?.focus();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  const handleKeyDown = (e) => {
    if (e.key === 'Escape') {
      onChange({ target: { value: '' } });
      inputRef.current?.blur();
    }
  };

  return (
    <div className={`search-bar-container ${isFocused ? 'focused' : ''}`}>
      <div className="search-icon-wrapper">
        {isLoading ? (
          <div className="spinner"></div>
        ) : (
          <svg className="search-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="11" cy="11" r="8"></circle>
            <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
          </svg>
        )}
      </div>
      
      <input
        ref={inputRef}
        type="text"
        className="search-input"
        placeholder="Search documents… (e.g., payment schedule)"
        value={value}
        onChange={onChange}
        onFocus={() => setIsFocused(true)}
        onBlur={() => setIsFocused(false)}
        onKeyDown={handleKeyDown}
        spellCheck={false}
        autoFocus
        aria-label="Search documents"
      />

      <div className="search-bar-right">
        {resultCount !== undefined && resultCount !== null && (
          <span className="result-hint">{resultCount} results</span>
        )}
        <kbd className={`shortcut-hint ${isFocused ? 'hidden' : ''}`}>/</kbd>
      </div>
    </div>
  );
}
