/*
   Pixi - Autonomous Humanoid Librarian Robot
   Motor controller firmware, Version 1.0
   Roboway Labs, Dhaka

   Board : Arduino Mega 2560
   Host  : Raspberry Pi 5B over USB serial, 115200 baud

   Hardware
   --------
   Base : 4 DC gear motors, two per side, driven by 2 x L298N.
          The two motors on a side are wired to the same driver channel and
          always turn together, so we only ever steer with two speeds.

   Arms : 2 arms x 2 joints (shoulder + mid), 4 NEMA-17 steppers on A4988
          drivers.  Each joint has a limit switch used for homing.

   Protocol (one ASCII command per line, reply is one line)
   --------
     P                     ping                     -> OK PIXI 1.0
     D,<left>,<right>      drive, -255..255 each    -> OK
     A,<L|R>,<S|M>,<deg>   move one joint, absolute -> OK
     H                     home both arms           -> OK
     S                     stop everything          -> OK
     anything else                                  -> ERR

   Safety
   ------
   If no command arrives for COMMAND_TIMEOUT milliseconds the base stops on
   its own.  The Pi sends a drive packet every 50 ms while a stick is held,
   so a crashed GUI or an unplugged cable brings the robot to a halt instead
   of leaving it running into a bookshelf.
*/

#include <AccelStepper.h>

// ---------------------------------------------------------------------------
// Pin map - base (2 x L298N)
// ---------------------------------------------------------------------------
const int LEFT_EN   = 2;    // ENA, PWM
const int LEFT_IN1  = 22;
const int LEFT_IN2  = 23;

const int RIGHT_EN  = 3;    // ENB, PWM
const int RIGHT_IN1 = 24;
const int RIGHT_IN2 = 25;

// ---------------------------------------------------------------------------
// Pin map - arms (4 x A4988, STEP / DIR / limit switch)
// ---------------------------------------------------------------------------
const int L_SHOULDER_STEP = 30;
const int L_SHOULDER_DIR  = 31;
const int L_SHOULDER_LIM  = 32;

const int L_MID_STEP      = 33;
const int L_MID_DIR       = 34;
const int L_MID_LIM       = 35;

const int R_SHOULDER_STEP = 36;
const int R_SHOULDER_DIR  = 37;
const int R_SHOULDER_LIM  = 38;

const int R_MID_STEP      = 39;
const int R_MID_DIR       = 40;
const int R_MID_LIM       = 41;

const int STEPPER_ENABLE  = 42;   // shared /EN on all four drivers, active LOW

// ---------------------------------------------------------------------------
// Mechanics
// ---------------------------------------------------------------------------
// NEMA-17 is 200 full steps per turn, the A4988 jumpers are set to 1/8, and
// the joints run through a 1:5 belt reduction.
const float STEPS_PER_REV   = 200.0;
const float MICROSTEPS      = 8.0;
const float GEAR_RATIO      = 5.0;
const float STEPS_PER_DEGREE = (STEPS_PER_REV * MICROSTEPS * GEAR_RATIO) / 360.0;

const float ARM_MAX_SPEED    = 900.0;   // steps per second
const float ARM_ACCELERATION = 400.0;

// Joint travel limits, degrees.  Kept in step with config.py on the Pi.
const int SHOULDER_MIN = -90;
const int SHOULDER_MAX =  90;
const int MID_MIN      = -120;
const int MID_MAX      =  0;

const unsigned long COMMAND_TIMEOUT = 500;   // ms

// ---------------------------------------------------------------------------
// Steppers.  Order: 0 = left shoulder, 1 = left mid, 2 = right shoulder,
// 3 = right mid.
// ---------------------------------------------------------------------------
AccelStepper leftShoulder(AccelStepper::DRIVER, L_SHOULDER_STEP, L_SHOULDER_DIR);
AccelStepper leftMid(AccelStepper::DRIVER, L_MID_STEP, L_MID_DIR);
AccelStepper rightShoulder(AccelStepper::DRIVER, R_SHOULDER_STEP, R_SHOULDER_DIR);
AccelStepper rightMid(AccelStepper::DRIVER, R_MID_STEP, R_MID_DIR);

AccelStepper *joints[4] = { &leftShoulder, &leftMid, &rightShoulder, &rightMid };
const int jointLimitPin[4] = { L_SHOULDER_LIM, L_MID_LIM, R_SHOULDER_LIM, R_MID_LIM };

String inputLine = "";
unsigned long lastCommandAt = 0;
bool driving = false;

// ---------------------------------------------------------------------------
void setup() {
  Serial.begin(115200);

  pinMode(LEFT_EN, OUTPUT);
  pinMode(LEFT_IN1, OUTPUT);
  pinMode(LEFT_IN2, OUTPUT);
  pinMode(RIGHT_EN, OUTPUT);
  pinMode(RIGHT_IN1, OUTPUT);
  pinMode(RIGHT_IN2, OUTPUT);

  pinMode(STEPPER_ENABLE, OUTPUT);
  digitalWrite(STEPPER_ENABLE, LOW);   // drivers on

  for (int i = 0; i < 4; i++) {
    pinMode(jointLimitPin[i], INPUT_PULLUP);
    joints[i]->setMaxSpeed(ARM_MAX_SPEED);
    joints[i]->setAcceleration(ARM_ACCELERATION);
  }

  stopBase();
  inputLine.reserve(32);
  lastCommandAt = millis();
}

// ---------------------------------------------------------------------------
void loop() {
  readSerial();

  // Keep the arms moving - AccelStepper needs this called as often as we can
  for (int i = 0; i < 4; i++) {
    joints[i]->run();
  }

  // Watchdog: the Pi has gone quiet, stop the base
  if (driving && (millis() - lastCommandAt > COMMAND_TIMEOUT)) {
    stopBase();
  }
}

// ---------------------------------------------------------------------------
void readSerial() {
  while (Serial.available() > 0) {
    char c = (char)Serial.read();
    if (c == '\n' || c == '\r') {
      if (inputLine.length() > 0) {
        handleCommand(inputLine);
        inputLine = "";
      }
    } else if (inputLine.length() < 30) {
      inputLine += c;
    }
  }
}

// ---------------------------------------------------------------------------
void handleCommand(String line) {
  line.trim();
  if (line.length() == 0) {
    return;
  }

  lastCommandAt = millis();
  char code = line.charAt(0);

  if (code == 'P') {
    Serial.println("OK PIXI 1.0");

  } else if (code == 'S') {
    stopBase();
    for (int i = 0; i < 4; i++) {
      joints[i]->stop();
    }
    Serial.println("OK");

  } else if (code == 'H') {
    homeArms();
    Serial.println("OK");

  } else if (code == 'D') {
    // D,<left>,<right>
    int firstComma = line.indexOf(',');
    int secondComma = line.indexOf(',', firstComma + 1);
    if (firstComma < 0 || secondComma < 0) {
      Serial.println("ERR");
      return;
    }
    int left = line.substring(firstComma + 1, secondComma).toInt();
    int right = line.substring(secondComma + 1).toInt();
    drive(left, right);
    Serial.println("OK");

  } else if (code == 'A') {
    // A,<L|R>,<S|M>,<degrees>
    int firstComma = line.indexOf(',');
    int secondComma = line.indexOf(',', firstComma + 1);
    int thirdComma = line.indexOf(',', secondComma + 1);
    if (firstComma < 0 || secondComma < 0 || thirdComma < 0) {
      Serial.println("ERR");
      return;
    }
    char arm = line.charAt(firstComma + 1);
    char joint = line.charAt(secondComma + 1);
    int degrees = line.substring(thirdComma + 1).toInt();

    if (moveJoint(arm, joint, degrees)) {
      Serial.println("OK");
    } else {
      Serial.println("ERR");
    }

  } else {
    Serial.println("ERR");
  }
}

// ---------------------------------------------------------------------------
// Base
// ---------------------------------------------------------------------------
void drive(int left, int right) {
  left = constrain(left, -255, 255);
  right = constrain(right, -255, 255);

  setSide(LEFT_EN, LEFT_IN1, LEFT_IN2, left);
  setSide(RIGHT_EN, RIGHT_IN1, RIGHT_IN2, right);

  driving = (left != 0 || right != 0);
}

void setSide(int enablePin, int in1, int in2, int speed) {
  if (speed > 0) {
    digitalWrite(in1, HIGH);
    digitalWrite(in2, LOW);
  } else if (speed < 0) {
    digitalWrite(in1, LOW);
    digitalWrite(in2, HIGH);
  } else {
    // Both low is a coast, both high would be a hard brake.  Coasting is
    // kinder to the gearboxes on a robot this heavy.
    digitalWrite(in1, LOW);
    digitalWrite(in2, LOW);
  }
  analogWrite(enablePin, abs(speed));
}

void stopBase() {
  setSide(LEFT_EN, LEFT_IN1, LEFT_IN2, 0);
  setSide(RIGHT_EN, RIGHT_IN1, RIGHT_IN2, 0);
  driving = false;
}

// ---------------------------------------------------------------------------
// Arms
// ---------------------------------------------------------------------------
int jointIndex(char arm, char joint) {
  if (arm == 'L' && joint == 'S') return 0;
  if (arm == 'L' && joint == 'M') return 1;
  if (arm == 'R' && joint == 'S') return 2;
  if (arm == 'R' && joint == 'M') return 3;
  return -1;
}

bool moveJoint(char arm, char joint, int degrees) {
  int index = jointIndex(arm, joint);
  if (index < 0) {
    return false;
  }

  // Clamp here as well as on the Pi - a garbled serial line must not be able
  // to fold an arm back into the robot's own body.
  if (joint == 'S') {
    degrees = constrain(degrees, SHOULDER_MIN, SHOULDER_MAX);
  } else {
    degrees = constrain(degrees, MID_MIN, MID_MAX);
  }

  long target = (long)(degrees * STEPS_PER_DEGREE);
  joints[index]->moveTo(target);
  return true;
}

void homeArms() {
  // Back every joint off towards zero until its limit switch closes, then
  // call that position zero.  Blocking, but homing only happens on request.
  for (int i = 0; i < 4; i++) {
    joints[i]->setMaxSpeed(ARM_MAX_SPEED / 3.0);
    joints[i]->move(-100000L);

    unsigned long startedAt = millis();
    while (digitalRead(jointLimitPin[i]) == HIGH) {
      joints[i]->run();
      // Give up after 15 seconds rather than grinding a stalled joint
      if (millis() - startedAt > 15000UL) {
        break;
      }
    }

    joints[i]->stop();
    joints[i]->setCurrentPosition(0);
    joints[i]->setMaxSpeed(ARM_MAX_SPEED);
    joints[i]->moveTo(0);
  }
}
