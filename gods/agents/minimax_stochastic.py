from __future__ import annotations
from gods.models import Game_State, Choice
from gods.game import compute_player_score, get_next_choice
import copy
import time
import random


class Agent_Minimax_Stochastic:
    def __init__(self, max_depth: int = 5, time_limit: float = 10.0, num_samples: int = 20):
        self.max_depth = max_depth
        self.time_limit = time_limit
        self.num_samples = num_samples
        self.player_index = None
        self.nodes_searched = 0
        self.time_up = False
        self.start_time = 0.0
        self.sample_time_limit = time_limit  # Per-sample time budget

    def message(self, msg: str):
        pass

    def _sample_state(self, state: Game_State) -> Game_State:
        """Create a sampled state by shuffling hidden information.

        The agent cannot see:
        - Opponent's hand (only knows the count)
        - Opponent's deck order
        - Agent's own deck order
        """
        sampled = copy.deepcopy(state)

        # Shuffle opponent's hidden cards (hand + deck)
        opp_index = 1 - self.player_index
        opp = sampled.players[opp_index]
        hand_size = len(opp.hand)
        hidden_cards = opp.hand + opp.deck
        random.shuffle(hidden_cards)
        opp.hand = hidden_cards[:hand_size]
        opp.deck = hidden_cards[hand_size:]

        # Shuffle agent's own deck (hand is known, deck order is not)
        me = sampled.players[self.player_index]
        random.shuffle(me.deck)

        return sampled

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
        """Stochastic minimax with root sampling.

        Runs multiple samples to handle hidden information:
        - Opponent's hand and deck are shuffled together, then redrawn
        - Agent's own deck is shuffled

        For each sample, runs iterative deepening alpha-beta search.
        Returns the action with the highest average score across samples.
        """
        num_actions = len(choice.actions.actions)
        total_scores: dict[int, float] = {a: 0.0 for a in range(num_actions)}
        time_per_sample = self.time_limit / self.num_samples
        overall_start = time.time()

        print(f"started: {choice.actions.type} ({self.num_samples} samples)")

        for sample_idx in range(self.num_samples):
            # Create a sampled state with shuffled hidden information
            sampled_state = self._sample_state(state)

            # Run iterative deepening on this sample
            self.start_time = time.time()
            self.sample_time_limit = time_per_sample
            self.time_up = False
            self.nodes_searched = 0

            best_scores: dict[int, float] = {a: -float("inf") for a in range(num_actions)}
            action_order = list(range(num_actions))

            for depth in range(1, self.max_depth + 1):
                if time.time() - self.start_time >= time_per_sample:
                    break
                _, _, scores = self.minimax_root(
                    sampled_state, choice, depth, action_order
                )
                if not self.time_up:
                    best_scores = scores
                    action_order.sort(key=lambda a: scores.get(a, -1e9), reverse=True)

            # Accumulate scores from this sample
            for action, score in best_scores.items():
                total_scores[action] += score

        # Find action with highest total (average) score
        best_action = max(range(num_actions), key=lambda a: total_scores[a])
        elapsed = time.time() - overall_start
        avg_score = total_scores[best_action] / self.num_samples
        print(
            f"  result: action={choice.actions.actions[best_action]} "
            f"avg_score={avg_score:.2f} time={elapsed:.2f}s"
        )

        return best_action

    def _check_time(self):
        """Set time_up flag if we exceeded the per-sample time budget."""
        if time.time() - self.start_time >= self.sample_time_limit:
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
