# Serial link between the Raspberry Pi and the Arduino on the robot base.
#
# Wire protocol - one ASCII command per line, the Arduino answers with a
# single line as well:
#
#   P                       ping                -> OK PIXI
#   D,<left>,<right>        drive, -255..255    -> OK
#   A,<L|R>,<S|M>,<deg>     move an arm joint   -> OK
#   H                       home both arms      -> OK
#   S                       stop everything     -> OK
#
# Anything the Arduino does not understand comes back as "ERR".
#
# The whole thing degrades quietly: if there is no Arduino plugged in the GUI
# still runs, it just reports "Disconnected" and drops the commands.  That
# makes it possible to work on the interface at a desk.

import threading
import time

import serial

import config


class RobotLink(object):

    def __init__(self, port=None, baud=None):
        self.port = port or config.SERIAL_PORT
        self.baud = baud or config.SERIAL_BAUD
        self.serial = None
        self.lock = threading.Lock()
        self.last_error = ''
        # Remember what we last sent so we do not spam identical drive packets
        self._last_drive = None

    # -- connection ---------------------------------------------------------
    def connect(self):
        """Open the port.  Returns True on success."""
        with self.lock:
            if self.serial is not None and self.serial.is_open:
                return True
            try:
                self.serial = serial.Serial(self.port, self.baud,
                                            timeout=config.SERIAL_TIMEOUT)
            except Exception as e:
                self.serial = None
                self.last_error = str(e)
                print("Could not open %s: %s" % (self.port, e))
                return False

        # Opening the port resets the Arduino, wait for the bootloader
        time.sleep(config.SERIAL_BOOT_DELAY)
        with self.lock:
            try:
                self.serial.reset_input_buffer()
            except Exception:
                pass
        self.last_error = ''
        return True

    def disconnect(self):
        with self.lock:
            if self.serial is not None:
                try:
                    self.serial.write(b'S\n')
                    self.serial.flush()
                    self.serial.close()
                except Exception:
                    pass
                self.serial = None
        self._last_drive = None

    def is_connected(self):
        return self.serial is not None and self.serial.is_open

    # -- raw send -----------------------------------------------------------
    def send(self, command):
        """Send one command line.  Returns the Arduino's reply, or None."""
        with self.lock:
            if self.serial is None or not self.serial.is_open:
                return None
            try:
                self.serial.write((command + '\n').encode('ascii'))
                self.serial.flush()
                reply = self.serial.readline().decode('ascii', 'ignore')
                return reply.strip()
            except Exception as e:
                self.last_error = str(e)
                print("Serial write failed: %s" % e)
                # The cable was probably yanked out - drop the handle so the
                # next connect() starts fresh.
                try:
                    self.serial.close()
                except Exception:
                    pass
                self.serial = None
                return None

    def ping(self):
        reply = self.send('P')
        return reply is not None and reply.startswith('OK')

    # -- drive base ---------------------------------------------------------
    def drive(self, left, right, force=False):
        """Set the two sides of the base.  left/right are -255..255."""
        left = _clamp(int(left), -config.MAX_DRIVE_SPEED, config.MAX_DRIVE_SPEED)
        right = _clamp(int(right), -config.MAX_DRIVE_SPEED, config.MAX_DRIVE_SPEED)

        packet = (left, right)
        # Zero has to be resent anyway, the Arduino needs to hear the stop
        if not force and packet == self._last_drive and packet != (0, 0):
            return
        self._last_drive = packet
        return self.send('D,%d,%d' % (left, right))

    def stop(self):
        self._last_drive = (0, 0)
        return self.send('S')

    # -- arms ---------------------------------------------------------------
    def move_joint(self, arm, joint, degrees):
        """Move one arm joint to an absolute angle, in degrees."""
        if joint == config.JOINT_SHOULDER:
            degrees = _clamp(degrees, config.SHOULDER_MIN, config.SHOULDER_MAX)
        else:
            degrees = _clamp(degrees, config.MID_MIN, config.MID_MAX)
        return self.send('A,%s,%s,%d' % (arm, joint, int(round(degrees))))

    def home_arms(self):
        return self.send('H')


def _clamp(value, low, high):
    if value < low:
        return low
    if value > high:
        return high
    return value


# A single link shared by every mode - the serial port can only be opened once.
link = RobotLink()
