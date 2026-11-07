import Icon from './Icon.jsx'

export default function PageHeading({ eyebrow, title, description, icon = 'book', children }) {
  return <div className="section-heading page-heading"><div className="page-heading-copy"><p className="eyebrow">{eyebrow}</p><h1>{title}</h1>{description && <p className="section-description">{description}</p>}</div>{children ?? <span className="section-icon"><Icon name={icon} size={28} /></span>}</div>
}
