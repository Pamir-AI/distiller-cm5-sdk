#!/usr/bin/env python3
"""E-ink composer CLI."""

import argparse
import json
import sys
from pathlib import Path

from .core import EinkComposer
from .templates import TemplateRenderer

try:
    from .. import Display, DisplayMode

    HARDWARE_AVAILABLE = True
except ImportError:
    HARDWARE_AVAILABLE = False
    Display = None
    DisplayMode = None


class ComposerSession:
    def __init__(self):
        self.session_file = Path.home() / ".eink_compose.json"
        self.composer = None
        self.load_session()

    def load_session(self):
        if self.session_file.exists():
            try:
                with open(self.session_file) as f:
                    data = json.load(f)
                self.composer = EinkComposer(data["width"], data["height"])
                for layer_data in data.get("layers", []):
                    self._restore_layer(layer_data)
            except Exception as e:
                print(f"Warning: Could not load session: {e}", file=sys.stderr)
                self.composer = None

    def save_session(self):
        if self.composer:
            data = {
                "width": self.composer.width,
                "height": self.composer.height,
                "layers": self.composer.get_layer_info(),
            }
            with open(self.session_file, "w") as f:
                json.dump(data, f)

    def ensure_composer(self):
        if not self.composer:
            print("No composition found. Creating default 128x250...", file=sys.stderr)
            self.composer = EinkComposer(128, 250)
            self.save_session()

    def _restore_layer(self, layer_data):
        layer_type = layer_data.get("type")
        layer_id = layer_data.get("id", "unknown")

        try:
            if layer_type == "text":
                self.composer.add_text_layer(
                    layer_id=layer_id,
                    text=layer_data.get("text", ""),
                    x=layer_data.get("x", 0),
                    y=layer_data.get("y", 0),
                    color=layer_data.get("color", 0),
                    font_size=layer_data.get("font_size", 1),
                )
            elif layer_type == "rectangle":
                self.composer.add_rectangle_layer(
                    layer_id=layer_id,
                    x=layer_data.get("x", 0),
                    y=layer_data.get("y", 0),
                    width=layer_data.get("width", 10),
                    height=layer_data.get("height", 10),
                    filled=layer_data.get("filled", True),
                    color=layer_data.get("color", 0),
                )
            elif layer_type == "image":
                image_path = layer_data.get("image_path")
                if image_path and Path(image_path).exists():
                    self.composer.add_image_layer(
                        layer_id=layer_id,
                        image_path=image_path,
                        x=layer_data.get("x", 0),
                        y=layer_data.get("y", 0),
                    )

            if not layer_data.get("visible", True):
                self.composer.toggle_layer(layer_id)

        except Exception as e:
            print(f"Warning: Could not restore layer {layer_id}: {e}", file=sys.stderr)


def create_parser():
    parser = argparse.ArgumentParser(
        description="E-ink display image composer - Create layered templates for e-ink displays",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    eink-compose create --size 128x250
  eink-compose add-text hello "HELLO E-INK" --x 20 --y 120
  eink-compose add-rect border --width 128 --height 250 --filled false
  eink-compose display

    eink-compose create --size 128x250
  eink-compose add-rect bg --width 128 --height 250 --filled true --color 255
  eink-compose add-text title "E-INK DISPLAY" --x 15 --y 50
  eink-compose add-text info "128 x 250 px" --x 25 --y 70
  eink-compose display --save-preview preview.png

    eink-compose render --output display.png --format png
  eink-compose render --output display.bin --format binary

    eink-compose save my_template.json
  eink-compose load my_template.json""",
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Create command
    create_parser = subparsers.add_parser("create", help="Create a new composition")
    create_parser.add_argument("--size", default="128x250", help="Canvas size WIDTHxHEIGHT")
    create_parser.add_argument("--output", help="Save immediately to file")

    # Add image command
    add_image_parser = subparsers.add_parser("add-image", help="Add an image layer")
    add_image_parser.add_argument("layer_id", help="Layer identifier")
    add_image_parser.add_argument("image_path", help="Path to image file")
    add_image_parser.add_argument("--x", type=int, default=0, help="X position")
    add_image_parser.add_argument("--y", type=int, default=0, help="Y position")
    add_image_parser.add_argument("--width", type=int, help="Target width")
    add_image_parser.add_argument("--height", type=int, help="Target height")
    add_image_parser.add_argument(
        "--resize-mode", choices=["stretch", "fit", "crop"], default="fit"
    )
    add_image_parser.add_argument(
        "--dither", choices=["floyd-steinberg", "threshold", "none"], default="floyd-steinberg"
    )
    add_image_parser.add_argument("--brightness", type=float, default=1.0)
    add_image_parser.add_argument("--contrast", type=float, default=0.0)
    add_image_parser.add_argument("--rotate", type=int, default=0, choices=[0, 90, 180, 270])
    add_image_parser.add_argument("--flip-h", action="store_true")
    add_image_parser.add_argument("--flip-v", action="store_true")
    add_image_parser.add_argument("--crop-x", type=int)
    add_image_parser.add_argument("--crop-y", type=int)

    # Add text command
    add_text_parser = subparsers.add_parser("add-text", help="Add a text layer")
    add_text_parser.add_argument("layer_id", help="Layer identifier")
    add_text_parser.add_argument("text", help="Text to display")
    add_text_parser.add_argument("--x", type=int, default=0, help="X position")
    add_text_parser.add_argument("--y", type=int, default=0, help="Y position")
    add_text_parser.add_argument(
        "--color", type=int, default=0, help="Text color (0=black, 255=white)"
    )
    add_text_parser.add_argument("--font-size", type=int, default=1, help="Font scale factor")
    add_text_parser.add_argument("--rotate", type=int, default=0, choices=[0, 90, 180, 270])
    add_text_parser.add_argument("--flip-h", action="store_true")
    add_text_parser.add_argument("--flip-v", action="store_true")
    add_text_parser.add_argument("--background", action="store_true", help="Draw background")
    add_text_parser.add_argument("--padding", type=int, default=2, help="Background padding")

    # Add rectangle command
    add_rect_parser = subparsers.add_parser("add-rect", help="Add a rectangle layer")
    add_rect_parser.add_argument("layer_id", help="Layer identifier")
    add_rect_parser.add_argument("--x", type=int, default=0, help="X position")
    add_rect_parser.add_argument("--y", type=int, default=0, help="Y position")
    add_rect_parser.add_argument("--width", type=int, default=10, help="Rectangle width")
    add_rect_parser.add_argument("--height", type=int, default=10, help="Rectangle height")
    add_rect_parser.add_argument(
        "--filled", type=lambda x: x.lower() in ["true", "1", "yes"], default=True
    )
    add_rect_parser.add_argument(
        "--color", type=int, default=0, help="Fill color (0=black, 255=white)"
    )
    add_rect_parser.add_argument("--border-width", type=int, default=1)

    # Remove command
    remove_parser = subparsers.add_parser("remove", help="Remove a layer")
    remove_parser.add_argument("layer_id", help="Layer identifier to remove")

    # Toggle command
    toggle_parser = subparsers.add_parser("toggle", help="Toggle layer visibility")
    toggle_parser.add_argument("layer_id", help="Layer identifier to toggle")

    # Reset command
    reset_parser = subparsers.add_parser("reset", help="Reset composition")
    reset_parser.add_argument("--size", default="128x250", help="Canvas size WIDTHxHEIGHT")

    # List command
    subparsers.add_parser("list", help="List all layers")

    # Render command
    render_parser = subparsers.add_parser("render", help="Render composition to file")
    render_parser.add_argument("--output", required=True, help="Output file path")
    render_parser.add_argument("--format", choices=["png", "binary"], default="png")

    # Save command
    save_parser = subparsers.add_parser("save", help="Save composition to JSON")
    save_parser.add_argument("filename", help="Output JSON file")

    # Load command
    load_parser = subparsers.add_parser("load", help="Load composition from JSON")
    load_parser.add_argument("filename", help="Input JSON file")
    load_parser.add_argument("--render", action="store_true", help="Render immediately")
    load_parser.add_argument("--output", help="Output file for rendering")
    load_parser.add_argument("--format", choices=["png", "binary"], default="png")

    # Display command
    display_parser = subparsers.add_parser("display", help="Display on e-ink hardware")
    display_parser.add_argument("--partial", action="store_true", help="Use partial refresh")
    display_parser.add_argument("--clear", action="store_true", help="Clear display first")
    display_parser.add_argument("--save-preview", help="Save preview image")
    display_parser.add_argument("--rotate", type=int, default=0, choices=[0, 90, 180, 270])
    display_parser.add_argument("--flip-h", action="store_true")
    display_parser.add_argument("--flip-v", action="store_true")

    # Hardware command
    hardware_parser = subparsers.add_parser("hardware", help="Hardware control commands")
    hardware_parser.add_argument(
        "hw_command", choices=["info", "clear", "sleep"], help="Hardware command"
    )

    # Template command
    template_parser = subparsers.add_parser("template", help="Render and display templates")
    template_parser.add_argument("template_path", help="Path to template JSON file")
    template_parser.add_argument("--ip", help="IP address for placeholder")
    template_parser.add_argument("--url", help="URL for QR code placeholder")
    template_parser.add_argument("--output", help="Save rendered template to file")
    template_parser.add_argument("--display", action="store_true", help="Display on hardware")

    return parser


def main():
    """Main CLI entry point."""
    parser = create_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    session = ComposerSession()

    if args.command == "create":
        try:
            width, height = map(int, args.size.split("x"))
        except ValueError:
            print(f"Error: Invalid size format '{args.size}'. Use WIDTHxHEIGHT", file=sys.stderr)
            sys.exit(1)

        session.composer = EinkComposer(width, height)
        session.save_session()
        print(f"Created new {width}x{height} composition")

        if args.output:
            session.composer.save(args.output)
            print(f"Saved to {args.output}")

    elif args.command == "add-image":
        session.ensure_composer()

        session.composer.add_image_layer(
            layer_id=args.layer_id,
            image_path=args.image_path,
            x=args.x,
            y=args.y,
            resize_mode=args.resize_mode,
            dither_mode=args.dither,
            brightness=args.brightness,
            contrast=args.contrast,
            rotate=args.rotate,
            flip_h=args.flip_h,
            flip_v=args.flip_v,
            crop_x=args.crop_x,
            crop_y=args.crop_y,
            width=args.width,
            height=args.height,
        )
        session.save_session()
        print(f"Added image layer '{args.layer_id}'")

    elif args.command == "add-text":
        session.ensure_composer()

        session.composer.add_text_layer(
            layer_id=args.layer_id,
            text=args.text,
            x=args.x,
            y=args.y,
            color=args.color,
            rotate=args.rotate,
            flip_h=args.flip_h,
            flip_v=args.flip_v,
            font_size=args.font_size,
            background=args.background,
            padding=args.padding,
        )
        session.save_session()
        print(f"Added text layer '{args.layer_id}'")

    elif args.command == "add-rect":
        session.ensure_composer()

        session.composer.add_rectangle_layer(
            layer_id=args.layer_id,
            x=args.x,
            y=args.y,
            width=args.width,
            height=args.height,
            filled=args.filled,
            color=args.color,
        )
        session.save_session()
        print(f"Added rectangle layer '{args.layer_id}'")

    elif args.command == "remove":
        session.ensure_composer()

        if session.composer.remove_layer(args.layer_id):
            session.save_session()
            print(f"Removed layer '{args.layer_id}'")
        else:
            print(f"Layer '{args.layer_id}' not found", file=sys.stderr)
            sys.exit(1)

    elif args.command == "toggle":
        session.ensure_composer()

        if session.composer.toggle_layer(args.layer_id):
            session.save_session()
            print(f"Toggled visibility of layer '{args.layer_id}'")
        else:
            print(f"Layer '{args.layer_id}' not found", file=sys.stderr)
            sys.exit(1)

    elif args.command == "reset":
        try:
            width, height = map(int, args.size.split("x"))
        except ValueError:
            print(f"Error: Invalid size format '{args.size}'. Use WIDTHxHEIGHT", file=sys.stderr)
            sys.exit(1)

        if session.session_file.exists():
            session.session_file.unlink()
            print("✓ Cleared existing session")

        session.composer = EinkComposer(width, height)
        session.save_session()
        print(f"✓ Created new {width}x{height} composition")
        print("Session reset complete")

    elif args.command == "list":
        session.ensure_composer()

        layers = session.composer.get_layer_info()
        if not layers:
            print("No layers")
        else:
            print(f"Composition: {session.composer.width}x{session.composer.height}")
            print("\nLayers:")
            for layer in layers:
                visibility = "✓" if layer["visible"] else "✗"
                print(
                    f"  [{visibility}] {layer['id']:15} {layer['type']:10} @ ({layer['x']},{layer['y']})"
                )

                if layer["type"] == "text":
                    print(f"      Text: '{layer['text']}'")
                elif layer["type"] == "image":
                    print(f"      Image: {layer.get('image_path', 'N/A')}")
                elif layer["type"] == "rectangle":
                    print(f"      Size: {layer['width']}x{layer['height']}")

    elif args.command == "render":
        session.ensure_composer()

        session.composer.save(args.output, format=args.format)
        print(f"Rendered to {args.output}")

    elif args.command == "save":
        session.ensure_composer()
        session.composer.save_json(args.filename)
        print(f"Saved composition to {args.filename}")

    elif args.command == "load":
        try:
            session.composer = EinkComposer(128, 250)
            session.composer.load_json(args.filename)
            session.save_session()
            print(f"Loaded composition from {args.filename}")

            if args.render and args.output:
                session.composer.save(args.output, format=args.format)
                print(f"Rendered to {args.output}")

        except Exception as e:
            print(f"Error loading composition: {e}", file=sys.stderr)
            sys.exit(1)

    elif args.command == "display":
        if not HARDWARE_AVAILABLE:
            print("Error: Hardware display not available. SDK not found.", file=sys.stderr)
            sys.exit(1)

        session.ensure_composer()

        try:
            # Use composer's display method which uses SDK
            mode = DisplayMode.PARTIAL if args.partial else DisplayMode.FULL

            # Clear first if requested
            if args.clear:
                session.composer.clear_display()
                print("✓ Display cleared")

            # Save preview if requested
            if args.save_preview:
                session.composer.save(args.save_preview, format="png")
                print(f"✓ Preview saved to {args.save_preview}")

            # Display on hardware
            # Convert boolean rotate to RotationMode
            from .. import RotationMode

            rotation = RotationMode.ROTATE_90 if args.rotate else RotationMode.NONE
            success = session.composer.display(
                mode=mode, rotation=rotation, flip_h=args.flip_h, flip_v=args.flip_v
            )

            if success:
                print("✓ Image displayed on e-ink")
            else:
                print("✗ Failed to display image", file=sys.stderr)
                sys.exit(1)

        except Exception as e:
            print(f"Display error: {e}", file=sys.stderr)
            sys.exit(1)

    elif args.command == "hardware":
        if not HARDWARE_AVAILABLE:
            print("Error: Hardware not available. SDK not found.", file=sys.stderr)
            sys.exit(1)

        try:
            # Use context manager for automatic acquire/release
            with Display(auto_init=False) as display:
                if args.hw_command == "info":
                    width, height = display.get_dimensions()
                    print(f"Display: {width}x{height} pixels")
                    print(f"Firmware: {display.get_firmware()}")

                elif args.hw_command == "clear":
                    display.clear()
                    print("✓ Display cleared")

                elif args.hw_command == "sleep":
                    display.sleep()
                    print("✓ Display in sleep mode")

        except Exception as e:
            print(f"Hardware error: {e}", file=sys.stderr)
            sys.exit(1)

    elif args.command == "template":
        try:
            renderer = TemplateRenderer(args.template_path)
            composer = renderer.render(ip_address=args.ip, tunnel_url=args.url)

            if args.output:
                composer.save(args.output)
                print(f"✓ Template rendered to {args.output}")

            if args.display:
                if not HARDWARE_AVAILABLE:
                    print("Error: Hardware not available", file=sys.stderr)
                    sys.exit(1)

                success = composer.display()
                if success:
                    print("✓ Template displayed on e-ink")
                else:
                    print("✗ Failed to display template", file=sys.stderr)
                    sys.exit(1)

        except Exception as e:
            print(f"Template error: {e}", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()
