from evdev import UInput, ecodes as e
from sam import SAM, ButtonType
import time

# Create virtual keyboard device
ui = UInput(name="virtual-keyboard")


# Define callbacks for each button
def on_up_press():
    print(f"{time.time()}: UP button pressed")
    ui.write(e.EV_KEY, e.KEY_UP, 1)
    ui.write(e.EV_KEY, e.KEY_UP, 0)
    ui.syn()



def on_down_press():
    print(f"{time.time()}: DOWN button pressed")
    ui.write(e.EV_KEY, e.KEY_DOWN, 1)
    ui.write(e.EV_KEY, e.KEY_DOWN, 0)
    ui.syn()


def on_select_press():
    print(f"{time.time()}: SELECT button pressed")
    ui.write(e.EV_KEY, e.KEY_ENTER, 1)
    ui.write(e.EV_KEY, e.KEY_ENTER, 0)
    ui.syn()


# Initialize and connect to SAM
sam = SAM()
if sam.connect():
    # Register callbacks
    sam.register_button_press_callback(ButtonType.UP, on_up_press)
    sam.register_button_press_callback(ButtonType.DOWN, on_down_press)
    sam.register_button_press_callback(ButtonType.SELECT, on_select_press)
    
    # Keep the script running
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        sam.disconnect()
        ui.close()
        print("SAM button test terminated")
else:
    print("Failed to connect to SAM")
    ui.close() 