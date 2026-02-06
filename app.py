import requests
import hashlib
from datetime import datetime
from flask import Flask, jsonify

app = Flask(__name__)

ETG_ENDPOINT = "https://engtechgroup.com/wp-content/themes/ETG/machines/filter-machines.php"

def slugify(text):
    return (
        text.lower()
        .replace("&", "and")
        .replace(" ", "-")
    )

def make_hash(url):
    return hashlib.md5(url.encode()).hexdigest()[:6]

@app.route("/etg/products", methods=["GET"])
def get_etg_products():
    page = 1
    products = []
    seen_urls = set()
    today = datetime.utcnow().strftime("%Y-%m-%d")

    while True:
        r = requests.get(
            ETG_ENDPOINT,
            params={
                "page": page,
                "feature[type]": "all"
            },
            timeout=20
        )
        r.raise_for_status()
        data = r.json()

        for p in data.get("products", []):
            url = p.get("url")
            if not url or url in seen_urls:
                continue

            seen_urls.add(url)

            brand = (p.get("manufacturer") or "").strip()

            products.append({
                "source": "etg",
                "brand": brand,
                "brand_slug": slugify(brand),
                "product_name": p.get("name", "").strip(),
                "product_url": url,
                "image_url": p.get("image"),
                "is_new": bool(p.get("new")),
                "hash": make_hash(url),
                "first_seen": today,
                "last_seen": today
            })

        count = int(data["details"]["count"])
        per_page = int(data["details"]["products_per_page"])

        if page * per_page >= count:
            break

        page += 1

    return jsonify({
        "total": len(products),
        "products": products
    })
