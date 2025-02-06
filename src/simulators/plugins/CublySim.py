import logging
import os
import platform
import sys
import threading
import time
from typing import List

import gif_pygame
import pygame

from llm.output_model import Command
from providers.io_provider import IOProvider


class CublySim:
    def __init__(self):
        self.messages: list[str] = []
        self.io_provider = IOProvider()
        self.io_provider.fuser_end_time = 0
        self.io_provider.llm_start_time = 0
        self.io_provider.llm_end_time = 0

        self.name = __class__
        self._initialized = False

        # Initialize basic attributes
        self.X = 1024
        self.Y = 768
        self.a_s = "idle"
        self.stats = {"fps": 0}
        self.last_time = time.time()

        # Initialize surfaces
        self.surface_info = None
        self.surface_main = None
        self.display = None
        self.animations = {}

        # Initialize pygame
        self._initialize_pygame()

    def _initialize_pygame(self):
        """Initialize pygame in the current thread"""
        try:
            pygame.init()
            pygame.display.init()

            # Create window with basic flags
            flags = pygame.DOUBLEBUF | pygame.RESIZABLE

            # Create window
            self.display = pygame.display.set_mode((self.X, self.Y), flags)
            pygame.display.set_caption("Racoon AI Assistant")

            # Create basic surfaces without alpha for better performance
            self.surface_info = pygame.Surface((300, self.Y))
            self.surface_main = pygame.Surface((self.X - 300, self.Y))

            # Initialize components
            self._init_components()
            self._initialized = True

            # Set up frame timing
            self.clock = pygame.time.Clock()
            self.frame_count = 0
            self.fps_update_time = time.time()
            self.last_frame = time.time()

            return True

        except Exception as e:
            logging.error(f"Error initializing pygame: {str(e)}")
            if pygame.get_init():
                pygame.quit()
            return False

    def _init_components(self):
        """Initialize all components after pygame is ready"""
        self.colors = {
            "bg": (240, 244, 248),
            "panel": (255, 255, 255),
            "primary": (41, 128, 185),
            "accent": (230, 126, 34),
            "text": (44, 62, 80),
            "text_light": (127, 140, 141),
            "debug": (255, 0, 0),
            "success": (46, 204, 113),
            "warning": (241, 196, 15),
            "info": (52, 152, 219),
        }

        # Initialize fonts
        self.title_font = pygame.font.SysFont("arial", 24, bold=True)
        self.font = pygame.font.SysFont("arial", 16)

        # Set up assets path
        self.path = os.path.join(os.path.dirname(__file__), "assets")

        # Load logo
        try:
            logo_path = os.path.join(self.path, "openmind_logo.png")
            self.logo = pygame.image.load(logo_path)
            self.logo = pygame.transform.scale(
                self.logo, (100, 30)
            )  # Adjust size as needed
        except Exception as e:
            logging.error(f"Error loading logo: {e}")
            self.logo = None

        # Load animations
        self._load_animations()

        self.a_s = "stand still"
        self.stats = {"fps": 0}
        self.last_time = time.time()

    def _load_animations(self):
        """Load all animation assets"""
        try:
            animation_files = {
                "idle": "idle.gif",
                "sit": "ko.gif",
                "walk": "walk.gif",
                "walk back": "walk_back.gif",
                "run": "run.gif",
                "shake paw": "crouch.gif",
                "dance": "dance.gif",
                "jump": "jump.gif",
            }

            self.animations = {}
            for action, filename in animation_files.items():
                filepath = os.path.join(self.path, filename)
                if os.path.exists(filepath):
                    try:
                        self.animations[action] = gif_pygame.load(filepath)
                        logging.info(f"Loaded animation: {action} from {filepath}")
                    except Exception as e:
                        logging.error(f"Failed to load animation {action}: {str(e)}")
                else:
                    logging.warning(f"Missing animation file: {filepath}")

        except Exception as e:
            logging.error(f"Error loading animations: {str(e)}")
            self.animations = {}

    def _draw_panel(self, surface, rect, color):
        """Draw a panel with a slight shadow effect"""
        shadow_rect = (rect[0] + 2, rect[1] + 2, rect[2], rect[3])
        pygame.draw.rect(surface, (0, 0, 0, 30), shadow_rect, border_radius=5)
        pygame.draw.rect(surface, color, rect, border_radius=5)

    def _render_text(self, surface, text, font, color, pos, max_width=None):
        """Render text with optional wrapping"""
        if max_width:
            words = text.split()
            lines = []
            current_line = []

            for word in words:
                test_line = " ".join(current_line + [word])
                test_surface = font.render(test_line, True, color)

                if test_surface.get_width() > max_width:
                    if current_line:
                        lines.append(" ".join(current_line))
                        current_line = [word]
                    else:
                        lines.append(word)
                else:
                    current_line.append(word)

            if current_line:
                lines.append(" ".join(current_line))

            height = 0
            for i, line in enumerate(lines):
                text_surface = font.render(line, True, color)
                surface.blit(text_surface, (pos[0], pos[1] + i * font.get_linesize()))
                height += font.get_linesize()
            return height
        else:
            text_surface = font.render(text, True, color)
            surface.blit(text_surface, pos)
            return font.get_linesize()

    def _render_animation(self, animation, dest_rect):
        """Safely render animation with proper synchronization"""
        try:
            if not animation:
                return None

            # Create a temporary surface for the animation frame
            temp_surface = pygame.Surface((dest_rect[2], dest_rect[3]))
            temp_surface.fill(self.colors["bg"])  # Fill with background color

            # Render the animation frame directly to temp surface
            animation.render(temp_surface, (0, 0))

            # Create a copy to avoid memory issues
            final_surface = temp_surface.copy()
            del temp_surface

            return final_surface

        except Exception as e:
            logging.error(f"Animation render error: {e}")
            return None

    def _render_main_area(self):
        """Render the main animation area"""
        try:
            # Clear main surface first
            self.surface_main.fill(self.colors["bg"])

            # Draw Input History on the left side
            history_width = 200
            history_x = 20
            history_y = 20

            # Input History section
            self._render_text(
                self.surface_main,
                "Input History",
                self.title_font,
                self.colors["primary"],
                (history_x, history_y),
            )

            # Input entries panel
            history_panel = (history_x, history_y + 35, history_width, self.Y - 80)
            self._draw_panel(self.surface_main, history_panel, self.colors["panel"])

            # Render input history
            y = history_y + 50
            if self.io_provider.inputs:
                for action, values in self.io_provider.inputs.items():
                    time_str = f"{(values.timestamp - self.get_earliest_time()):.3f}s"
                    self._render_text(
                        self.surface_main,
                        time_str,
                        self.font,
                        self.colors["accent"],
                        (history_x + 15, y),
                    )
                    y += 20

                    y += self._render_text(
                        self.surface_main,
                        f"{action}: {values.input}",
                        self.font,
                        self.colors["text"],
                        (history_x + 15, y),
                        max_width=history_width - 30,
                    )
                    y += 15

            # Calculate animation area with offset for history panel
            animation_width = 400
            available_width = (
                self.X - 300 - history_width - 60
            )  # Subtract history width and some padding
            animation_x = (
                history_width + 40 + (available_width - animation_width) // 2
            )  # Center in remaining space

            # Draw animation area background
            animation_panel = (animation_x, 20, animation_width, animation_width)
            self._draw_panel(self.surface_main, animation_panel, self.colors["panel"])

            # Prepare animation frame
            animation = self.animations.get(self.a_s, self.animations["idle"])
            if animation:
                frame_surface = self._render_animation(
                    animation, (0, 0, animation_width - 20, animation_width - 20)
                )
                if frame_surface:
                    self.surface_main.blit(frame_surface, (animation_x + 10, 30))
                    del frame_surface

            # Draw action label
            label_panel = (animation_x, animation_width + 30, animation_width, 40)
            self._draw_panel(self.surface_main, label_panel, self.colors["primary"])

            text = f"Current Action: {self.a_s.title()}"
            text_surface = self.font.render(text, True, self.colors["panel"])
            text_rect = text_surface.get_rect(
                center=(animation_x + animation_width // 2, animation_width + 50)
            )
            self.surface_main.blit(text_surface, text_rect)

        except Exception as e:
            logging.error(f"Error in main area render: {e}")

    def _render_footer(self):
        """Render footer with OpenMind logo and info"""
        try:
            footer_height = 40
            footer_y = self.Y - footer_height - 10

            # Draw footer background
            footer_rect = (0, footer_y, self.X - 300, footer_height)
            self._draw_panel(self.surface_main, footer_rect, self.colors["panel"])

            # Draw logo if available
            if hasattr(self, "logo") and self.logo:
                logo_y = footer_y + (footer_height - self.logo.get_height()) // 2
                self.surface_main.blit(self.logo, (20, logo_y))
                text_x = 130  # Adjust based on logo width
            else:
                text_x = 20

            text_y = footer_y + (footer_height - self.font.get_height()) // 2

            # Version info
            version_text = "OpenMind AI Assistant v1.0"
            self._render_text(
                self.surface_main,
                version_text,
                self.font,
                self.colors["text"],
                (text_x, text_y),
            )

            # Draw right-aligned text
            right_text = "Powered by OpenMind"
            text_surface = self.font.render(right_text, True, self.colors["text_light"])
            text_rect = text_surface.get_rect(
                right=(self.X - 320, text_y + self.font.get_height())
            )
            self.surface_main.blit(text_surface, text_rect)

        except Exception as e:
            logging.error(f"Error rendering footer: {e}")

    def _render_actions_panel(self, x, y, width):
        """Render available actions panel with improved aesthetics"""
        height = self.Y - 40
        SPACING = {
            "panel_padding": 20,
            "section_spacing": 25,
            "item_spacing": 18,
            "category_spacing": 30,
        }

        # Draw main panel
        self._draw_panel(self.surface_main, (x, y, width, height), self.colors["panel"])

        # Content layout
        content_x = x + SPACING["panel_padding"]
        content_y = y + SPACING["panel_padding"]

        # Title with shadow
        content_y += self._render_text(
            self.surface_main,
            "Available Actions",
            self.title_font,
            self.colors["primary"],
            (content_x, content_y),
        )
        content_y += SPACING["section_spacing"]

        # Categories with improved spacing
        categories = [
            (
                "Movement",
                ["Be Still", "Little Jump", "Medium Jump", "Big Jump"],
            ),
            ("Speech", ["speak"]),
        ]

        for category, actions in categories:
            # Category header with shadow
            content_y += self._render_text(
                self.surface_main,
                category,
                self.font,
                self.colors["accent"],
                (content_x, content_y),
            )
            content_y += SPACING["item_spacing"]

            # Actions with improved bullets
            for action in actions:
                bullet_x = content_x + 10
                text_x = bullet_x + 15

                # Draw bullet point
                pygame.draw.circle(
                    self.surface_main,
                    self.colors["accent"],
                    (bullet_x, content_y + 8),
                    3,
                )

                # Action text with shadow
                content_y += self._render_text(
                    self.surface_main,
                    action,
                    self.font,
                    self.colors["text"],
                    (text_x, content_y),
                )
                content_y += SPACING["item_spacing"] - 5

            content_y += SPACING["category_spacing"] - SPACING["item_spacing"]

    def _render_status_panel(self, x, y, width):
        """Render status information panel"""
        # Background panel
        panel_rect = (x, y, width, self.Y - 40)
        self._draw_panel(self.surface_main, panel_rect, self.colors["panel"])

        # Last Speech section
        speech_y = 100
        speech_rect = (x + 10, speech_y, width - 20, 100)
        self._draw_panel(self.surface_main, speech_rect, self.colors["info"])

        # Speech title
        self._render_text(
            self.surface_main,
            "Last Speech",
            self.title_font,
            self.colors["panel"],
            (x + 20, speech_y + 10),
        )

        # Speech content with word wrap
        speech_text = (
            self.last_speech if hasattr(self, "last_speech") else "No speech yet"
        )
        self._render_text(
            self.surface_main,
            speech_text,
            self.font,
            self.colors["panel"],
            (x + 20, speech_y + 40),
            max_width=width - 40,
        )

        # Available Actions section
        actions_y = speech_y + 120
        actions_rect = (x + 10, actions_y, width - 20, 200)
        self._draw_panel(self.surface_main, actions_rect, self.colors["primary"])

        # Actions title
        self._render_text(
            self.surface_main,
            "Quick Actions",
            self.title_font,
            self.colors["panel"],
            (x + 20, actions_y + 10),
        )

        # List of common actions
        actions = ["Be Still", "Little Jump", "Medium Jump", "Big Jump"]

        action_y = actions_y + 40
        action_x = x + 20
        for action in actions:
            self._render_text(
                self.surface_main,
                f"• {action}",
                self.font,
                self.colors["panel"],
                (action_x, action_y),
            )
            action_y += 20

    def _render_sidebar(self, earliest_time):
        """Render information sidebar"""
        # Clear sidebar
        self.surface_info.fill(self.colors["panel"])

        y = 20

        # System Status section
        self._render_text(
            self.surface_info,
            "System Status",
            self.title_font,
            self.colors["primary"],
            (20, y),
        )

        # FPS display
        y += 35
        self._render_text(
            self.surface_info,
            f"FPS: {self.stats['fps']:.1f}",
            self.font,
            self.colors["text"],
            (20, y),
        )

        # Timing information
        y += 30
        timing_data = [
            ("Fuse time:", f"{self.io_provider.fuser_end_time - earliest_time:.3f}s"),
            (
                "LLM start:",
                f"{float(self.io_provider.llm_start_time or 0) - earliest_time:.3f}s",
            ),
            (
                "Processing:",
                f"{float(self.io_provider.llm_end_time or 0) - float(self.io_provider.llm_start_time or 0):.3f}s",
            ),
            (
                "Complete:",
                f"{float(self.io_provider.llm_end_time or 0) - earliest_time:.3f}s",
            ),
        ]

        for label, value in timing_data:
            self._render_text(
                self.surface_info, label, self.font, self.colors["text_light"], (20, y)
            )
            self._render_text(
                self.surface_info, value, self.font, self.colors["text"], (120, y)
            )
            y += 25

        # Available Commands section
        y += 30
        self._render_text(
            self.surface_info,
            "Possible Actions",
            self.title_font,
            self.colors["primary"],
            (20, y),
        )

        y += 35
        commands = {
            "Movement": ["be still", "small jump", "medium jump", "big jump"],
            "Speech": ["speech - Speak a message"],
        }

        for category, cmd_list in commands.items():
            # Draw category
            self._render_text(
                self.surface_info, category, self.font, self.colors["accent"], (20, y)
            )
            y += 25

            # Draw commands
            for cmd in cmd_list:
                y += self._render_text(
                    self.surface_info,
                    f"• {cmd}",
                    self.font,
                    self.colors["text"],
                    (30, y),
                    max_width=250,
                )
            y += 15

    def _handle_events(self):
        """Process pygame events"""
        if threading.current_thread() is not threading.main_thread():
            return

        try:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.cleanup()
                    sys.exit()
                elif event.type == pygame.VIDEORESIZE:
                    self.X, self.Y = event.size
                    self.display = pygame.display.set_mode(
                        (self.X, self.Y), pygame.RESIZABLE
                    )
                    # Recreate surfaces with new size
                    self.surface_info = pygame.Surface((300, self.Y))
                    self.surface_main = pygame.Surface((self.X - 300, self.Y))
        except Exception as e:
            logging.error(f"Error handling events: {e}")

    def tick(self) -> None:
        """Main update loop"""
        if not self._initialized:
            return

        try:
            # Handle events first
            self._handle_events()

            # Frame timing
            current_time = time.time()
            frame_time = 1.0 / 60.0  # Target 60 FPS

            if current_time - self.last_frame < frame_time:
                return

            # Update FPS counter
            self.frame_count += 1
            if current_time - self.fps_update_time >= 1.0:
                self.stats["fps"] = self.frame_count
                self.frame_count = 0
                self.fps_update_time = current_time

            self.last_frame = current_time

            # Clear main display once
            self.display.fill(self.colors["bg"])

            # Render everything
            self._render_main_area()
            earliest_time = self.get_earliest_time()
            self._render_sidebar(earliest_time)

            # Single blit operation for each surface
            self.display.blit(self.surface_main, (0, 0))
            self.display.blit(self.surface_info, (self.X - 300, 0))

            # Single flip operation
            pygame.display.flip()

            # Maintain frame timing
            self.clock.tick(60)

        except Exception as e:
            logging.error(f"Error in tick: {str(e)}")

    def input_clean(self, input, earliest_time) -> str:
        st = input
        st = st.strip()
        st = st.replace("\n", "")
        st = st.replace("INPUT // START ", "")
        st = st.replace(" // END", "")

        sts = st.split("::")
        time = float(sts[0])
        time_rezero = time - earliest_time
        time_st = f"{time_rezero:.3f}::{sts[-1]}"

        return time_st

    def get_earliest_time(self) -> float:
        earliest_time = float("inf")
        for value in self.io_provider.inputs.values():
            timestamp = value.timestamp
            if timestamp < earliest_time:
                earliest_time = timestamp
        return earliest_time

    def sim(self, commands: List[Command]) -> None:
        """Handle simulation updates from commands"""
        try:
            # Update animation state based on commands
            for command in commands:
                if command.name == "move":
                    self.a_s = command.arguments[0].value
                elif command.name == "speak":
                    self.update_speech(command.arguments[0].value)

        except Exception as e:
            logging.error(f"Error in sim update: {str(e)}")

    def cleanup(self):
        """Clean up resources"""
        try:
            if pygame.get_init():
                pygame.quit()
        except Exception as e:
            logging.error(f"Error during cleanup: {e}")
        finally:
            self._initialized = False

    def __del__(self):
        self.cleanup()

    def update_speech(self, text: str):
        """Update the last speech text"""
        self.last_speech = text[:50] + "..." if len(text) > 50 else text

    def __enter__(self):
        """Initialize platform-specific settings before pygame"""
        if platform.system() == "Darwin":
            os.environ["SDL_VIDEODRIVER"] = "cocoa"
            os.environ["SDL_THREADSAFE"] = "1"
            os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"
            os.environ["SDL_VIDEO_CENTERED"] = "1"
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Cleanup when exiting context"""
        self.cleanup()
