from pyray import *
from kitchen_table.config import tweak
from kitchen_table.game_state import create_example_table_state
from kitchen_table.rendering import draw_table, draw_background
from kitchen_table.input import update_input


def main():
    # Initialize window
    init_window(
        tweak["window_width"],
        tweak["window_height"],
        tweak["window_title"]
    )
    set_target_fps(tweak["target_fps"])

    # Create initial table state
    state = create_example_table_state()

    # Main loop
    while not window_should_close():
        # Update
        update_input(state)

        # Draw
        begin_drawing()
        draw_background()
        draw_table(state)
        end_drawing()

    # Cleanup
    close_window()


if __name__ == "__main__":
    main()
