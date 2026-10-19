"""Расчёт персонализированного индекса комфорта."""


def calculate_comfort_index(scores: dict, weights: dict) -> float:
    """Рассчитывает взвешенную оценку района по шкале 0–100."""
    if not scores:
        raise ValueError("Не переданы оценки критериев.")

    if scores.keys() != weights.keys():
        raise ValueError("Оценки и веса должны содержать одинаковые критерии.")

    if any(not 0 <= score <= 100 for score in scores.values()):
        raise ValueError("Оценки должны находиться в диапазоне 0–100.")

    if any(weight < 0 for weight in weights.values()):
        raise ValueError("Веса не могут быть отрицательными.")

    total_weight = sum(weights.values())

    if total_weight <= 0:
        raise ValueError("Сумма весов должна быть больше нуля.")

    return sum(
        scores[key] * weights[key]
        for key in scores
    ) / total_weight
