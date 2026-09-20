"""Best-effort, read-only extraction of products visible in a Jev browser session."""

from __future__ import annotations

from typing import Any

# The script works only on the current document and returns JSON values through CDP. It never clicks,
# scrolls, changes DOM state, or sends data to the site.
PRODUCTS_SCRIPT = r"""
(() => {
  const isVisible = e => !!e && e.checkVisibility({checkOpacity:true, checkVisibilityCSS:true});
  const clean = value => (value || '').replace(/\s+/g, ' ').trim();
  const price = /(?:[¥￥$€£]\s?\d[\d,.]*|\d[\d,.]*\s?(?:元|USD|CNY|EUR|GBP))/i;
  const rating = /(?:\b[0-5](?:\.\d)?\s*(?:\/\s*5|out of 5|星)|评分\s*[0-5](?:\.\d)?)/i;
  const priceFilter = /^(?:under|over)\s*[$€£¥￥]?\s*\d|^[$€£¥￥]?\s*\d[\d,.]*\s*(?:to|-|–)\s*[$€£¥￥]?\s*\d/i;
  const visited = new Set();
  const products = [];
  for (const link of document.querySelectorAll('a[href]')) {
    if (!isVisible(link) || visited.has(link)) continue;
    const name = clean(link.getAttribute('aria-label') || link.innerText || link.textContent);
    if (name.length < 2) continue;
    let card = link;
    for (let depth = 0; depth < 7 && card.parentElement; depth += 1) {
      const candidate = card.parentElement;
      const text = clean(candidate.innerText);
      if (text.length <= 1800 && price.test(text)) { card = candidate; break; }
      card = candidate;
    }
    const text = clean(card.innerText);
    if (!price.test(text) || text.length < 40 || text.length > 1800 || priceFilter.test(name)) continue;
    if (/^shop on ebay$/i.test(name)) continue;
    visited.add(link);
    const priceMatch = text.match(price);
    const ratingMatch = text.match(rating);
    const heading = card.querySelector('h1,h2,h3,h4,[role="heading"]');
    products.push({
      name: clean(heading?.innerText) || name.slice(0, 300),
      price: priceMatch ? priceMatch[0] : null,
      rating: ratingMatch ? ratingMatch[0] : null,
      details: text.slice(0, 1200),
      url: link.href,
    });
    if (products.length >= 30) break;
  }
  const unique = [];
  const keys = new Set();
  for (const item of products) {
    const key = `${item.name}|${item.url}`;
    if (!keys.has(key)) { keys.add(key); unique.push(item); }
  }
  return { products: unique, extraction_note: "Best-effort extraction from visible product cards only." };
})()
"""


def extract_visible_products(browser: Any) -> dict[str, Any]:
    """Extract decision-ready product fields from the current page without changing it."""
    result = browser.evaluate(PRODUCTS_SCRIPT)
    if not isinstance(result, dict):
        return {"products": [], "extraction_note": "The page changed during extraction; try again."}
    products = result.get("products")
    return {
        "products": products if isinstance(products, list) else [],
        "extraction_note": str(result.get("extraction_note", "Best-effort extraction.")),
    }
