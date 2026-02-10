import os

# Motor Pins
MOTOR_PINS = {
    'EN1': 21, 'DIR1': 20, 'STEP1': 16,
    'EN2': 26, 'DIR2': 14, 'STEP2': 15
}

# Motor Physics
STEPS_PER_REV_M1 = 1200  # Base motor
STEPS_PER_REV_M2 = 600   # Top motor
MICROSTEPPING = 8
DEG_PER_STEP_M1 = 360 / (STEPS_PER_REV_M1 * MICROSTEPPING)
DEG_PER_STEP_M2 = 360 / (STEPS_PER_REV_M2 * MICROSTEPPING)
STEP_DELAY = 0.003

# Temi Configuration
MQTT_HOST = os.getenv('MQTT_HOST', 'localhost')
MQTT_PORT = int(os.getenv('MQTT_PORT', 1883))
TEMI_SERIAL = os.getenv('TEMI_SERIAL', 'xxxxxxxxxxx') # Add Temi Serial Here

# Storage
STORAGE_FOLDER = 'secure_dicom_storage'

# Flask Config
HOST = '0.0.0.0'
PORT = 5001
DEBUG = False
