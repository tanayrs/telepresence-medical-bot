import cv2
from flask import Flask, Response, render_template_string

# Initialize Flask app
app = Flask(__name__)

# Initialize the camera
# 0 usually maps to /dev/video0. If you have multiple cameras, change this to 1 or 2.
camera = cv2.VideoCapture(0)

# Set camera resolution (optional, adjust as needed for performance)
camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

def generate_frames():
    """
    Generator function that reads frames from the camera, 
    encodes them to JPEG, and yields them as a byte stream.
    """
    while True:
        success, frame = camera.read()
        if not success:
            break
        else:
            # Encode the frame in JPEG format
            # Quality 70 is a good balance between speed and quality
            ret, buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 70])
            frame = buffer.tobytes()
            
            # Yield the frame in the specific MJPEG format
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

@app.route('/')
def index():
    """
    Root URL - serves a simple HTML page with the video stream embedded.
    """
    # Simple inline HTML to display the video feed centered on the screen
    html_template = """
    <html>
        <head>
            <title>RPi Camera Stream</title>
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <style>
                body { background-color: #1a1a1a; color: white; text-align: center; font-family: sans-serif; }
                h1 { margin-top: 20px; }
                img { border: 5px solid #444; border-radius: 8px; max-width: 100%; height: auto; }
                .footer { margin-top: 20px; color: #888; font-size: 0.9em; }
            </style>
        </head>
        <body>
            <h1>Live Camera Feed</h1>
            <img src="{{ url_for('video_feed') }}">
            <div class="footer">Streaming from Raspberry Pi</div>
        </body>
    </html>
    """
    return render_template_string(html_template)

@app.route('/video_feed')
def video_feed():
    """
    Route that streams the video frames.
    """
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

if __name__ == '__main__':
    # host='0.0.0.0' allows access from other computers on the network
    # debug=False prevents the camera from trying to initialize twice
    print("Starting server... Access at http://<YOUR_PI_IP>:5000")
    app.run(host='0.0.0.0', port=5000, debug=False)
