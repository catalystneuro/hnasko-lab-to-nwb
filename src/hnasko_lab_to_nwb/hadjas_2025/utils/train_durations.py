"""Train durations of the stimulation protocols."""

TRAIN_DURATION_IN_S_TO_LABEL = {0.25: "250ms", 1.0: "1s", 4.0: "4s", 16.0: "16s"}


def label_train_duration(duration: float) -> str | None:
    """Label a train duration with the closest duration of the protocols (e.g. 0.26 gives "250ms").

    Parameters
    ----------
    duration : float
        The duration of a stimulation train, in seconds (offset minus onset).

    Returns
    -------
    str or None
        The label of the closest protocol duration, or None if the duration differs from it by more than 10%.
    """
    train_duration = min(TRAIN_DURATION_IN_S_TO_LABEL, key=lambda protocol_duration: abs(protocol_duration - duration))
    if abs(train_duration - duration) > 0.1 * train_duration:
        return None
    return TRAIN_DURATION_IN_S_TO_LABEL[train_duration]
