from pyray import *
from config import tweak
from game_state import create_game_state
from rendering import draw_game, color_from_tuple
from input import update_input


def main():
    # Initialize window
    init_window(
        tweak["window_width"],
        tweak["window_height"],
        tweak["window_title"]
    )
    set_target_fps(tweak["target_fps"])

    # Create initial game state
    state = create_game_state()

    # Main loop
    while not window_should_close():
        # Update
        update_input(state)

        # Draw
        begin_drawing()
        clear_background(color_from_tuple(tweak["background_color"]))
        draw_game(state)
        end_drawing()

    # Cleanup
    close_window()


if __name__ == "__main__":
    main()
