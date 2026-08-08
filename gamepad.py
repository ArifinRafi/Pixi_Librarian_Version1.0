# USB gamepad reader for Manual Mode.
#
# A background thread polls the pad and hands the latest stick positions to
# the GUI.  We use pygame's joystick module because it is the only thing that
# works the same on the Pi and on a Windows dev machine.  If pygame is not
# installed, or nothing is plugged in, everything here reports "no pad" and
# Manual Mode falls back to the on-screen controls.
#
# Mapping (tested with a generic Xbox-style pad):
#   left stick  Y  -> forward / reverse
#   left stick  X  -> turn
#   right stick Y  -> shoulder joint
#   right stick X  -> mid joint
#   button 4 (LB)  -> select left arm
#   button 5 (RB)  -> select right arm
#   button 1 (B)   -> emergency stop

import os
import threading
import time

import config

# Ask SDL for the dummy video driver before pygame is ever imported.
#
# We only want the joystick subsystem, but SDL insists on a video device
# before it will pump events.  The real macOS driver registers a Cocoa app
# and touches the main menu, which is illegal from a background thread and
# takes the whole process down with an NSException - so we give it the dummy
# driver instead.  It opens no window and never touches AppKit.
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')

# Axis numbers on a standard pad
AXIS_DRIVE_Y = 1
AXIS_DRIVE_X = 0
AXIS_ARM_Y = 3
AXIS_ARM_X = 2

BUTTON_LEFT_ARM = 4
BUTTON_RIGHT_ARM = 5
BUTTON_STOP = 1

POLL_INTERVAL = 0.03


def _deadzone(value):
    if abs(value) < config.JOYSTICK_DEADZONE:
        return 0.0
    # Rescale so the stick still reaches 1.0 after the deadzone is removed
    sign = 1.0 if value > 0 else -1.0
    span = 1.0 - config.JOYSTICK_DEADZONE
    return sign * (abs(value) - config.JOYSTICK_DEADZONE) / span


class Gamepad(object):

    def __init__(self):
        self.name = ''
        self.connected = False
        self.running = False
        self.thread = None
        self.lock = threading.Lock()

        # Latest state, read by the GUI
        self.drive_x = 0.0
        self.drive_y = 0.0
        self.arm_x = 0.0
        self.arm_y = 0.0

        # Callbacks the GUI can hook into
        self.on_button = None       # called with the button number
        self.on_connect = None      # called with True/False

        self._pygame = None
        self._joystick = None
        self._buttons = []      # last seen button state, for edge detection

    # -- lifecycle ----------------------------------------------------------
    def start(self):
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._run)
        self.thread.daemon = True
        self.thread.start()

    def stop(self):
        self.running = False
        if self.thread is not None:
            self.thread.join(timeout=1.0)
            self.thread = None

    def state(self):
        """Snapshot of the sticks, already deadzoned."""
        with self.lock:
            return (self.drive_x, self.drive_y, self.arm_x, self.arm_y)

    # -- worker thread ------------------------------------------------------
    def _run(self):
        try:
            import pygame
        except ImportError:
            print("pygame is not installed - the USB gamepad is disabled.")
            self._set_connected(False)
            return

        self._pygame = pygame
        try:
            # Note: NOT pygame.init(), that brings up the real video driver.
            # display.init() under the dummy driver is all SDL needs before
            # it will let us pump events.
            pygame.display.init()
            pygame.joystick.init()
        except Exception as e:
            print("Could not start SDL for the gamepad: %s" % e)
            self._set_connected(False)
            return

        while self.running:
            if self._joystick is None:
                self._try_open()
                if self._joystick is None:
                    # Nothing plugged in, check again in a moment
                    time.sleep(1.0)
                    continue

            try:
                # Refresh the driver's copy of the stick and button state.
                # We poll rather than read the event queue - the queue needs
                # a real video device behind it, and we do not have one.
                pygame.event.pump()

                axes = self._joystick.get_numaxes()
                with self.lock:
                    self.drive_x = _deadzone(self._axis(AXIS_DRIVE_X, axes))
                    # Pads report "stick pushed forward" as -1, flip it
                    self.drive_y = -_deadzone(self._axis(AXIS_DRIVE_Y, axes))
                    self.arm_x = _deadzone(self._axis(AXIS_ARM_X, axes))
                    self.arm_y = -_deadzone(self._axis(AXIS_ARM_Y, axes))

                self._poll_buttons()
            except Exception as e:
                # Usually means the pad was unplugged mid-poll
                print("Gamepad read failed: %s" % e)
                self._close()

            time.sleep(POLL_INTERVAL)

        self._close()
        try:
            self._pygame.joystick.quit()
            self._pygame.display.quit()
        except Exception:
            pass

    def _poll_buttons(self):
        """Edge detect the buttons ourselves, since we do not use events."""
        count = self._joystick.get_numbuttons()
        pressed = []
        for i in range(count):
            pressed.append(bool(self._joystick.get_button(i)))

        if len(self._buttons) != count:
            # First poll after a pad is opened - remember, do not fire
            self._buttons = pressed
            return

        for i in range(count):
            if pressed[i] and not self._buttons[i] and self.on_button:
                self.on_button(i)
        self._buttons = pressed

    def _axis(self, index, count):
        if index >= count:
            return 0.0
        return self._joystick.get_axis(index)

    def _try_open(self):
        pygame = self._pygame
        try:
            # Re-scan, otherwise a pad plugged in after startup is never seen
            pygame.joystick.quit()
            pygame.joystick.init()
            if pygame.joystick.get_count() == 0:
                self._set_connected(False)
                return
            self._joystick = pygame.joystick.Joystick(0)
            self._joystick.init()
            # Forget the old button state, or reconnecting a pad with a
            # button held down fires a phantom press.
            self._buttons = []
            self.name = self._joystick.get_name()
            print("Gamepad connected: %s" % self.name)
            self._set_connected(True)
        except Exception as e:
            print("Could not open gamepad: %s" % e)
            self._joystick = None
            self._set_connected(False)

    def _close(self):
        self._joystick = None
        self.name = ''
        self._buttons = []
        with self.lock:
            self.drive_x = self.drive_y = 0.0
            self.arm_x = self.arm_y = 0.0
        self._set_connected(False)

    def _set_connected(self, connected):
        if connected == self.connected:
            return
        self.connected = connected
        if self.on_connect:
            self.on_connect(connected)


pad = Gamepad()
