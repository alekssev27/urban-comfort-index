CRITERIA = {
    "transport": "Транспорт",
    "education": "Образование",
    "medical": "Медицина",
    "green": "Зелёные зоны",
    "daily": "Повседневная инфраструктура",
    "leisure": "Досуг",
}


def calculate_index(row, weights):
    """Calculate a weighted comfort score from 0 to 100."""
    total_weight = sum(weights.values())

    if total_weight == 0:
        return 0.0

    return sum(row[key] * weights[key] for key in CRITERIA) / total_weight
