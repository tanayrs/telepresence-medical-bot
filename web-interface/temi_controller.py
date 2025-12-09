import logging

logger = logging.getLogger(__name__)

class TemiController:
    def __init__(self, mqtt_host, mqtt_port, temi_serial):
        self.available = False
        self.robot = None
        try:
            import pytemi as temi
            logger.info(f"Connecting to Temi at {mqtt_host}...")
            mqtt_client = temi.connect(mqtt_host, mqtt_port)
            self.robot = temi.Robot(mqtt_client, temi_serial)
            self.available = True
            logger.info("Temi connected successfully")
        except Exception as e:
            logger.warning(f"Temi Connection Failed: {e}")
            logger.warning("Running without Robot features.")

    def get_info(self):
        if not self.available or self.robot is None:
            return {'available': False, 'locations': [], 'current_location': 'Unknown'}

        try:
            locs = self.robot.locations
            curr = getattr(self.robot, 'current_location', 'Unknown')
        except Exception as e:
            logger.error(f"Error getting Temi info: {e}")
            locs = []
            curr = 'Error'

        return {'available': True, 'locations': locs, 'current_location': curr}

    def tts(self, text):
        if not self.available:
            raise ValueError("Temi not available")
        self.robot.tts(text)

    def goto(self, location):
        if not self.available:
            raise ValueError("Temi not available")
        self.robot.goto(location)

    def rotate(self, angle):
        if not self.available:
            raise ValueError("Temi not available")
        self.robot.rotate(angle)

    def joystick(self, x, y):
        """Send joystick command to temi. x and y should be floats in [-1, 1]."""
        if not self.available:
            raise ValueError("Temi not available")
        try:
            # forward to robot joystick
            self.robot.joystick(float(x), float(y))
        except Exception as e:
            logger.error(f"Error sending joystick command: {e}")
            raise

    def stop(self):
        """Stop robot movement (proxy)."""
        if not self.available:
            raise ValueError("Temi not available")
        try:
            self.robot.stop()
        except Exception as e:
            logger.error(f"Error stopping temi: {e}")
            raise