# Manual Mode - drive Pixi by hand.
#
# The base has four DC gear motors (two a side, tank steering) and each arm
# has two stepper driven joints, the shoulder and the mid joint.  All of it
# hangs off the Arduino, which talks to the Pi over USB serial.
#
# Three ways to drive it:
#   1. a USB gamepad          - left stick drives, right stick moves the arms
#   2. the on-screen pad      - drag it with a finger on the touchscreen
#   3. the voice command      - press VOICE COMMAND and say "turn left"
#
# The Arduino stops the motors on its own if we go quiet for half a second,
# so a crashed GUI cannot leave the robot running into a bookshelf.

import threading
import time
import tkinter as tk

import config
import gamepad
import robot_link
import speech
import ui_theme as theme
import voice_commands

PAD_SIZE = 240          # on-screen joystick, pixels
PAD_RING = 6            # inset of the outer ring drawn on the pad
KNOB_RADIUS = 26
# How far the centre of the knob may travel, so its edge stays inside the ring
PAD_REACH = (PAD_SIZE / 2.0) - PAD_RING - KNOB_RADIUS

TICK_MS = 50            # how often we poll the pad and push a drive packet


class ManualMode(tk.Frame):

    def __init__(self, master, on_back=None):
        tk.Frame.__init__(self, master, bg=theme.BG)
        self.on_back = on_back

        self.link = robot_link.link
        self.pad = gamepad.pad

        self.selected_arm = config.ARM_LEFT
        # Current commanded angle of each joint, in degrees
        self.angles = {
            (config.ARM_LEFT, config.JOINT_SHOULDER): 0,
            (config.ARM_LEFT, config.JOINT_MID): 0,
            (config.ARM_RIGHT, config.JOINT_SHOULDER): 0,
            (config.ARM_RIGHT, config.JOINT_MID): 0,
        }

        self.active = False
        self.listening = False
        self.touch_vector = (0.0, 0.0)   # on-screen pad, -1..1
        self._tick_job = None
        self._arm_accumulator = {}

        self._build()

    # -- layout -------------------------------------------------------------
    def _build(self):
        header = tk.Frame(self, bg=theme.BG)
        header.pack(fill='x', padx=30, pady=(22, 6))

        theme.RoundedButton(header, '<  BACK', command=self._go_back,
                            width=110, height=38, fill=theme.SURFACE,
                            hover=theme.SURFACE_HI, text_color=theme.TEXT,
                            font_name='small', bg=theme.BG).pack(side='left')

        tk.Label(header, text='MANUAL MODE', bg=theme.BG, fg=theme.AMBER,
                 font=theme.font('heading')).pack(side='left', padx=20)

        self.pad_pill = theme.StatusPill(header, 'No gamepad', theme.TEXT_DIM,
                                         width=230)
        self.pad_pill.pack(side='right', padx=(8, 0))

        self.link_pill = theme.StatusPill(header, 'Arduino: disconnected',
                                          theme.RED, width=230)
        self.link_pill.pack(side='right')

        body = tk.Frame(self, bg=theme.BG)
        body.pack(fill='both', expand=True, padx=36, pady=10)

        self._build_drive(body)
        self._build_arms(body)
        self._build_footer()

    # -- left column: the joystick -----------------------------------------
    def _build_drive(self, parent):
        card = tk.Frame(parent, bg=theme.SURFACE, highlightthickness=1,
                        highlightbackground=theme.BORDER)
        card.pack(side='left', fill='both', expand=True, padx=(0, 10))

        tk.Label(card, text='DRIVE BASE  -  4 MOTORS', bg=theme.SURFACE,
                 fg=theme.AMBER, font=theme.font('small')).pack(pady=(14, 4))

        self.canvas = tk.Canvas(card, width=PAD_SIZE, height=PAD_SIZE,
                                bg=theme.SURFACE, highlightthickness=0)
        self.canvas.pack(pady=10)

        centre = PAD_SIZE // 2
        self.canvas.create_oval(PAD_RING, PAD_RING, PAD_SIZE - PAD_RING,
                                PAD_SIZE - PAD_RING,
                                outline=theme.BORDER, width=2)
        self.canvas.create_line(centre, 18, centre, PAD_SIZE - 18,
                                fill=theme.BORDER)
        self.canvas.create_line(18, centre, PAD_SIZE - 18, centre,
                                fill=theme.BORDER)
        self.knob = self.canvas.create_oval(centre - KNOB_RADIUS,
                                            centre - KNOB_RADIUS,
                                            centre + KNOB_RADIUS,
                                            centre + KNOB_RADIUS,
                                            fill=theme.AMBER, outline='')

        self.canvas.bind('<Button-1>', self._on_pad_drag)
        self.canvas.bind('<B1-Motion>', self._on_pad_drag)
        self.canvas.bind('<ButtonRelease-1>', self._on_pad_release)

        self.speed_label = tk.Label(card, text='L 0    R 0', bg=theme.SURFACE,
                                    fg=theme.TEXT, font=theme.font('mono'))
        self.speed_label.pack(pady=(0, 6))

        tk.Label(card, text='Drag the pad, or use the left stick on the gamepad',
                 bg=theme.SURFACE, fg=theme.TEXT_DIM,
                 font=theme.font('small'), wraplength=260).pack(pady=(0, 16))

    # -- right column: the arms --------------------------------------------
    def _build_arms(self, parent):
        card = tk.Frame(parent, bg=theme.SURFACE, highlightthickness=1,
                        highlightbackground=theme.BORDER)
        card.pack(side='left', fill='both', expand=True, padx=(10, 0))

        tk.Label(card, text='ARMS  -  2 DOF EACH', bg=theme.SURFACE,
                 fg=theme.AMBER, font=theme.font('small')).pack(pady=(14, 8))

        picker = tk.Frame(card, bg=theme.SURFACE)
        picker.pack()

        self.left_button = theme.RoundedButton(
            picker, 'LEFT ARM', command=lambda: self.select_arm(config.ARM_LEFT),
            width=150, height=44, font_name='body', bg=theme.SURFACE)
        self.left_button.pack(side='left', padx=6)

        self.right_button = theme.RoundedButton(
            picker, 'RIGHT ARM', command=lambda: self.select_arm(config.ARM_RIGHT),
            width=150, height=44, font_name='body', bg=theme.SURFACE)
        self.right_button.pack(side='left', padx=6)

        self.shoulder_scale = self._joint_slider(
            card, 'SHOULDER', config.SHOULDER_MIN, config.SHOULDER_MAX,
            config.JOINT_SHOULDER)
        self.mid_scale = self._joint_slider(
            card, 'MID JOINT', config.MID_MIN, config.MID_MAX,
            config.JOINT_MID)

        theme.RoundedButton(card, 'HOME ARMS', command=self.home_arms,
                            width=200, height=44, fill=theme.SURFACE_HI,
                            hover=theme.BORDER, text_color=theme.TEXT,
                            font_name='body', bg=theme.SURFACE).pack(pady=14)

        tk.Label(card, text='Right stick moves the selected arm. '
                            'LB / RB switch arms.',
                 bg=theme.SURFACE, fg=theme.TEXT_DIM,
                 font=theme.font('small'), wraplength=280).pack(pady=(0, 16))

        self.select_arm(config.ARM_LEFT)

    def _joint_slider(self, parent, title, low, high, joint):
        holder = tk.Frame(parent, bg=theme.SURFACE)
        holder.pack(fill='x', padx=26, pady=(14, 0))

        tk.Label(holder, text=title, bg=theme.SURFACE, fg=theme.TEXT_DIM,
                 font=theme.font('small'), anchor='w').pack(fill='x')

        scale = tk.Scale(holder, from_=low, to=high, orient='horizontal',
                         bg=theme.SURFACE, fg=theme.TEXT,
                         troughcolor=theme.BG, highlightthickness=0,
                         activebackground=theme.AMBER, bd=0,
                         font=theme.font('small'), length=280,
                         command=lambda value, j=joint: self._on_slider(j, value))
        scale.pack(fill='x')
        return scale

    # -- footer -------------------------------------------------------------
    def _build_footer(self):
        footer = tk.Frame(self, bg=theme.BG)
        footer.pack(fill='x', padx=36, pady=(6, 22))

        self.connect_button = theme.RoundedButton(
            footer, 'CONNECT ARDUINO', command=self.toggle_connection,
            width=220, height=54, fill=theme.SURFACE_HI, hover=theme.BORDER,
            text_color=theme.TEXT, font_name='body', bg=theme.BG)
        self.connect_button.pack(side='left')

        self.voice_button = theme.RoundedButton(
            footer, 'VOICE COMMAND', command=self.voice_command, width=240,
            height=54, fill=theme.ACCENT, hover=theme.ACCENT_DARK,
            font_name='body', bg=theme.BG)
        self.voice_button.pack(side='left', padx=12)

        theme.RoundedButton(footer, 'EMERGENCY STOP', command=self.emergency_stop,
                            width=240, height=54, fill=theme.RED,
                            hover='#b8413c', font_name='body',
                            bg=theme.BG).pack(side='right')

        self.log_label = tk.Label(self, text='Manual mode standing by.',
                                  bg=theme.BG, fg=theme.TEXT_DIM,
                                  font=theme.font('small'))
        self.log_label.pack(pady=(0, 14))

    # -- mode lifecycle -----------------------------------------------------
    def on_enter(self):
        """The shell calls this when Manual Mode comes on screen."""
        self.active = True
        self.pad.on_connect = self._on_pad_connect
        self.pad.on_button = self._on_pad_button
        self.pad.start()
        if not self.link.is_connected():
            self.toggle_connection()
        self._schedule_tick()

    def on_leave(self):
        """Always stop the motors when the operator leaves this screen."""
        self.active = False
        if self._tick_job is not None:
            self.after_cancel(self._tick_job)
            self._tick_job = None
        self.touch_vector = (0.0, 0.0)
        self._reset_knob()
        self.link.stop()
        self.pad.on_connect = None
        self.pad.on_button = None
        self.pad.stop()

    # -- Arduino ------------------------------------------------------------
    def toggle_connection(self):
        if self.link.is_connected():
            self.link.disconnect()
            self.link_pill.set('Arduino: disconnected', theme.RED)
            self.connect_button.set_text('CONNECT ARDUINO')
            self._log('Serial link closed.')
            return

        self._log('Opening %s ...' % self.link.port)
        self.connect_button.set_enabled(False)

        # connect() sleeps for two seconds while the Arduino reboots, so it
        # cannot run on the Tk thread or the whole window freezes.
        def worker():
            ok = self.link.connect() and self.link.ping()
            self.after(0, self._connection_result, ok)

        thread = threading.Thread(target=worker)
        thread.daemon = True
        thread.start()

    def _connection_result(self, ok):
        self.connect_button.set_enabled(True)
        if ok:
            self.link_pill.set('Arduino: connected', theme.GREEN)
            self.connect_button.set_text('DISCONNECT')
            self._log('Arduino ready on %s.' % self.link.port)
        else:
            self.link_pill.set('Arduino: disconnected', theme.RED)
            self.connect_button.set_text('CONNECT ARDUINO')
            self._log('No Arduino on %s - %s' % (self.link.port,
                                                 self.link.last_error or 'no reply'))

    # -- the drive loop -----------------------------------------------------
    def _schedule_tick(self):
        if self.active:
            self._tick_job = self.after(TICK_MS, self._tick)

    def _tick(self):
        drive_x, drive_y, arm_x, arm_y = self.pad.state()

        # The on-screen pad wins if a finger is actually on it
        touch_x, touch_y = self.touch_vector
        if touch_x or touch_y:
            drive_x, drive_y = touch_x, touch_y
        else:
            self._move_knob(drive_x, drive_y)

        left, right = self._mix(drive_x, drive_y)
        self.speed_label.config(text='L %-6d R %-6d' % (left, right))
        self.link.drive(left, right)

        self._apply_arm_stick(arm_x, arm_y)
        self._schedule_tick()

    def _mix(self, x, y):
        """Tank mixing - forward on both sides, turn by subtracting."""
        speed = y * config.MAX_DRIVE_SPEED
        turn = x * config.TURN_SPEED
        left = speed + turn
        right = speed - turn

        # Scale both back rather than clipping one, or the robot curves away
        peak = max(abs(left), abs(right))
        if peak > config.MAX_DRIVE_SPEED:
            scale = config.MAX_DRIVE_SPEED / peak
            left *= scale
            right *= scale
        return int(left), int(right)

    def _apply_arm_stick(self, arm_x, arm_y):
        """The right stick nudges the selected arm a few degrees at a time."""
        if not arm_x and not arm_y:
            self._arm_accumulator = {}
            return

        if arm_y:
            self._nudge_joint(config.JOINT_SHOULDER,
                              arm_y * config.ARM_STEP_DEGREES * 0.25)
        if arm_x:
            self._nudge_joint(config.JOINT_MID,
                              arm_x * config.ARM_STEP_DEGREES * 0.25)

    def _nudge_joint(self, joint, delta):
        key = (self.selected_arm, joint)
        # Accumulate the fractional degrees, only send a command once a whole
        # degree has built up - otherwise we flood the serial port.
        pending = self._arm_accumulator.get(key, 0.0) + delta
        if abs(pending) < 1.0:
            self._arm_accumulator[key] = pending
            return
        self._arm_accumulator[key] = 0.0

        angle = self.angles[key] + int(pending)
        scale = self.shoulder_scale if joint == config.JOINT_SHOULDER else self.mid_scale
        scale.set(angle)   # the slider callback does the actual sending

    # -- on-screen pad ------------------------------------------------------
    def _on_pad_drag(self, event):
        centre = PAD_SIZE / 2.0
        x = (event.x - centre) / PAD_REACH
        y = -(event.y - centre) / PAD_REACH

        # Clamp the length of the vector, not each axis on its own - clamping
        # separately lets a corner drag reach 1.0 on both axes at once, which
        # puts the knob outside the ring and asks for more speed than the
        # stick can actually give.
        length = (x * x + y * y) ** 0.5
        if length > 1.0:
            x /= length
            y /= length

        self.touch_vector = (x, y)
        self._move_knob(x, y)

    def _on_pad_release(self, event):
        self.touch_vector = (0.0, 0.0)
        self._reset_knob()

    def _move_knob(self, x, y):
        # The gamepad sticks are square edged too, so clamp here as well
        length = (x * x + y * y) ** 0.5
        if length > 1.0:
            x /= length
            y /= length

        centre = PAD_SIZE / 2.0
        cx = centre + x * PAD_REACH
        cy = centre - y * PAD_REACH
        self.canvas.coords(self.knob, cx - KNOB_RADIUS, cy - KNOB_RADIUS,
                           cx + KNOB_RADIUS, cy + KNOB_RADIUS)

    def _reset_knob(self):
        self._move_knob(0.0, 0.0)
        self.speed_label.config(text='L 0      R 0')

    # -- arms ---------------------------------------------------------------
    def select_arm(self, arm):
        self.selected_arm = arm
        active, inactive = self.left_button, self.right_button
        if arm == config.ARM_RIGHT:
            active, inactive = self.right_button, self.left_button
        active.set_fill(theme.AMBER, '#d18e30')
        inactive.set_fill(theme.SURFACE_HI, theme.BORDER)

        # Show the angles this arm is actually at
        self.shoulder_scale.set(self.angles[(arm, config.JOINT_SHOULDER)])
        self.mid_scale.set(self.angles[(arm, config.JOINT_MID)])

    def _on_slider(self, joint, value):
        angle = int(float(value))
        key = (self.selected_arm, joint)
        if self.angles[key] == angle:
            return
        self.angles[key] = angle
        self.link.move_joint(self.selected_arm, joint, angle)

    def home_arms(self):
        for key in self.angles:
            self.angles[key] = 0
        self.shoulder_scale.set(0)
        self.mid_scale.set(0)
        self.link.home_arms()
        self._log('Arms returned to the home position.')

    def emergency_stop(self):
        self.touch_vector = (0.0, 0.0)
        self._reset_knob()
        self.link.stop()
        self._log('EMERGENCY STOP - all motors cut.')

    # -- voice --------------------------------------------------------------
    def voice_command(self):
        if self.listening:
            return
        self.listening = True
        self.voice_button.set_enabled(False)
        self.voice_button.set_text('LISTENING...')
        self._log('Say a command, for example "turn left" or "raise left arm".')

        thread = threading.Thread(target=self._voice_worker)
        thread.daemon = True
        thread.start()

    def _voice_worker(self):
        phrase, error = speech.listen(config.LANG_ENGLISH)
        if error:
            self.after(0, self._voice_done, error)
            return

        action, argument, description = voice_commands.parse(phrase)
        if action is None:
            self.after(0, self._voice_done, description)
            return

        self.after(0, self._log, 'Heard "%s" -> %s' % (phrase, description))
        self._run_action(action, argument)
        self.after(0, self._voice_done, None)

    def _run_action(self, action, argument):
        """Carry out one voice command.  Runs on the worker thread."""
        if action == 'stop':
            self.link.stop()

        elif action == 'drive':
            left, right = argument
            speed = config.DEFAULT_DRIVE_SPEED
            self.link.drive(left * speed, right * speed, force=True)
            time.sleep(voice_commands.DRIVE_BURST)
            self.link.stop()

        elif action == 'turn':
            left, right = argument
            speed = config.TURN_SPEED
            self.link.drive(left * speed, right * speed, force=True)
            time.sleep(voice_commands.TURN_BURST)
            self.link.stop()

        elif action == 'joint':
            arm, joint, angle = argument
            self.angles[(arm, joint)] = angle
            self.link.move_joint(arm, joint, angle)
            self.after(0, self.select_arm, arm)

        elif action == 'home':
            self.after(0, self.home_arms)

        elif action == 'wave':
            arm = config.ARM_RIGHT
            self.link.move_joint(arm, config.JOINT_SHOULDER, 80)
            time.sleep(0.8)
            for _ in range(3):
                self.link.move_joint(arm, config.JOINT_MID, -60)
                time.sleep(0.5)
                self.link.move_joint(arm, config.JOINT_MID, -10)
                time.sleep(0.5)
            self.link.home_arms()
            self.after(0, self.home_arms)

    def _voice_done(self, error):
        self.listening = False
        self.voice_button.set_enabled(True)
        self.voice_button.set_text('VOICE COMMAND')
        if error:
            self._log(error)

    # -- gamepad callbacks --------------------------------------------------
    def _on_pad_connect(self, connected):
        # These come off the gamepad thread, hop back onto the Tk thread
        self.after(0, self._pad_status, connected)

    def _pad_status(self, connected):
        if connected:
            self.pad_pill.set(self.pad.name[:26] or 'Gamepad ready', theme.GREEN)
        else:
            self.pad_pill.set('No gamepad', theme.TEXT_DIM)

    def _on_pad_button(self, button):
        if button == gamepad.BUTTON_LEFT_ARM:
            self.after(0, self.select_arm, config.ARM_LEFT)
        elif button == gamepad.BUTTON_RIGHT_ARM:
            self.after(0, self.select_arm, config.ARM_RIGHT)
        elif button == gamepad.BUTTON_STOP:
            self.after(0, self.emergency_stop)

    # -- housekeeping -------------------------------------------------------
    def _log(self, message):
        print(message)
        self.log_label.config(text=message)

    def _go_back(self):
        if self.on_back:
            self.on_back()


if __name__ == '__main__':
    root = tk.Tk()
    root.title('Pixi - Manual Mode')
    root.geometry('1200x800')
    root.configure(bg=theme.BG)
    theme.init_fonts(root)
    frame = ManualMode(root)
    frame.pack(fill='both', expand=True)
    frame.on_enter()
    root.protocol('WM_DELETE_WINDOW', lambda: (frame.on_leave(), root.destroy()))
    root.mainloop()
