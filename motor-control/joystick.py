import RPi.GPIO as GPIO
import time
import curses

GPIO.cleanup()

# Motor 1 pins
EN1   = 21
DIR1  = 20
STEP1 = 16

# Motor 2 pins
EN2   = 26
DIR2  = 14
STEP2 = 15

GPIO.setmode(GPIO.BCM)

for pin in [EN1, DIR1, STEP1, EN2, DIR2, STEP2]:
    GPIO.setup(pin, GPIO.OUT)

GPIO.output(EN1, GPIO.HIGH)
GPIO.output(EN2, GPIO.HIGH)

STEP_DELAY = 0.001


def step_motor(step_pin):
    GPIO.output(step_pin, GPIO.HIGH)
    time.sleep(STEP_DELAY)
    GPIO.output(step_pin, GPIO.LOW)
    time.sleep(STEP_DELAY)


def set_direction(dir_pin, direction):
    # direction > 0 = forward, direction < 0 = reverse
    GPIO.output(dir_pin, GPIO.HIGH if direction > 0 else GPIO.LOW)


def curses_main(stdscr):
    curses.cbreak()
    stdscr.nodelay(True)
    stdscr.keypad(True)

    # Steps pending (to be consumed)
    m1_pending = 0
    m2_pending = 0

    # Steps completed (cumulative)
    m1_done = 0
    m2_done = 0

    while True:
        stdscr.clear()
        stdscr.addstr(0, 0, "Motor 1:")
        stdscr.addstr(1, 2, f"Steps pending:  {m1_pending}")
        stdscr.addstr(2, 2, f"Steps done:     {m1_done}")

        stdscr.addstr(4, 0, "Motor 2:")
        stdscr.addstr(5, 2, f"Steps pending:  {m2_pending}")
        stdscr.addstr(6, 2, f"Steps done:     {m2_done}")

        stdscr.addstr(8, 0, "Controls:")
        stdscr.addstr(9, 2, "w/s: add +/- steps to Motor 1")
        stdscr.addstr(10, 2, "Up/Down: add +/- steps to Motor 2")
        stdscr.addstr(12, 0, "Press q to quit")

        stdscr.refresh()

        key = stdscr.getch()
        if key == ord('q'):
            break

        # Motor 1 add steps
        if key == ord('w'):
            m1_pending += 50
        elif key == ord('s'):
            m1_pending -= 50

        # Motor 2 add steps
        elif key == curses.KEY_UP:
            m2_pending += 20
        elif key == curses.KEY_DOWN:
            m2_pending -= 20

        # Consume pending steps for Motor 1
        if m1_pending != 0:
            direction = 1 if m1_pending > 0 else -1
            set_direction(DIR1, direction)
            step_motor(STEP1)
            m1_pending -= direction
            m1_done += direction

        # Consume pending steps for Motor 2
        if m2_pending != 0:
            direction = 1 if m2_pending > 0 else -1
            set_direction(DIR2, direction)
            step_motor(STEP2)
            m2_pending -= direction
            m2_done += direction

        time.sleep(0.001)


try:
    curses.wrapper(curses_main)
finally:
    GPIO.cleanup()

