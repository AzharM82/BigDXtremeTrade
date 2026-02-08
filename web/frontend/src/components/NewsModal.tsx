import { useEffect } from 'react'
import { StockResult } from '../types'

interface NewsModalProps {
  stock: StockResult | null
  onClose: () => void
}

function NewsModal({ stock, onClose }: NewsModalProps) {
  useEffect(() => {
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', handleEsc)
    return () => document.removeEventListener('keydown', handleEsc)
  }, [onClose])

  if (!stock) return null

  const changeColor = stock.change_pct_today >= 0 ? '#16a34a' : '#dc2626'
  const changeSign = stock.change_pct_today >= 0 ? '+' : ''

  // Use news_items if available, fall back to single headline
  const articles = stock.news_items?.length
    ? stock.news_items
    : stock.news_headline
      ? [{ headline: stock.news_headline, link: stock.news_link }]
      : []

  return (
    <div className="news-modal-overlay" onClick={onClose}>
      <div className="news-modal-card" onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className="news-modal-header">
          <div className="flex items-center gap-3">
            <span className="news-modal-ticker">{stock.ticker}</span>
            <span className="news-modal-price" style={{ color: changeColor }}>
              ${stock.last_price.toFixed(2)}
              <span className="ml-2 text-sm">
                {changeSign}{stock.change_pct_today.toFixed(2)}%
              </span>
            </span>
          </div>
          <button className="news-modal-close" onClick={onClose}>&times;</button>
        </div>

        {/* Company */}
        <div className="news-modal-company">{stock.company}</div>

        {/* News Articles */}
        <div className="news-modal-body">
          {articles.length > 0 ? (
            <div className="news-articles-list">
              {articles.map((article, i) => (
                <div key={i} className="news-article-item">
                  <span className="news-article-number">{i + 1}</span>
                  <div className="news-article-content">
                    <p className="news-article-headline">{article.headline}</p>
                    {article.link && (
                      <a
                        href={article.link}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="news-article-link"
                      >
                        Read article &rarr;
                      </a>
                    )}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="news-modal-empty">No recent news available for this stock.</p>
          )}
        </div>

        {/* Quick Stats Footer */}
        <div className="news-modal-footer">
          <div className="news-modal-stat">
            <span className="news-modal-stat-label">5D Change</span>
            <span className="news-modal-stat-value" style={{ color: stock.change_pct_5d >= 0 ? '#16a34a' : '#dc2626' }}>
              {stock.change_pct_5d >= 0 ? '+' : ''}{stock.change_pct_5d.toFixed(2)}%
            </span>
          </div>
          <div className="news-modal-stat">
            <span className="news-modal-stat-label">1M Change</span>
            <span className="news-modal-stat-value" style={{ color: stock.change_pct_1m >= 0 ? '#16a34a' : '#dc2626' }}>
              {stock.change_pct_1m >= 0 ? '+' : ''}{stock.change_pct_1m.toFixed(2)}%
            </span>
          </div>
          <div className="news-modal-stat">
            <span className="news-modal-stat-label">RVOL</span>
            <span className="news-modal-stat-value">{stock.rvol.toFixed(1)}x</span>
          </div>
          <div className="news-modal-stat">
            <span className="news-modal-stat-label">Short Ratio</span>
            <span className="news-modal-stat-value">{stock.short_ratio ? stock.short_ratio.toFixed(1) : '-'}</span>
          </div>
          <div className="news-modal-stat">
            <span className="news-modal-stat-label">Float</span>
            <span className="news-modal-stat-value">{stock.float_shares || '-'}</span>
          </div>
        </div>
      </div>
    </div>
  )
}

export default NewsModal
