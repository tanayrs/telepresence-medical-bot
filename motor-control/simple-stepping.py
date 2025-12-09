import RPi.GPIO as GPIO
import time

EN = 21
DIR = 20
STEP = 16

GPIO.setmode(GPIO.BCM)
GPIO.setup(EN, GPIO.OUT)
GPIO.setup(DIR, GPIO.OUT)
GPIO.setup(STEP, GPIO.OUT)

GPIO.output(EN, GPIO.HIGH)   # Enable driver (HIGH = enable on most TB6560 boards)

print(f'Give Direction Bro')
direction = input()
if direction == 't':
    GPIO.output(DIR, GPIO.LOW)   # Pick a direction
else:
    GPIO.output(DIR, GPIO.HIGH)

print(f'Gimme Steps bro')
steps = int(input())
print(f'Gimme Step Time bro')
step_time = float(input())
try:
    for _ in range(steps):         # 200 steps
        GPIO.output(STEP, GPIO.HIGH)
        time.sleep(step_time)
        GPIO.output(STEP, GPIO.LOW)
        time.sleep(step_time)
except:
    GPIO.cleanup()

