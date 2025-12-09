import cv2
import time
import threading
import logging
import numpy as np
from flask import Flask, Response, render_template, request, jsonify

from config import (
    MOTOR_PINS, STEPS_PER_REV_M1, STEPS_PER_REV_M2, MICROSTEPPING, 
    DEG_PER_STEP_M1, DEG_PER_STEP_M2, STEP_DELAY,
    MQTT_HOST, MQTT_PORT, TEMI_SERIAL, STORAGE_FOLDER, HOST, PORT, DEBUG
)
from motor_controller import MotorController
from dicom_handler import DICOMHandler
from temi_controller import TemiController

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Initialize components
motor_controller = MotorController(MOTOR_PINS, DEG_PER_STEP_M1, DEG_PER_STEP_M2, STEP_DELAY)
dicom_handler = DICOMHandler(STORAGE_FOLDER)
temi_controller = TemiController(MQTT_HOST, MQTT_PORT, TEMI_SERIAL)

# Flask App
app = Flask(__name__)
camera = cv2.VideoCapture(0)
global_frame = None
frame_lock = threading.Lock()
detection_enabled = False  # Toggle for face tracking
anomaly_detection_enabled = False  # Toggle for skin anomaly detection
detection_mode = 'haar_balanced'  # Options: 'haar_fast', 'haar_balanced', 'haar_accurate'
detection_interval = 3  # Process face detection every N frames to reduce latency
frame_counter = 0
last_faces = []
last_anomalies = []

# Load DNN model for face detection (if available)
# Download model files from:
# https://raw.githubusercontent.com/opencv/opencv/master/samples/dnn/face_detector/deploy.prototxt
# https://github.com/opencv/opencv_3rdparty/raw/dnn_samples_face_detector_20170830/res10_300x300_ssd_iter_140000.caffemodel
# Note: DNN and LBP modes removed, keeping only Haar cascades for simplicity
dnn_available = False
face_net = None

def detect_faces(frame, mode='haar_balanced'):
    try:
        # Convert to grayscale for cascade methods
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        face_rects = []
        
        if mode.startswith('haar'):
            # Haar cascade detection
            try:
                face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
                if face_cascade.empty():
                    return []
            except:
                return []
            
            # Parameters based on mode
            if mode == 'haar_fast':
                scaleFactor = 1.3
                minNeighbors = 3
                minSize = (20, 20)
            elif mode == 'haar_balanced':
                scaleFactor = 1.1
                minNeighbors = 5
                minSize = (30, 30)
            elif mode == 'haar_accurate':
                scaleFactor = 1.05
                minNeighbors = 7
                minSize = (40, 40)
            else:
                scaleFactor = 1.1
                minNeighbors = 5
                minSize = (30, 30)
            
            faces = face_cascade.detectMultiScale(gray, scaleFactor=scaleFactor, minNeighbors=minNeighbors, minSize=minSize)
            for (x, y, w, h) in faces:
                face_rects.append((x, y, w, h))
        
        
        
        return face_rects
    except Exception as e:
        logger.error(f"Error in face detection: {e}")
        return []

def detect_skin_anomalies(face_roi):
    """
    Detect small white patches (electrical tape).
    Uses color segmentation in HSV space.
    Returns list of (center_x, center_y, radius) for detected anomalies.
    """
    try:
        if face_roi.size == 0:
            return []
        
        hsv = cv2.cvtColor(face_roi, cv2.COLOR_BGR2HSV)
        
        # White patch mask: stricter thresholds to avoid spurious detections
        white_mask = cv2.inRange(hsv, (0, 0, 200), (180, 50, 255))
        
        # Clean mask with morphological operations
        kernel = np.ones((3,3), np.uint8)
        white_mask = cv2.morphologyEx(white_mask, cv2.MORPH_OPEN, kernel)
        
        # Find white patch contours
        contours, _ = cv2.findContours(white_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        anomalies = []
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < 100 or area > 1000:  # Increased min area
                continue
            
            # Filter by circularity to prefer round/compact shapes
            perimeter = cv2.arcLength(cnt, True)
            if perimeter == 0:
                continue
            circularity = 4 * np.pi * area / (perimeter * perimeter)
            if circularity < 0.5:  # Not too elongated
                continue
            
            # Get bounding circle
            (x, y), radius = cv2.minEnclosingCircle(cnt)
            center = (int(x), int(y))
            radius = int(radius)
            
            anomalies.append((center[0], center[1], radius, area))
        
        # Sort by area descending and take top 3
        anomalies = sorted(anomalies, key=lambda x: x[3], reverse=True)[:3]
        # Remove area from tuple
        anomalies = [(x, y, r) for x, y, r, a in anomalies]
        
        logger.info(f"Image size: {face_roi.shape}, White contours: {len(contours)}, Anomalies: {len(anomalies)}")
        return anomalies
    except Exception as e:
        logger.error(f"Error in anomaly detection: {e}")
        return []

def generate_frames():
    global global_frame, frame_counter, last_faces
    while True:
        success, frame = camera.read()
        if not success:
            break

        processed_frame = frame.copy()

        frame_counter += 1

        if detection_enabled:
            interval = detection_interval
            if frame_counter % interval == 0:
                last_faces = detect_faces(frame, detection_mode)
            # Use last_faces for drawing
            label = 'Face'
            for (x, y, w, h) in last_faces:
                cv2.rectangle(processed_frame, (x, y), (x+w, y+h), (0, 255, 0), 2)
                cv2.putText(processed_frame, label, (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
        
        # Anomaly detection on entire frame
        if anomaly_detection_enabled:
            if frame_counter % detection_interval == 0:
                last_anomalies = detect_skin_anomalies(frame)
                logger.info(f"Frame {frame_counter}: Detected {len(last_anomalies)} anomalies")
        
        # Draw last anomalies every frame if enabled
        if anomaly_detection_enabled:
            for (cx, cy, r) in last_anomalies:
                top_left = (cx - r, cy - r)
                bottom_right = (cx + r, cy + r)
                cv2.rectangle(processed_frame, top_left, bottom_right, (0, 0, 255), 3)

        with frame_lock:
            global_frame = processed_frame.copy()

        ret, buffer = cv2.imencode('.jpg', processed_frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
        yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/toggle_detection')
def toggle_detection():
    global detection_enabled
    detection_enabled = not detection_enabled
    return jsonify(enabled=detection_enabled)

@app.route('/toggle_anomaly_detection')
def toggle_anomaly_detection():
    global anomaly_detection_enabled
    anomaly_detection_enabled = not anomaly_detection_enabled
    return jsonify(enabled=anomaly_detection_enabled)

@app.route('/set_detection_mode', methods=['POST'])
def set_detection_mode():
    global detection_mode
    data = request.json
    mode = data.get('mode', 'haar_balanced')
    valid_modes = ['haar_fast', 'haar_balanced', 'haar_accurate']
    if mode in valid_modes:
        detection_mode = mode
        return jsonify(success=True, mode=mode)
    return jsonify(success=False, error="Invalid mode")

@app.route('/control/<motor>/<direction>')
def control_motor(motor, direction):
    steps = 50 if motor == 'm1' else 20
    motor_controller.move_motor(motor, direction, steps)
    return jsonify(success=True)

@app.route('/set_angle', methods=['POST'])
def set_angle():
    data = request.json
    motor = data.get('motor')
    angle = data.get('angle', 0)
    if motor not in ['m1', 'm2']:
        return jsonify(success=False, error="Invalid motor")
    try:
        motor_controller.set_target_angle(motor, float(angle))
        return jsonify(success=True)
    except Exception as e:
        logger.error(f"Error setting angle: {e}")
        return jsonify(success=False, error=str(e))

@app.route('/reset_angles')
def reset_angles():
    try:
        motor_controller.reset_angles()
        return jsonify(success=True)
    except Exception as e:
        logger.error(f"Error resetting angles: {e}")
        return jsonify(success=False, error=str(e))

@app.route('/tare_position')
def tare_position():
    try:
        motor_controller.tare_position()
        return jsonify(success=True)
    except Exception as e:
        logger.error(f"Error taring position: {e}")
        return jsonify(success=False, error=str(e))

@app.route('/emergency_stop')
def emergency_stop():
    try:
        motor_controller.emergency_stop()
        return jsonify(success=True)
    except Exception as e:
        logger.error(f"Error emergency stop: {e}")
        return jsonify(success=False, error=str(e))

@app.route('/get_angles')
def get_angles():
    try:
        positions = motor_controller.get_positions()
        targets = motor_controller.get_targets()
        return jsonify(current={'m1': positions['m1'], 'm2': positions['m2']}, target={'m1': targets['m1'], 'm2': targets['m2']})
    except Exception as e:
        logger.error(f"Error getting angles: {e}")
        return jsonify(error=str(e))

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


@app.route('/temi/joystick', methods=['POST'])
def temi_joystick_route():
    if not temi_controller.available:
        return jsonify(success=False, error="Temi not available")
    data = request.json or {}
    try:
        x = float(data.get('x', 0))
        y = float(data.get('y', 0))
    except Exception:
        return jsonify(success=False, error="Invalid x/y")
    try:
        # Clamp values to [-1, 1]
        x = max(-1.0, min(1.0, x))
        y = max(-1.0, min(1.0, y))
        temi_controller.joystick(x, y)
        return jsonify(success=True)
    except Exception as e:
        logger.error(f"Error sending joystick command: {e}")
        return jsonify(success=False, error=str(e))


@app.route('/temi/joystick_stop', methods=['POST'])
def temi_joystick_stop_route():
    if not temi_controller.available:
        return jsonify(success=False, error="Temi not available")
    try:
        temi_controller.stop()
        return jsonify(success=True)
    except Exception as e:
        logger.error(f"Error stopping temi: {e}")
        return jsonify(success=False, error=str(e))

if __name__ == '__main__':
    try:
        logger.info("Starting Flask app...")
        app.run(host=HOST, port=PORT, debug=DEBUG)
    finally:
        logger.info("Shutting down...")
        motor_controller.stop()
        camera.release()
