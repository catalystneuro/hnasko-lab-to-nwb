"""Train durations of the stimulation protocols."""

import math

TRAIN_DURATION_IN_S_TO_LABEL = {0.25: "250ms", 1.0: "1s", 4.0: "4s", 16.0: "16s"}
TRAIN_DURATION_LABEL_TO_S = {label: duration for duration, label in TRAIN_DURATION_IN_S_TO_LABEL.items()}


def count_pulses(train_duration_label: str, stimulus_frequency: float) -> int:
    """Count the pulses of a train of the protocol: the whole pulse periods that fit in the train duration.

    TDT records only the onset and offset of each train, so the count comes from the protocol duration, not from
    the recorded one, which can be a fraction of a millisecond shorter (e.g. 0.2497 s x 40 Hz would give 9 pulses
    instead of 10). A train of 250 ms at 5 Hz has 1 pulse, as the preprint counts it ("as little as a single
    pulse"), and one of 250 ms at 10 Hz has 2.

    Parameters
    ----------
    train_duration_label : str
        The protocol duration of the train, as given by label_train_duration (e.g. "250ms").
    stimulus_frequency : float
        The pulse frequency of the train, in Hz.

    Returns
    -------
    int
        The number of pulses in the train.
    """
    periods = TRAIN_DURATION_LABEL_TO_S[train_duration_label] * stimulus_frequency
    return math.floor(round(periods, 9))


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
