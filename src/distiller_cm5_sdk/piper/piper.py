import subprocess
import os
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("Piper")


class Piper:
    def __init__(self, model_path=os.path.join(os.path.dirname(__file__), "models"),
                 piper_path=os.path.join(os.path.dirname(__file__), "piper")):
        logger.info("Piper: Initializing Piper")
        self.model_path = model_path
        self.piper_path = piper_path
        self.voice_onnx = os.path.join(self.model_path, "en_US-amy-medium.onnx")
        self.voice_json = os.path.join(self.model_path, "en_US-amy-medium.onnx.json")
        self.piper = os.path.join(self.piper_path, "piper")

        # Check if the model file exists
        if not os.path.exists(self.voice_onnx):
            logger.error(f"Piper: Model onnx file does not exist: {self.voice_onnx}")
            raise ValueError(f"Piper: Model onnx file does not exist: {self.voice_onnx}")
        if not os.path.exists(self.voice_json):
            logger.error(f"Piper: Model json file does not exist: {self.voice_json}")
            raise ValueError(f"Piper: Model json file does not exist: {self.voice_json}")
        if not os.path.exists(self.piper_path):
            logger.error(f"Piper: piper does not exist: {self.piper}")
            raise ValueError(f"Piper: piper does not exist: {self.piper}")

        logger.info("Piper: Piper initialized")

    def get_wav_file_path(self, text):
        output_file_path = os.path.join(os.getcwd(), "output.wav")
        escaped_text = text.replace("'", "'\\''")
        command = f"""echo '{escaped_text}' | {self.piper} --model {self.voice_onnx} --config {self.voice_json} --output_file {output_file_path}"""
        logger.info(f"Piper exec command: {command}")
        try:
            subprocess.run(command, shell=True, check=True, text=True, capture_output=True)
            logger.info(f"Piper: Text '{text}' spoken successfully and saved to {output_file_path}")
            return output_file_path
        except subprocess.CalledProcessError as e:
            logger.error(f"Piper: Error running piper command: {e.stderr}")
            raise ValueError(f"Piper: Error running piper command: {e.stderr}")

    def speak_stream(self, text, volume=50):
        if volume < 0 or volume > 100:
            logger.warning("Piper: The volume level is not within the range of 0-100.")
            raise ValueError("Piper: The volume level is not within the range of 0-100.")
        volume = volume / 100
        # Escape single quotes in text to prevent shell syntax errors
        escaped_text = text.replace("'", "'\\''")
        command = f"""echo '{escaped_text}' | sudo {self.piper} --model {self.voice_onnx} --config {self.voice_json} --output-raw | aplay -D plughw:1 -r 22050 -f S16_LE -t raw -V {volume}"""
        logger.info(f"Piper: Piper exec command {command}")
        try:
            subprocess.run(command, shell=True, check=True)
            logger.info(f"Piper: Text '{text}' streamed successfully")
        except subprocess.CalledProcessError as e:
            logger.error(f"Piper: Error streaming audio: {str(e)}")
            raise ValueError(f"Piper: Error streaming audio: {str(e)}")


if __name__ == '__main__':
    piper = Piper()
    text_t = "Hello, this is a test."
    output_file_path_t = piper.get_wav_file_path(text_t)
    print("output_file_path:",output_file_path_t)
    piper.speak_stream(text_t, 10)