from sklearn.metrics import precision_recall_fscore_support


def calculate_metrics(
    predictions,
    ground_truth,
    hallucination_events,
):
    precision, recall, f1, _ = (
        precision_recall_fscore_support(
            ground_truth,
            predictions,
            average="macro",
        )
    )

    assert (
        f1 >= 0.87
    ), (
        f"Regression detected. "
        f"F1 score {f1} below threshold 0.87"
    )

    assert (
        sum(hallucination_events) == 0
    ), (
        "Hallucinations detected in evaluation set"
    )

    return {
        "precision": precision,
        "recall": recall,
        "f1": f1,
    }