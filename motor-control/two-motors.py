import RPi.GPIO as GPIO
import time

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

# Enable both drivers
GPIO.output(EN1, GPIO.HIGH)
GPIO.output(EN2, GPIO.HIGH)

def run_motor(name, EN, DIR, STEP):
    print(f'Give Direction for {name}')
    direction = input()
    if direction == 't':
        GPIO.output(DIR, GPIO.LOW)
    else:
        GPIO.output(DIR, GPIO.HIGH)

    print(f'Gimme Steps for {name}')
    steps = int(input())
    print(f'Gimme Step Time for {name}')
    step_time = float(input())

    for _ in range(steps):
        GPIO.output(STEP, GPIO.HIGH)
        time.sleep(step_time)
        GPIO.output(STEP, GPIO.LOW)
        time.sleep(step_time)

try:
    run_motor("Motor 1", EN1, DIR1, STEP1)
    run_motor("Motor 2", EN2, DIR2, STEP2)

finally:
    GPIO.cleanup()

