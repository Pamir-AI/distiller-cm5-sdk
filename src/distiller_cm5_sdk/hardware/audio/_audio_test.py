import time

from audio import Audio

print("Testing static methods:")
print(f"Current mic gain: {Audio.get_mic_gain_static()}")
print(f"Current speaker volume: {Audio.get_speaker_volume_static()}")

# Set values using static methods
Audio.set_mic_gain_static(70)
Audio.set_speaker_volume_static(75)
print(
    f"After static update - mic gain: {Audio.get_mic_gain_static()}, speaker volume: {Audio.get_speaker_volume_static()}"
)

print("\nTesting instance methods:")
audio = Audio(auto_check_config=True)

if audio.check_system_config():
    print("System config is good")
else:
    print("System config is Not Configured")


audio.play("test_audio.wav")
audio.set_speaker_volume(60)
print(f"Speaker volume: {audio.get_speaker_volume()}")
time.sleep(5)
audio.stop_playback()

audio.record("test_recording.wav", duration=None)
time.sleep(5)
audio.stop_recording()
audio.play("test_recording.wav")
time.sleep(5)
audio.stop_playback()

audio.close()
