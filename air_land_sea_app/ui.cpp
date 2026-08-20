#include "ui.h"

#include <air_land_sea/gameplay.h>
#include <tabletop/config.h>
#include <tabletop/rendering.h>

#include <vector>

// raylib last: its color macros (RED/GREEN/BLUE) would expand inside enums
// otherwise.
#include <raylib.h>

using namespace air_land_sea;

Color theater_color(int theater) {
  if (theater == AIR) return Color{170, 182, 196, 255};
  if (theater == LAND) return Color{96, 142, 84, 255};
  return Color{58, 112, 172, 255};
}

const char* theater_name(int theater) {
  if (theater == AIR) return "AIR";
  if (theater == LAND) return "LAND";
  return "SEA";
}

// Splits `text` into lines no wider than `width` and draws them from `y` down.
// Returns the y below the last line.
static float draw_wrapped_text(
  const std::string& text, float x, float y, float width, int size, Color color
) {
  auto line = std::string();
  auto word = std::string();
  for (size_t i = 0; i <= text.size(); ++i) {
    const bool end = i == text.size();
    if (!end && text[i] != ' ') {
      word += text[i];
      continue;
    }
    const std::string candidate = line.empty() ? word : line + " " + word;
    if (text_width(candidate, size) > width && !line.empty()) {
      render_text(line, x, y, size, color);
      y += (float)size + 2.0f;
      line = word;
    } else {
      line = candidate;
    }
    word.clear();
  }
  if (!line.empty()) {
    render_text(line, x, y, size, color);
    y += (float)size + 2.0f;
  }
  return y;
}

// Where a card is, as far as what the local player may see goes.
static bool is_visible_to(
  const Game_State& state, int card, int local_seat, bool hot_seat
) {
  const Placement* placement = find_placement(state, card);
  if (placement) {
    if (!placement->face_down) return true;
    return placement->owner == local_seat || hot_seat;
  }
  for (int held : state.hands[local_seat]) {
    if (held == card) return true;
  }
  for (int held : state.hands[1 - local_seat]) {
    if (held == card) return hot_seat;
  }
  return false;  // Still in the deck.
}

std::function<void(const Table_State&, const Input&, bool)>
make_card_draw_callback(
  const Game_State& state,
  int               card,
  int               local_seat,
  bool              hot_seat,
  bool              highlighted
) {
  return [&state, card, local_seat, hot_seat, highlighted](
           const Table_State&, const Input&, bool face_up
         ) {
    if (!face_up) return;
    const float half_width  = (float)tt::CARD_WIDTH / 2.0f;
    const float half_height = (float)tt::CARD_HEIGHT / 2.0f;
    const Rectangle face =
      Rectangle{-half_width, -half_height, (float)tt::CARD_WIDTH,
                (float)tt::CARD_HEIGHT};
    const float rounding = (float)tt::CARD_CORNER_RADIUS /
                           (float)tt::CARD_WIDTH;

    // The zoom draws a thing face up whatever the card itself says, so a card
    // this player may not see is covered here.
    if (!is_visible_to(state, card, local_seat, hot_seat)) {
      DrawRectangleRounded(face, rounding, 8, ::Color{48, 62, 94, 255});
      DrawRectangleRounded(
        Rectangle{face.x + 15.0f, face.y + 15.0f, face.width - 30.0f,
                  face.height - 30.0f},
        rounding,
        8,
        ::Color{64, 80, 112, 255}
      );
      return;
    }

    const Card_Design& design = card_designs[card];
    const auto strength       = std::to_string(card_strength(card));
    render_text(
      strength, -half_width + 12.0f, -half_height + 8.0f, 42,
      Color{20, 20, 20, 255}
    );
    const char* theater = theater_name(card_theater(card));
    render_text(
      theater,
      half_width - (float)text_width(theater, 16) - 12.0f,
      -half_height + 14.0f,
      16,
      Color{30, 30, 30, 210}
    );

    float y = -half_height + 62.0f;
    y = draw_wrapped_text(
      design.name, -half_width + 10.0f, y, (float)tt::CARD_WIDTH - 20.0f, 17,
      Color{15, 15, 15, 255}
    );
    draw_wrapped_text(
      design.text, -half_width + 10.0f, y + 6.0f,
      (float)tt::CARD_WIDTH - 20.0f, 11, Color{25, 25, 25, 220}
    );

    // On the table a card can count for a different strength than the one
    // printed on it: face down it is 2, and Escalation or Cover Fire make it 4.
    const Placement* placement = find_placement(state, card);
    if (placement) {
      const int counted = strength_in_play(state, *placement);
      if (counted != card_strength(card)) {
        const auto  text    = std::to_string(counted);
        const float badge_x = half_width - 24.0f;
        const float badge_y = half_height - 24.0f;
        DrawCircle(
          (int)badge_x, (int)badge_y, 20.0f, ::Color{20, 20, 20, 235}
        );
        render_text(
          text,
          badge_x - (float)text_width(text, 26) / 2.0f,
          badge_y - 13.0f,
          26,
          Color{255, 255, 255, 255}
        );
      }
      if (placement->face_down) {
        DrawRectangleRounded(face, rounding, 8, ::Color{0, 0, 0, 120});
      }
    }

    if (highlighted) {
      DrawRectangleRoundedLinesEx(
        face, rounding, 8, 5.0f, Color{255, 215, 0, 230}
      );
    }
  };
}

std::function<void(const Table_State&, const Input&, bool)>
make_theater_draw_callback(
  const Game_State& state, int position, bool highlighted
) {
  return [&state, position, highlighted](
           const Table_State&, const Input&, bool
         ) {
    const float half_width  = 100.0f;
    const float half_height = 35.0f;
    const char* name        = theater_name(state.theaters[position]);
    render_text(
      name,
      -(float)text_width(name, 30) / 2.0f,
      -15.0f,
      30,
      Color{255, 255, 255, 240}
    );
    if (highlighted) {
      DrawRectangleRoundedLinesEx(
        Rectangle{-half_width, -half_height, half_width * 2.0f,
                  half_height * 2.0f},
        0.2f,
        8,
        5.0f,
        Color{255, 215, 0, 230}
      );
    }
  };
}

void draw_air_land_sea_hud(const Game_State& state, int local_seat) {
  const float x = 16.0f;
  render_text("Air, Land, & Sea", x, 16.0f, 26, Color{235, 235, 235, 255});

  const std::string turn = state.current_player == local_seat
                             ? "Your turn"
                             : "Opponent's turn";
  render_text(turn, x, 50.0f, 20, Color{170, 170, 170, 255});

  const std::string points =
    "Points  you " + std::to_string(state.points[local_seat]) + "  -  " +
    std::to_string(state.points[1 - local_seat]) + " opponent  (first to " +
    std::to_string(POINTS_TO_WIN) + ")";
  render_text(points, x, 76.0f, 18, Color{170, 170, 170, 255});

  const std::string theaters =
    "Theaters  you " + std::to_string(theaters_controlled(state, local_seat)) +
    "  -  " + std::to_string(theaters_controlled(state, 1 - local_seat)) +
    " opponent";
  render_text(theaters, x, 100.0f, 18, Color{170, 170, 170, 255});

  if (state.first_player == local_seat) {
    render_text(
      "You are 1st player: you win tied theaters", x, 124.0f, 16,
      Color{200, 180, 120, 255}
    );
  }
}
