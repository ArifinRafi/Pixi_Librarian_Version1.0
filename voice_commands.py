# Voice control for Manual Mode.
#
# Pressing the VOICE COMMAND button records one phrase and we try to turn it
# into a movement.  This is deliberately a plain keyword table and not
# anything clever - it has to work in a noisy library hall, so the vocabulary
# is small and the words are far apart from each other.

import config

# Each entry is (list of phrases, action, argument)
DRIVE_COMMANDS = [
    (['go forward', 'move forward', 'forward', 'go ahead', 'go straight'],
     'drive', (1, 1)),
    (['go back', 'move back', 'backward', 'reverse', 'back up'],
     'drive', (-1, -1)),
    (['turn left', 'go left', 'left'], 'turn', (-1, 1)),
    (['turn right', 'go right', 'right'], 'turn', (1, -1)),
    (['stop', 'halt', 'stop moving', 'freeze'], 'stop', None),
]

ARM_COMMANDS = [
    (['raise left arm', 'lift left arm', 'left arm up'],
     'joint', (config.ARM_LEFT, config.JOINT_SHOULDER, 60)),
    (['lower left arm', 'left arm down', 'drop left arm'],
     'joint', (config.ARM_LEFT, config.JOINT_SHOULDER, 0)),
    (['raise right arm', 'lift right arm', 'right arm up'],
     'joint', (config.ARM_RIGHT, config.JOINT_SHOULDER, 60)),
    (['lower right arm', 'right arm down', 'drop right arm'],
     'joint', (config.ARM_RIGHT, config.JOINT_SHOULDER, 0)),
    (['bend left elbow', 'fold left arm', 'left elbow'],
     'joint', (config.ARM_LEFT, config.JOINT_MID, -90)),
    (['bend right elbow', 'fold right arm', 'right elbow'],
     'joint', (config.ARM_RIGHT, config.JOINT_MID, -90)),
    (['straighten left arm', 'left arm straight'],
     'joint', (config.ARM_LEFT, config.JOINT_MID, 0)),
    (['straighten right arm', 'right arm straight'],
     'joint', (config.ARM_RIGHT, config.JOINT_MID, 0)),
    (['wave', 'say hello', 'wave hand', 'greet'], 'wave', None),
    (['home', 'reset arms', 'arms home', 'stand by'], 'home', None),
]

# How long a "go forward" runs before the base stops itself, in seconds
DRIVE_BURST = 1.5
TURN_BURST = 0.8


def parse(phrase):
    """Turn a spoken phrase into (action, argument, description).

    Returns (None, None, reason) when nothing matched.
    """
    if not phrase:
        return None, None, "I did not hear a command."

    text = phrase.lower().strip()

    # Arms first - "raise left arm" also contains the word "left"
    for phrases, action, argument in ARM_COMMANDS:
        for candidate in phrases:
            if candidate in text:
                return action, argument, candidate

    for phrases, action, argument in DRIVE_COMMANDS:
        for candidate in phrases:
            if candidate in text:
                return action, argument, candidate

    return None, None, 'I do not know how to "%s".' % phrase
