import cv2
import time
import threading
import logging
from flask import Flask, Response, render_template, request, jsonify

from config import (
    MOTOR_PINS, STEPS_PER_REV, MICROSTEPPING, DEG_PER_STEP, STEP_DELAY,
    MQTT_HOST, MQTT_PORT, TEMI_SERIAL, STORAGE_FOLDER, HOST, PORT, DEBUG
)
from motor_controller import MotorController
from dicom_handler import DICOMHandler
from temi_controller import TemiController

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Initialize components
motor_controller = MotorController(MOTOR_PINS, DEG_PER_STEP, STEP_DELAY)
dicom_handler = DICOMHandler(STORAGE_FOLDER)
temi_controller = TemiController(MQTT_HOST, MQTT_PORT, TEMI_SERIAL)

# Flask App
app = Flask(__name__)
camera = cv2.VideoCapture(0)
global_frame = None
frame_lock = threading.Lock()

def generate_frames():
    global global_frame
    while True:
        success, frame = camera.read()
        if not success:
            break
        with frame_lock:
            global_frame = frame.copy()
        ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
        yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/control/<motor>/<direction>')
def control_motor(motor, direction):
    steps = 50 if motor == 'm1' else 20
    motor_controller.move_motor(motor, direction, steps)
    return jsonify(success=True)

@app.route('/save_dicom', methods=['POST'])
def save_dicom_route():
    data = request.json
    with frame_lock:
        if global_frame is None:
            return jsonify(success=False, error="No camera frame available")
        image_rgb = cv2.cvtColor(global_frame, cv2.COLOR_BGR2RGB)

    try:
        positions = motor_controller.get_positions()
        fname = dicom_handler.save_as_dicom(image_rgb, data, positions)
        return jsonify(success=True, filename=fname)
    except Exception as e:
        logger.error(f"Error saving DICOM: {e}")
        return jsonify(success=False, error=str(e))

# Temi Routes
@app.route('/temi/info')
def temi_info():
    info = temi_controller.get_info()
    return jsonify(info)

@app.route('/temi/tts', methods=['POST'])
def temi_tts_route():
    if not temi_controller.available:
        return jsonify(success=False, error="Temi not available")
    text = request.json.get('text', '')
    if not text:
        return jsonify(success=False, error="No text provided")
    try:
        temi_controller.tts(text)
        return jsonify(success=True)
    except Exception as e:
        logger.error(f"Error in Temi TTS: {e}")
        return jsonify(success=False, error=str(e))

@app.route('/temi/goto', methods=['POST'])
def temi_goto_route():
    if not temi_controller.available:
        return jsonify(success=False, error="Temi not available")
    loc = request.json.get('location', '')
    if not loc:
        return jsonify(success=False, error="No location provided")
    try:
        temi_controller.goto(loc)
        return jsonify(success=True)
    except Exception as e:
        logger.error(f"Error in Temi goto: {e}")
        return jsonify(success=False, error=str(e))

@app.route('/temi/rotate', methods=['POST'])
def temi_rotate_route():
    if not temi_controller.available:
        return jsonify(success=False, error="Temi not available")
    angle = request.json.get('angle', 0)
    try:
        temi_controller.rotate(int(angle))
        return jsonify(success=True)
    except Exception as e:
        logger.error(f"Error in Temi rotate: {e}")
        return jsonify(success=False, error=str(e))

if __name__ == '__main__':
    try:
        logger.info("Starting Flask app...")
        app.run(host=HOST, port=PORT, debug=DEBUG)
    finally:
        logger.info("Shutting down...")
        motor_controller.stop()
        camera.release()