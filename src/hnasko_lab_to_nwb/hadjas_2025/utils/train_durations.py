"""Train durations of the stimulation protocols."""

TRAIN_DURATION_IN_S_TO_LABEL = {0.25: "250ms", 1.0: "1s", 4.0: "4s", 16.0: "16s"}


def label_train_duration(duration: float) -> str | None:
    """Label a train duration in seconds (e.g. 0.26 gives "250ms"); None if it is not one of the protocol's."""
    train_duration = min(TRAIN_DURATION_IN_S_TO_LABEL, key=lambda protocol_duration: abs(protocol_duration - duration))
    if abs(train_duration - duration) > 0.1 * train_duration:
        return None
    return TRAIN_DURATION_IN_S_TO_LABEL[train_duration]
