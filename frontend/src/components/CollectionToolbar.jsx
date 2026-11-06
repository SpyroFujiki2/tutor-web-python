import Icon from './Icon.jsx'

export default function CollectionToolbar({ query, onQueryChange, filters = [], onReset, active, placeholder = 'Bạn muốn tìm gì?', count, noun = 'kết quả' }) {
  return <div className="collection-tools"><form className="search-toolbar" role="search" onSubmit={(event) => event.preventDefault()}><label className="search-input"><Icon name="search" size={21} /><span className="sr-only">Tìm kiếm</span><input type="search" value={query} onChange={(event) => onQueryChange(event.target.value)} placeholder={placeholder} maxLength={200} /></label>
    <div className="filter-controls"><span className="filter-label"><Icon name="filter" size={18} /><span>Lọc theo</span></span>{filters.map((filter) => <label className="filter-select" key={filter.label}><span className="sr-only">{filter.label}</span><select aria-label={filter.label} value={filter.value} onChange={(event) => filter.onChange(event.target.value)}>{filter.options.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>)}</div>
  </form><div className="collection-summary"><p role="status" aria-live="polite">{count === null || count === undefined ? 'Đang tải nội dung…' : <><strong>{count}</strong> {noun}{query && <> cho “{query}”</>}</>}</p>{active && <button type="button" className="text-button" onClick={onReset}><Icon name="close" size={14} />Đặt lại bộ lọc</button>}</div></div>
}

