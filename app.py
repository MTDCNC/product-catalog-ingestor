import time
import hashlib
from datetime import datetime
from flask import Flask, jsonify, request
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

app = Flask(__name__)

ETG_ENDPOINT = "https://engtechgroup.com/wp-content/themes/ETG/machines/filter-machines.php"

def slugify(text: str) -> str:
    t = (text or "").strip().lower().replace("&", "and")
    out, last_dash = [], False
    for ch in t:
        if ch.isalnum():
            out.append(ch); last_dash = False
        else:
            if not last_dash:
                out.append("-"); last_dash = True
    s = "".join(out).strip("-")
    return s or "unknown"

def make_hash(url: str) -> str:
    return hashlib.md5(url.encode("utf-8")).hexdigest()[:6]

def build_session() -> requests.Session:
    s = requests.Session()
    retries = Retry(
        total=4,
        backoff_factor=0.6,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
        raise_on_status=False
    )
    adapter = HTTPAdapter(max_retries=retries, pool_connections=10, pool_maxsize=10)
    s.mount("https://", adapter)
    s.headers.update({"User-Agent": "MTDCNC product-catalog-ingestor/1.0"})
    return s

@app.route("/etg/products", methods=["GET"])
def etg_products():
    max_seconds = int(request.args.get("max_seconds", "55"))
    per_request_timeout = float(request.args.get("timeout", "18"))
    passes = int(request.args.get("passes", "2"))  # try 2 passes to recover unstable paging

    t0 = time.time()
    today = datetime.utcnow().strftime("%Y-%m-%d")
    session = build_session()

    # --- Fetch page 1 to get count/per_page ---
    errors = []
    try:
        r1 = session.get(ETG_ENDPOINT, params={"page": 1, "feature[type]": "all"}, timeout=per_request_timeout)
        data1 = r1.json()
    except Exception as e:
        return jsonify({"error": "Failed to fetch/parse ETG page 1", "details": str(e)}), 502

    etg_reported_count = int((data1.get("details") or {}).get("count") or 0)
    per_page = int((data1.get("details") or {}).get("products_per_page") or 15)
    expected_pages = max(1, (etg_reported_count + per_page - 1) // per_page)

    seen_urls = set()
    products = []

    def ingest_products(page_data):
        added = 0
        for p in (page_data.get("products") or []):
            url = p.get("url")
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)
            brand = (p.get("manufacturer") or "").strip() or "Unknown"
            products.append({
                "source": "etg",
                "brand": brand,
                "brand_slug": slugify(brand),
                "product_name": (p.get("name") or "").strip(),
                "product_url": url,
                "image_url": p.get("image"),
                "is_new": bool(p.get("new")),
                "hash": make_hash(url),
                "first_seen": today,
                "last_seen": today
            })
            added += 1
        return added

    # ingest page 1
    ingest_products(data1)

    # --- Passes over all pages to reduce “missing uniques” due to unstable ordering ---
    pages_fetched = 1
    for pass_no in range(1, passes + 1):
        for page in range(2, expected_pages + 1):
            if time.time() - t0 > max_seconds:
                errors.append({"page": page, "error": "max_seconds exceeded"})
                break

            try:
                r = session.get(
                    ETG_ENDPOINT,
                    params={"page": page, "feature[type]": "all"},
                    timeout=per_request_timeout
                )
                page_data = r.json()
                pages_fetched += 1
                ingest_products(page_data)
            except Exception as e:
                errors.append({"page": page, "error": str(e)})
                continue

        # if we reached ETG’s reported unique count, stop
        if etg_reported_count and len(seen_urls) >= etg_reported_count:
            break

    return jsonify({
        "total": len(products),
        "unique_urls": len(seen_urls),
        "etg_reported_count": etg_reported_count,
        "per_page": per_page,
        "expected_pages": expected_pages,
        "pages_fetched": pages_fetched,
        "duration_seconds": round(time.time() - t0, 2),
        "errors": errors[:20],  # cap output size
        "products": products
    })
