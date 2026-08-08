# Configuration for Pixi - Autonomous Humanoid Librarian Robot
# Roboway Labs, Dhaka

import os
import sys

# ---------------------------------------------------------------------------
# Serial link to the Arduino (motor controller board)
# ---------------------------------------------------------------------------
# The Arduino Mega sits on the base of the robot and is connected to the
# Raspberry Pi over USB.  On the Pi it usually shows up as /dev/ttyACM0, on a
# Windows development machine it is a COM port.
if sys.platform.startswith('win'):
    SERIAL_PORT = 'COM3'
else:
    SERIAL_PORT = '/dev/ttyACM0'

# Allow overriding the port without editing this file (useful on the Pi)
SERIAL_PORT = os.environ.get('PIXI_SERIAL_PORT', SERIAL_PORT)

SERIAL_BAUD = 115200
SERIAL_TIMEOUT = 0.5

# The Arduino resets when the serial port is opened, so give it a moment
# before we start throwing commands at it.
SERIAL_BOOT_DELAY = 2.0

# ---------------------------------------------------------------------------
# Drive base - 4 DC gear motors, two per side (tank drive)
# ---------------------------------------------------------------------------
MAX_DRIVE_SPEED = 255       # what the Arduino analogWrite() can take
DEFAULT_DRIVE_SPEED = 160   # speed used by the voice commands
TURN_SPEED = 130

# Anything smaller than this on the gamepad stick is treated as zero, the
# cheap sticks never really come back to the centre.
JOYSTICK_DEADZONE = 0.15

# How often we push a drive packet to the Arduino while a stick is held
DRIVE_SEND_INTERVAL = 0.05  # seconds

# If the GUI stops sending for this long the Arduino stops the motors itself
COMMAND_TIMEOUT = 0.5

# ---------------------------------------------------------------------------
# Arms - 2 arms, 2 degrees of freedom each (shoulder + mid joint)
# ---------------------------------------------------------------------------
ARM_LEFT = 'L'
ARM_RIGHT = 'R'

JOINT_SHOULDER = 'S'
JOINT_MID = 'M'

# Safe travel of every joint, in degrees.  These are enforced on both sides,
# here and again in the Arduino sketch.
SHOULDER_MIN = -90
SHOULDER_MAX = 90
MID_MIN = -120
MID_MAX = 0

ARM_STEP_DEGREES = 5        # how far one gamepad nudge moves a joint

# ---------------------------------------------------------------------------
# Speech
# ---------------------------------------------------------------------------
LANG_BENGALI = 'bn'
LANG_ENGLISH = 'en'

# Google speech recognition language codes
STT_CODES = {
    LANG_BENGALI: 'bn-BD',
    LANG_ENGLISH: 'en-US',
}

LISTEN_TIMEOUT = 5
PHRASE_TIME_LIMIT = 10

# ---------------------------------------------------------------------------
# Knowledge files
# ---------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

LIBRARIAN_RESPONSES = {
    LANG_BENGALI: os.path.join(BASE_DIR, 'responses.json'),
    LANG_ENGLISH: os.path.join(BASE_DIR, 'responses_en.json'),
}

GENERAL_RESPONSES = os.path.join(BASE_DIR, 'general_responses.json')
