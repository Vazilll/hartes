def calculate_discount(price: int, discount: int) -> int:
    """
    Calculate discounted price.
    :requires: price >= 0
    :requires: discount >= 0
    :ensures: result > 0
    """
    return price - discount
