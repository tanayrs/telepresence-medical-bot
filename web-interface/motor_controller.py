import time
import threading
import logging

logger = logging.getLogger(__name__)

class MotorController:
    def __init__(self, pins, deg_per_step_m1, deg_per_step_m2, step_delay):
        self.pins = pins
        self.deg_per_step = {'m1': deg_per_step_m1, 'm2': deg_per_step_m2}
        self.step_delay = step_delay
        self.state = {
            'm1_pending': 0, 'm1_pos': 0,
            'm2_pending': 0, 'm2_pos': 0,
            'running': True
        }
        self.target_steps = {'m1': 0, 'm2': 0}  # Store target positions in steps
        self.lock = threading.Lock()
        self.thread = threading.Thread(target=self._control_loop)
        self.thread.start()

        # GPIO Setup
        try:
            import RPi.GPIO as GPIO
            self.gpio_available = True
            GPIO.setmode(GPIO.BCM)
            for pin in self.pins.values():
                GPIO.setup(pin, GPIO.OUT)
            GPIO.output(self.pins['EN1'], GPIO.HIGH)
            GPIO.output(self.pins['EN2'], GPIO.HIGH)
        except ImportError:
            logger.warning("RPi.GPIO not found. Running in simulation mode.")
            self.gpio_available = False

    def move_motor(self, motor, direction, steps):
        with self.lock:
            if motor == 'm1':
                self.state['m1_pending'] += steps if direction == 'forward' else -steps
            elif motor == 'm2':
                self.state['m2_pending'] += steps if direction == 'forward' else -steps

    def set_target_angle(self, motor, angle):
        self.target_steps[motor] = round(angle / self.deg_per_step[motor])
        with self.lock:
            self.state[f'{motor}_pending'] = self.target_steps[motor] - self.state[f'{motor}_pos']

    def reset_angles(self):
        self.target_steps['m1'] = 0
        self.target_steps['m2'] = 0
        with self.lock:
            self.state['m1_pending'] = -self.state['m1_pos']
            self.state['m2_pending'] = -self.state['m2_pos']

    def tare_position(self):
        with self.lock:
            self.state['m1_pos'] = 0
            self.state['m2_pos'] = 0
            self.state['m1_pending'] = 0
            self.state['m2_pending'] = 0
        self.target_steps['m1'] = 0
        self.target_steps['m2'] = 0

    def emergency_stop(self):
        with self.lock:
            self.state['m1_pending'] = 0
            self.state['m2_pending'] = 0

    def get_positions(self):
        with self.lock:
            return {
                'm1': self.state['m1_pos'] * self.deg_per_step['m1'],
                'm2': self.state['m2_pos'] * self.deg_per_step['m2']
            }

    def get_targets(self):
        return {
            'm1': self.target_steps['m1'] * self.deg_per_step['m1'],
            'm2': self.target_steps['m2'] * self.deg_per_step['m2']
        }

    def stop(self):
        self.state['running'] = False
        self.thread.join()
        if self.gpio_available:
            import RPi.GPIO as GPIO
            GPIO.cleanup()

    def _set_direction(self, dir_pin, direction):
        if not self.gpio_available:
            return
        import RPi.GPIO as GPIO
        GPIO.output(dir_pin, GPIO.HIGH if direction > 0 else GPIO.LOW)

    def _step_pin_pulse(self, step_pin):
        if not self.gpio_available:
            time.sleep(self.step_delay * 2)
            return
        import RPi.GPIO as GPIO
        GPIO.output(step_pin, GPIO.HIGH)
        time.sleep(self.step_delay)
        GPIO.output(step_pin, GPIO.LOW)
        time.sleep(self.step_delay)

    def _control_loop(self):
        logger.info("Motor control thread started...")
        while self.state['running']:
            moved = False
            with self.lock:
                # Motor 1
                if self.state['m1_pending'] != 0:
                    direction = 1 if self.state['m1_pending'] > 0 else -1
                    self._set_direction(self.pins['DIR1'], direction)
                    self._step_pin_pulse(self.pins['STEP1'])
                    self.state['m1_pending'] -= direction
                    self.state['m1_pos'] += direction
                    moved = True
                # Motor 2
                if self.state['m2_pending'] != 0:
                    direction = 1 if self.state['m2_pending'] > 0 else -1
                    self._set_direction(self.pins['DIR2'], direction)
                    self._step_pin_pulse(self.pins['STEP2'])
                    self.state['m2_pending'] -= direction
                    self.state['m2_pos'] += direction
                    moved = True
            if not moved:
                time.sleep(0.01)