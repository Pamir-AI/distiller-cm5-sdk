import os


def get_model_path(module_name):
    """
    Get the correct model path for a given module.

    Args:
        module_name (str): Name of the module (e.g., 'whisper', 'parakeet', 'piper')

    Returns:
        str: Path to the models directory
    """
    # First check if we're in a Debian package installation
    debian_path = f"/opt/distiller-cm5-sdk/models/{module_name}"
    if os.path.exists(debian_path):
        return debian_path

    # Fall back to relative path for development
    return os.path.join(os.path.dirname(__file__), module_name, "models")

def get_library_path():
    """
    Get the correct library path for native libraries.

    Returns:
        str: Path to the library directory
    """
    # First check if we're in a Debian package installation
    debian_path = "/opt/distiller-cm5-sdk/lib"
    if os.path.exists(debian_path):
        return debian_path

    # Fall back to relative path for development
    return os.path.join(os.path.dirname(__file__), "hardware", "eink", "lib")
