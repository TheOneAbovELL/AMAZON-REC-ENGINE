"""Explainability helpers leveraging large language models."""


def explain_recommendation(query, product, user_profile=None):
    """Generate a human-readable recommendation explanation."""
    title = product.get("title", "Product")
    description = product.get("description", "")
    rating = product.get("rating", None)
    price = product.get("price", None)
    reasons = []
    if product.get("budget_score", 0.0) > 0.0:
        reasons.append("It falls within your budget.")
    if rating and rating >= 4.0:
        reasons.append("The product has high customer ratings.")
    if product.get("popularity", 0) >= 100:
        reasons.append("It has strong user confidence from many reviews.")
    if "gpu" in description.lower() or "rtx" in description.lower():
        reasons.append("The laptop has a strong GPU suitable for AI and gaming workloads.")
    if user_profile:
        reasons.append(f"It also matches preferences for {user_profile} users.")
    if not reasons:
        reasons.append("It is semantically relevant to your query.")

    explanation = (
        f"Recommended product: {title}.\n"
        f"Query: {query}.\n"
        f"Details: {description}.\n"
        f"Price: {price}.\n"
        + "\n".join(reasons)
    )
    return explanation
