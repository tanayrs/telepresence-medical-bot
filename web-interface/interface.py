import cv2
import time
import threading
from flask import Flask, Response, render_template_string, request, jsonify

# --- GPIO CONFIGURATION ---
try:
    import RPi.GPIO as GPIO
    GPIO_AVAILABLE = True
except ImportError:
    print("RPi.GPIO not found. Running in simulation mode for motors.")
    GPIO_AVAILABLE = False

# Motor 1 pins
EN1   = 21
DIR1  = 20
STEP1 = 16

# Motor 2 pins
EN2   = 26
DIR2  = 14
STEP2 = 15

STEP_DELAY = 0.001

# Global state to share between Web Server and Motor Thread
motor_state = {
    'm1_pending': 0,
    'm2_pending': 0,
    'running': True  # To stop the thread gracefully
}

def setup_gpio():
    if not GPIO_AVAILABLE: return
    
    GPIO.setmode(GPIO.BCM)
    pins = [EN1, DIR1, STEP1, EN2, DIR2, STEP2]
    for pin in pins:
        GPIO.setup(pin, GPIO.OUT)
    
    # Enable motors (Based on your code: HIGH = Enabled)
    GPIO.output(EN1, GPIO.HIGH)
    GPIO.output(EN2, GPIO.HIGH)

def step_motor(step_pin):
    if not GPIO_AVAILABLE:
        time.sleep(STEP_DELAY * 2) # Simulate delay
        return

    GPIO.output(step_pin, GPIO.HIGH)
    time.sleep(STEP_DELAY)
    GPIO.output(step_pin, GPIO.LOW)
    time.sleep(STEP_DELAY)

def set_direction(dir_pin, direction):
    if not GPIO_AVAILABLE: return
    # direction > 0 = forward, direction < 0 = reverse
    GPIO.output(dir_pin, GPIO.HIGH if direction > 0 else GPIO.LOW)

def motor_control_loop():
    """
    Background thread that constantly checks if steps need to be taken.
    Replaces the 'while True' loop from your curses code.
    """
    print("Motor control thread started...")
    while motor_state['running']:
        moved = False
        
        # --- Motor 1 Logic ---
        if motor_state['m1_pending'] != 0:
            direction = 1 if motor_state['m1_pending'] > 0 else -1
            set_direction(DIR1, direction)
            step_motor(STEP1)
            motor_state['m1_pending'] -= direction
            moved = True

        # --- Motor 2 Logic ---
        if motor_state['m2_pending'] != 0:
            direction = 1 if motor_state['m2_pending'] > 0 else -1
            set_direction(DIR2, direction)
            step_motor(STEP2)
            motor_state['m2_pending'] -= direction
            moved = True

        # If no motors moved, sleep a tiny bit to save CPU
        if not moved:
            time.sleep(0.01)

# --- FLASK APP ---
app = Flask(__name__)

# Initialize Camera
camera = cv2.VideoCapture(0)
camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

def generate_frames():
    while True:
        success, frame = camera.read()
        if not success:
            break
        else:
            ret, buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 70])
            frame = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

@app.route('/')
def index():
    html_template = """
    <html>
        <head>
            <title>RPi Bot Control</title>
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <style>
                body { background-color: #1a1a1a; color: white; text-align: center; font-family: sans-serif; user-select: none; }
                h1 { margin-top: 10px; font-size: 1.5rem; }
                .container { display: flex; flex-direction: column; align-items: center; }
                img { border: 4px solid #444; border-radius: 8px; max-width: 90%; height: auto; }
                
                .controls { margin-top: 20px; display: grid; grid-template-columns: 1fr 1fr; gap: 20px; max-width: 600px; width: 100%; }
                .control-group { background: #333; padding: 15px; border-radius: 10px; }
                .btn { 
                    background-color: #007bff; color: white; border: none; padding: 15px 30px; 
                    font-size: 1.2rem; border-radius: 5px; margin: 5px; cursor: pointer; touch-action: manipulation;
                }
                .btn:active { background-color: #0056b3; transform: translateY(2px); }
                .status { margin-top: 10px; font-size: 0.9em; color: #aaa; }
                
                /* Mobile optimized layout */
                @media (max-width: 600px) {
                    .controls { grid-template-columns: 1fr; }
                }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>Bot Control</h1>
                <img src="{{ url_for('video_feed') }}">
                
                <div class="controls">
                    <div class="control-group">
                        <h3>Motor 1 (W/S)</h3>
                        <button class="btn" onmousedown="sendCommand('m1', 'forward')" ontouchstart="sendCommand('m1', 'forward')">Extend</button>
                        <br>
                        <button class="btn" onmousedown="sendCommand('m1', 'backward')" ontouchstart="sendCommand('m1', 'backward')">Retract</button>
                    </div>
                    
                    <div class="control-group">
                        <h3>Motor 2 (Up/Down)</h3>
                        <button class="btn" onmousedown="sendCommand('m2', 'backward')" ontouchstart="sendCommand('m2', 'backward')">Up</button>
                        <br>
                        <button class="btn" onmousedown="sendCommand('m2', 'forward')" ontouchstart="sendCommand('m2', 'forward')">Down</button>
                    </div>
                </div>
                <div class="status" id="status-log">Ready</div>
            </div>

            <script>
                // Function to send commands to Python
                function sendCommand(motor, direction) {
                    fetch(`/control/${motor}/${direction}`)
                        .then(response => response.json())
                        .then(data => {
                            document.getElementById('status-log').innerText = `${motor} moving ${direction}`;
                        });
                }

                // Keyboard Controls
                document.addEventListener('keydown', function(event) {
                    if (event.repeat) return; // Prevent spamming on hold if desired, or remove to allow hold

                    switch(event.key.toLowerCase()) {
                        case 'w': sendCommand('m1', 'forward'); break;
                        case 's': sendCommand('m1', 'backward'); break;
                        case 'arrowup': sendCommand('m2', 'forward'); break;
                        case 'arrowdown': sendCommand('m2', 'backward'); break;
                    }
                });
            </script>
        </body>
    </html>
    """
    return render_template_string(html_template)

@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/control/<motor>/<direction>')
def control_motor(motor, direction):
    steps = 50 # Number of steps to add per click/keypress
    
    if motor == 'm1':
        if direction == 'forward':
            motor_state['m1_pending'] += steps
        elif direction == 'backward':
            motor_state['m1_pending'] -= steps
    elif motor == 'm2':
        # Adjust steps for M2 if needed (your original code used 20 for M2)
        steps_m2 = 20
        if direction == 'forward':
            motor_state['m2_pending'] += steps_m2
        elif direction == 'backward':
            motor_state['m2_pending'] -= steps_m2
            
    return jsonify(success=True, state=motor_state)

if __name__ == '__main__':
    print("Setting up GPIO...")
    setup_gpio()

    # Start the motor control thread
    motor_thread = threading.Thread(target=motor_control_loop)
    motor_thread.start()

    try:
        print("Starting web server at http://<YOUR_PI_IP>:5000")
        app.run(host='0.0.0.0', port=5000, debug=False)
    finally:
        print("Cleaning up...")
        motor_state['running'] = False # Stop thread
        motor_thread.join()
        if GPIO_AVAILABLE:
            GPIO.cleanup()
