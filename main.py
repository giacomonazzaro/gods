from pyray import *
from config import tweak
from game_state import create_example_table_state
from rendering import draw_table, color_from_tuple
from input import update_input
from copy import deepcopy


def animate(rendered_state, target_state, dt: float = 0.1) -> None:
    """Animate rendered_state towards target_state."""
    # Sync stack and loose_cards indices (these are just references)

    # Interpolate card positions
    for r_card, t_card in zip(rendered_state.cards, target_state.cards):
        r_card.x = r_card.x * (1 - dt) + t_card.x * dt
        r_card.y = r_card.y * (1 - dt) + t_card.y * dt
        r_card.rotation = r_card.rotation * (1 - dt) + t_card.rotation * dt

    rendered_state.cards[target_state.drag_state.card_id].x = target_state.cards[target_state.drag_state.card_id].x
    rendered_state.cards[target_state.drag_state.card_id].y = target_state.cards[target_state.drag_state.card_id].y

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
    rendered_state = deepcopy(state)

    # Main loop
    while not window_should_close():
        # Update
        update_input(state)


        for r_stack, t_stack in zip(rendered_state.stacks, state.stacks):
            r_stack.cards = t_stack.cards[:]
        rendered_state.loose_cards = state.loose_cards[:]
        rendered_state.drag_state = state.drag_state
        animate(rendered_state, state)

        # Draw
        begin_drawing()
        clear_background(color_from_tuple(tweak["background_color"]))
        draw_table(rendered_state)
        end_drawing()

    # Cleanup
    close_window()


if __name__ == "__main__":
    main()
