"""Explainability helpers for recommendation results."""


def explain_recommendation(query, product, user_profile=None):
    """
    Generate a business-friendly explanation describing
    why the recommendation engine selected this product.
    """

    title = product.get(
        "title",
        product.get(
            "name",
            "Unknown Product"
        ),
    )

    description = product.get(
        "description",
        product.get(
            "reviewText",
            "",
        ),
    )

    rating = float(product.get("rating", 0))
    price = product.get("price", "N/A")

    similarity = product.get("similarity", None)

    reasons = []

    # Semantic Retrieval
    if similarity is not None and similarity > 0.40:
        reasons.append(
            "Retrieved through semantic similarity search using Sentence Transformers and FAISS."
        )

    # Rating Signal
    if rating >= 4.5:
        reasons.append(
            f"Ranks among the highest-rated products in the candidate pool ({rating}/5 rating)."
        )
    elif rating >= 4.0:
        reasons.append(
            f"Shows strong customer satisfaction with a rating of {rating}/5."
        )

    # Budget Signal
    if product.get("budget_score", 0) > 0:
        reasons.append(
            "Matches the budget constraints detected from the user query."
        )

    # Popularity Signal
    if product.get("popularity", 0) >= 500:
        reasons.append(
            "Frequently reviewed and trusted by a large number of customers."
        )

    # AI / Gaming Signals
    text = f"{title} {description}".lower()

    if any(word in text for word in ["rtx", "gpu", "deep learning", "machine learning"]):
        reasons.append(
            "Contains hardware features suitable for AI, machine learning, and compute-intensive workloads."
        )

    if "gaming" in text:
        reasons.append(
            "Includes gaming-oriented specifications that typically correlate with strong performance hardware."
        )

    # Personalization
    if user_profile:
        reasons.append(
            f"Received an additional personalization boost for the '{user_profile}' profile."
        )

    # Fallback
    if not reasons:
        reasons.append(
            "Ranked highly after semantic retrieval and business-aware ranking."
        )

    explanation = (
        f"Why this product was recommended:\n\n"
        + "\n".join([f"• {reason}" for reason in reasons])
    )

    return explanation