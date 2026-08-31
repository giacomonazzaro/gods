#pragma once

#include <mindbug/models.h>

namespace mindbug {

// The three moments a card can act on, each looked up by the creature's
// design. An ability that asks the players something pushes the choices onto
// state.queue instead of resolving right away.
void trigger_play(Game_State& state, int card);
void trigger_attack(Game_State& state, int card);
// A defeated creature has already left play, so its controller is passed in.
void trigger_defeated(Game_State& state, int card, int controller);

// ---- Standing abilities, also looked up by design ----
//
// These back the power and keyword auras, block restrictions and Play
// suppression that hold all the time a card is in play, rather than firing at
// one of the three moments above. gameplay.cpp calls these without knowing
// which design answers; a new card's standing ability is added here, never
// there.

// Power `ally` adds to another creature on its own side. 0 for cards with no
// such aura.
int ally_power_bonus(const Game_State& state, int ally, bool its_turn);

// Power a creature adds to itself. 0 for cards with no such condition.
int self_power_bonus(const Game_State& state, int card);

// Keywords `ally` grants another creature on its own side. 0 for cards with
// no such aura.
int ally_keywords(const Game_State& state, int ally, int card);

// Keywords a creature grants itself. 0 for cards with no such condition.
int self_keywords(const Game_State& state, int card);

// Keywords a creature copies from the enemy side. 0 for cards with no such
// ability.
int mirrored_keywords(const Game_State& state, int card);

// True when a standing ability — the attacker's own, or one of its allies' —
// stops `blocker` from blocking `attacker`.
bool block_prevented(const Game_State& state, int attacker, int blocker);

// True when something on the other side switches this Play ability off.
bool play_ability_suppressed(const Game_State& state, int controller);

}  // namespace mindbug
