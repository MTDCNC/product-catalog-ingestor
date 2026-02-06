# ETG Product Catalog Service

This service fetches, normalises, and returns the complete ETG machine product catalog.

It handles:
- Pagination of ETG `filter-machines.php`
- Brand extraction
- Product de-duplication
- Stable hashing for upsert workflows
- Detection support for retired products (via absence in latest run)

## Endpoint

### GET /etg/products

Returns the full list of currently published ETG machine products.

#### Example response
```json
{
  "total": 310,
  "products": [
    {
      "source": "etg",
      "brand": "Chiron",
      "brand_slug": "chiron",
      "product_name": "08 Series",
      "product_url": "https://engtechgroup.com/machine/08-series/",
      "image_url": "https://etg.glowt.co.uk/...",
      "is_new": false,
      "hash": "a9d709",
      "first_seen": "2026-02-05",
      "last_seen": "2026-02-05"
    }
  ]
}
