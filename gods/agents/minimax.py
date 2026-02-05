from __future__ import annotations
from gods.models import Game_State, Choice
from gods.game import compute_player_score, get_next_choice
import copy
import time


class Agent_Minimax:
    def __init__(self, max_depth: int = 5, time_limit: float = 10.0):
        self.max_depth = max_depth
        self.time_limit = time_limit
        self.player_index = None
        self.nodes_searched = 0
        self.time_up = False
        self.start_time = 0.0

    def message(self, msg: str):
        pass

    def choose_action(self, state: Game_State, choice: Choice) -> int:
        # Trivial cases: no real decision to make.
        action_list = choice.actions
        if len(action_list.actions) == 0:
            return 0
        if len(action_list.actions) == 1:
            return 0

        # Track which player we are. is_root is True for the top-level call
        # (the actual move we need to pick). The agent can also be called
        # recursively during simulation, in which case player_index is
        # already set.
        is_root = self.player_index is None
        if is_root:
            self.player_index = choice.player_index

        selected = self._search(state, choice)

        # Reset player_index so the agent is reusable for the next real move.
        if is_root:
            self.player_index = None
        return selected

    def _search(self, state: Game_State, choice: Choice) -> int:
        """Iterative deepening: run alpha-beta at depth 1, then 2, etc.
        up to max_depth or until time runs out. Each deeper search gives
        a better answer; if time expires mid-search we keep the result
        from the last fully completed depth."""
        self.start_time = time.time()
        self.time_up = False
        best_action = 0
        num_actions = len(choice.actions.actions)
        # action_order controls which moves we try first. After each
        # completed depth we reorder by score so the best move is tried
        # first at the next depth -- this makes alpha-beta prune more.
        action_order = list(range(num_actions))

        print("started:", choice.actions.type)
        for depth in range(1, self.max_depth + 1):
            if self.time_up:
                break
            self.nodes_searched = 0
            action, score, scores = self.minimax_root(
                state, choice, depth, action_order
            )
            # Only trust the result if the search finished before time ran out.
            if not self.time_up:
                best_action = action
                elapsed = time.time() - self.start_time
                print(
                    f"  depth {depth}: action={choice.actions.actions[action]} "
                    f"score={score:.2f} nodes={self.nodes_searched} "
                    f"time={elapsed:.2f}s"
                )
                # Reorder: try the highest-scoring moves first next iteration.
                action_order.sort(
                    key=lambda a: scores.get(a, -1e9), reverse=True
                )
            # Early exit if we found a win or loss (score near +/-1000).
            if abs(score) >= 900:
                break

        return best_action

    def _check_time(self):
        """Set time_up flag if we exceeded the time budget."""
        if time.time() - self.start_time >= self.time_limit:
            self.time_up = True

    def minimax_root(
        self,
        state: Game_State,
        choice: Choice,
        depth: int,
        action_order: list[int],
    ) -> tuple[int, float, dict[int, float]]:
        """Try every action at the root and return (best_action, best_score,
        all_scores). This is separate from minimax because at the root
        we always need to try all actions (to get scores for reordering),
        and we need to track which action index is best."""
        best_score = -float("inf")
        best_action = action_order[0]
        alpha = -float("inf")
        beta = float("inf")
        scores: dict[int, float] = {}

        for action in action_order:
            if self.time_up:
                break
            # Simulate this action on a deep copy, then evaluate recursively.
            sim = copy.deepcopy(state)
            sim_choice = copy.deepcopy(choice)
            sim_choice.resolve(sim, sim_choice, action)
            score = self.minimax(sim, depth, alpha, beta)
            scores[action] = score
            if score > best_score:
                best_score = score
                best_action = action
            alpha = max(alpha, score)

        return best_action, best_score, scores

    def minimax(
        self,
        state: Game_State,
        depth: int,
        alpha: float,
        beta: float,
    ) -> float:
        """Recursive minimax with alpha-beta pruning.

        - alpha: the best score the maximizing player (us) can guarantee so far
        - beta:  the best score the minimizing player (opponent) can guarantee

        If alpha >= beta, the opponent would never let us reach this branch,
        so we can prune (stop exploring) early.
        """
        self.nodes_searched += 1
        # Check time every 1024 nodes (the bitmask is cheaper than modulo).
        if self.nodes_searched & 1023 == 0:
            self._check_time()
        if self.time_up:
            return 0.0

        # Terminal state: game ended, return exact evaluation.
        if state.game_over:
            return self._evaluate(state)

        # Advance game to next decision point.
        choice = get_next_choice(state)
        if choice is None:
            return self._evaluate(state)

        # Depth counts "main" choices (play/pass/end turns). Sub-choices like
        # "pick a target for this card" don't consume depth so we explore
        # the full consequences of a single game action.
        
        # Whose turn to move? We maximize our score, opponent minimizes it.
        maximizing = choice.player_index == self.player_index

        next_depth = depth - 1 if not maximizing else depth
        if next_depth < 0:
            # Reached depth limit without game ending: use heuristic estimate.
            return self._evaluate_heuristic(state)

        actions = list(range(len(choice.actions.actions)))
        if not actions:
            return self._evaluate_heuristic(state)

        if maximizing:
            value = -float("inf")
            for action in actions:
                # Simulate the action on a copy of the state.
                sim = copy.deepcopy(state)
                sim_choice = copy.deepcopy(choice)
                sim_choice.resolve(sim, sim_choice, action)
                score = self.minimax(sim, next_depth, alpha, beta)
                value = max(value, score)
                alpha = max(alpha, value)
                # Beta cutoff: opponent won't allow us to reach a position
                # this good, so stop searching this branch.
                if alpha >= beta:
                    break
            return value
        else:
            # Minimizing: opponent picks the move worst for us.
            value = float("inf")
            for action in actions:
                sim = copy.deepcopy(state)
                sim_choice = copy.deepcopy(choice)
                sim_choice.resolve(sim, sim_choice, action)
                score = self.minimax(sim, next_depth, alpha, beta)
                value = min(value, score)
                beta = min(beta, value)
                # Alpha cutoff: we already have a better option elsewhere,
                # so the opponent choosing this branch can't hurt us more.
                if alpha >= beta:
                    break
            return value

    def _evaluate(self, state: Game_State) -> float:
        """Evaluate a finished game. Returns +1000 for win, -1000 for loss.
        On a tie, the player who declared "end" loses, so we check that."""
        my_score = compute_player_score(state, self.player_index)
        opp_score = compute_player_score(state, 1 - self.player_index)
        diff = my_score - opp_score
        if diff > 0:
            return 1000.0
        elif diff < 0:
            return -1000.0
        else:
            # Tie-breaker: whoever called "end" loses on a tie.
            if state.ending_player == self.player_index:
                return -1000.0
            else:
                return 1000.0

    def _evaluate_heuristic(self, state: Game_State) -> float:
        """Estimate how good a non-finished position is. Used when we hit
        the depth limit and can't search further. The base is the current
        point difference, plus small bonuses for advantageous board state."""
        my_score = compute_player_score(state, self.player_index)
        opp_score = compute_player_score(state, 1 - self.player_index)

        # Point difference is the main signal.
        score = float(my_score - opp_score)

        # Having more cards in hand = more options = slight advantage.
        my_hand = len(state.players[self.player_index].hand)
        opp_hand = len(state.players[1 - self.player_index].hand)
        score += 0.1 * (my_hand - opp_hand)

        # Wonders in play provide ongoing effects; slightly valuable.
        my_wonders = len(state.players[self.player_index].wonders)
        opp_wonders = len(state.players[1 - self.player_index].wonders)
        score += 0.2 * (my_wonders - opp_wonders)

        # Larger deck = more draws before game ends = small bonus.
        my_deck = len(state.players[self.player_index].deck)
        opp_deck = len(state.players[1 - self.player_index].deck)
        score += 0.05 * (my_deck - opp_deck)

        return score
