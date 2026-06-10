"""Personalization components for user-specific recommendations."""

USER_PROFILES = {
    "gaming": ["gaming", "rtx", "graphics", "asus", "lenovo"],
    "student": ["affordable", "battery life", "lightweight", "portable"],
    "ai_student": ["machine learning", "gpu", "deep learning", "ram"],
}


def personalization_boost(text, user_type):
    """Compute a score boost when product text matches user preferences."""
    boost = 0.0
    preferences = USER_PROFILES.get(user_type, [])
    text_lower = text.lower()
    for pref in preferences:
        if pref in text_lower:
            boost += 0.05
    return min(boost, 0.10)


def personalize_recommendations(products, user_type):
    """Apply personalization boost to a list of recommended products."""
    personalized = []
    for product in products:
        combined_text = product.get("combined_text", "")
        boost = personalization_boost(combined_text, user_type)
        base_score = product.get("final_score", product.get("score", 0.0))
        product["personalized_score"] = float(base_score) + boost
        personalized.append(product)
    return sorted(personalized, key=lambda x: x["personalized_score"], reverse=True)
