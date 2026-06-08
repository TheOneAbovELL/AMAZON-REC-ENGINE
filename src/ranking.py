"""Ranking utilities for personalized product recommendations."""

TRUSTED_BRANDS = {"lenovo", "asus", "dell", "hp", "logitech", "sony", "jbl"}


def compute_business_score(product, category_score=0.0):
    score = 0.0
    in_stock = product.get("in_stock")
    if isinstance(in_stock, bool) and in_stock:
        score += 0.4
    elif isinstance(in_stock, str) and in_stock.lower() in {"yes", "true", "available", "in stock", "instock"}:
        score += 0.4

    rating = float(product.get("rating", 0.0) or 0.0)
    if rating >= 4.3:
        score += 0.3

    popularity = float(product.get("popularity", 0.0) or 0.0)
    if popularity >= 500:
        score += 0.2

    title = str(product.get("title", "")).lower()
    brand = str(product.get("brand", "")).lower()
    text = f"{brand} {title}"
    if any(brand_name in text for brand_name in TRUSTED_BRANDS):
        score += 0.1

    score += 0.1 * float(category_score or 0.0)
    return min(score, 1.0)


def compute_score(similarity, rating, popularity, budget_score=0.0, business_score=0.0):
    """Compute a final ranking score with business-aware normalization."""
    normalized_rating = min(max(float(rating or 0.0) / 5.0, 0.0), 1.0)
    normalized_popularity = min(max(float(popularity or 0.0) / 1500.0, 0.0), 1.0)
    return (
        0.35 * float(similarity or 0.0)
        + 0.25 * normalized_rating
        + 0.15 * normalized_popularity
        + 0.10 * float(budget_score or 0.0)
        + 0.05 * float(business_score or 0.0)
    )


def rank_products(products):
    """Rank products by computed score and business quality signals."""
    max_popularity = max((float(product.get("popularity", 0.0) or 0.0) for product in products), default=1.0)
    for product in products:
        popularity = float(product.get("popularity", 0.0) or 0.0)
        product["popularity_norm"] = popularity / max_popularity if max_popularity else 0.0
        business_score = compute_business_score(product, category_score=product.get("category_score", 0.0))
        product["business_score"] = business_score
        product["score"] = compute_score(
            product.get("similarity", 0.0),
            product.get("rating", 0.0),
            popularity,
            product.get("budget_score", 0.0),
            business_score,
        )
    return sorted(products, key=lambda x: x["score"], reverse=True)
