#pragma once

#include <vector>

template <typename T>
struct History {
  std::vector<T> states        = {};
  int            current_state = -1;

  void save(const T& state) {
    // Overwrite future.
    this->states.resize(this->current_state + 1);
    this->states.push_back(state);
    this->current_state = (int)this->states.size() - 1;
  }

  bool undo(T& state) {
    if (this->current_state <= 0) {
      return false;
    }
    this->current_state -= 1;
    state = this->states[current_state];
    return true;
  }

  bool redo(T& state) {
    if (this->current_state + 1 >= (int)this->states.size()) {
      return false;
    }
    this->current_state += 1;
    state = this->states[current_state];
    return true;
  };
};
