"""Ranking utilities for personalized product recommendations."""

TRUSTED_BRANDS = {
    "lenovo",
    "asus",
    "dell",
    "hp",
    "logitech",
    "sony",
    "jbl",
    "acer",
    "msi",
    "samsung",
    "lg",
}


def compute_business_score(product, category_score=0.0):

    score = 0.0

    # --------------------------
    # Rating Quality
    # --------------------------

    rating = float(
        product.get("rating", 0.0) or 0.0
    )

    if rating >= 4.5:
        score += 0.40

    elif rating >= 4.0:
        score += 0.25

    # --------------------------
    # Popularity
    # --------------------------

    popularity = float(
        product.get("popularity", 0.0) or 0.0
    )

    if popularity >= 10000:
        score += 0.30

    elif popularity >= 1000:
        score += 0.20

    elif popularity >= 100:
        score += 0.10

    # --------------------------
    # Trusted Brand
    # --------------------------

    product_name = str(
        product.get("name", "")
    ).lower()

    if any(
        brand in product_name
        for brand in TRUSTED_BRANDS
    ):
        score += 0.20

    # --------------------------
    # Category Match
    # --------------------------

    score += (
        0.10 *
        float(category_score or 0.0)
    )

    return min(score, 1.0)


def compute_score(
    similarity,
    rating,
    popularity,
    budget_score=0.0,
    business_score=0.0,
):

    rating_norm = min(
        max(float(rating or 0.0) / 5.0, 0.0),
        1.0,
    )

    popularity_norm = min(
        float(popularity or 0.0) / 10000.0,
        1.0,
    )

    return (
        0.45 * float(similarity or 0.0)
        + 0.20 * rating_norm
        + 0.15 * popularity_norm
        + 0.10 * float(budget_score or 0.0)
        + 0.10 * float(business_score or 0.0)
    )


def rank_products(products):

    ranked_products = []

    for product in products:

        business_score = compute_business_score(
            product,
            category_score=product.get(
                "category_score",
                0.0,
            ),
        )

        product["business_score"] = (
            business_score
        )

        final_score = compute_score(
            similarity=product.get(
                "similarity",
                0.0,
            ),
            rating=product.get(
                "rating",
                0.0,
            ),
            popularity=product.get(
                "popularity",
                0.0,
            ),
            budget_score=product.get(
                "budget_score",
                0.0,
            ),
            business_score=business_score,
        )

        product["score"] = float(final_score)
        product["final_score"] = float(final_score)

        ranked_products.append(product)

    ranked_products.sort(
        key=lambda x: x["final_score"],
        reverse=True,
    )

    return ranked_products