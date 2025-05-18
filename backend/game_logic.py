import random
from collections import deque

NAIPES = ['♣', '♥', '♠', '♦']
VALORES = ['4', '5', '6', '7', 'Q', 'J', 'K', 'A', '2', '3']
ORDEM_CARTAS = {v: i for i, v in enumerate(VALORES)}
ORDEM_NAIPE_MANILHA = {'♦': 0, '♠': 1, '♥': 2, '♣': 3}
ORDEM_NAIPE_DESEMPATE = {'♣': 3, '♥': 2, '♠': 1, '♦': 0}

class Carta:
    def __init__(self, valor, naipe):
        self.valor, self.naipe = valor, naipe
    def __repr__(self): return f'{self.valor}{self.naipe}'
    def forca(self, manilha=None):
        if manilha and self.valor == manilha:
            return 100 + ORDEM_NAIPE_MANILHA[self.naipe]
        return ORDEM_CARTAS[self.valor]

def criar_baralho():
    baralho = [Carta(v, n) for v in VALORES for n in NAIPES]
    random.shuffle(baralho)
    return deque(baralho)

def definir_manilha(carta_meio):
    return VALORES[(VALORES.index(carta_meio.valor)+1) % len(VALORES)]

def simular_rodada(jogadores, n_cartas, vidas, dealer_idx):
    print("\n🎲 Nova Rodada")
    baralho = criar_baralho()
    carta_meio = baralho.popleft()
    manilha = definir_manilha(carta_meio)
    print(f'Carta do meio: {carta_meio} → Manilha: {manilha}')

    maos = {j:[baralho.popleft() for _ in range(n_cartas)] for j in jogadores}
    dealer = jogadores[dealer_idx]
    print(f"\n🃏 Dealer: Jogador {dealer}")

    idx_primeiro = (dealer_idx + 1) % len(jogadores)
    ordem_palpites = jogadores[idx_primeiro:] + jogadores[:idx_primeiro]

    if n_cartas == 1:
        print("\n🃏 Você NÃO pode ver sua carta.")
        print("🔎 Cartas dos outros jogadores:")
        for j in jogadores[1:]:
            print(f'Jogador {j}: {maos[j][0]}')
    else:
        print("\n🃏 Suas cartas:")
        for i,c in enumerate(maos[1]): print(f'{i+1}: {c}')

    palpites, soma = {}, 0
    print("\n📢 Palpites:")
    for i, j in enumerate(ordem_palpites):
        ultimo = i == len(ordem_palpites)-1
        if j == 1:
            while True:
                try:
                    print(f"Palpites anteriores: {palpites}")
                    p = int(input(f"Jogador {j} (você) — 0-{n_cartas}: "))
                    if 0 <= p <= n_cartas and not (ultimo and soma+p == n_cartas):
                        break
                except ValueError: pass
                print("Palpite inválido ou proibido.")
        else:
            p = random.randint(0, n_cartas)
            if ultimo and soma + p == n_cartas:
                p = (p + 1) % (n_cartas + 1)
        palpites[j], soma = p, soma + p
    for j in jogadores: print(f'Jogador {j}: {palpites[j]}')

    vitorias = {j:0 for j in jogadores}
    ordem_jogada = deque(jogadores[jogadores.index(ordem_palpites[0]):]+jogadores[:jogadores.index(ordem_palpites[0])])
    multiplicador = 1

    for r in range(n_cartas):
        print(f"\n🔁 Jogada {r+1}")
        mesa, canceladas = [], []
        lead_strength, lead_cards = None, []
        for _ in jogadores:
            j_atual = ordem_jogada[0]
            carta = (maos[1].pop(0) if j_atual==1 and n_cartas==1 else
                     (maos[1].pop(int(input("Número da carta: "))-1) if j_atual==1 else maos[j_atual].pop(0)))
            mesa.append((j_atual,carta))
            print(f'Jog {j_atual} jogou {carta}')
            ordem_jogada.rotate(-1)
            st = carta.forca(manilha)
            if lead_strength is None or st > lead_strength:
                lead_strength, lead_cards = st, [(j_atual,carta)]
            elif st == lead_strength:
                canceladas += lead_cards + [(j_atual,carta)]
                lead_strength, lead_cards = None, []
                print("⚠️ Empate: cartas canceladas imediatamente.")
        if lead_cards:
            vencedor = lead_cards[0][0]
            vitorias[vencedor] += multiplicador
            multiplicador = 1
            ordem_jogada = deque(jogadores[jogadores.index(vencedor):]+jogadores[:jogadores.index(vencedor)])
            print(f'✅ Jogador {vencedor} venceu com {lead_cards[0][1]}')
        else:
            rodada_final = r == n_cartas-1
            if rodada_final:
                carta_venc = max(canceladas, key=lambda x: ORDEM_NAIPE_DESEMPATE[x[1].naipe])
                vencedor = carta_venc[0]
                vitorias[vencedor] += multiplicador
                print(f'🏁 Naipe decide: Jog {vencedor} vence com {carta_venc[1]}')
                multiplicador = 1
            else:
                multiplicador += 1
                ultimo = mesa[-1][0]
                ordem_jogada = deque(jogadores[jogadores.index(ultimo):]+jogadores[:jogadores.index(ultimo)])
                print("🔄 Sem vencedor → multiplicador +1")

    print("\n📊 Vitórias finais:")
    for j in jogadores:
        vidas[j] -= abs(vitorias[j]-palpites[j])
        print(f'Jog {j}: {vitorias[j]} vitórias | Palpite {palpites[j]} → vidas = {vidas[j]}')

    mortos = [j for j,v in vidas.items() if v <= 0]
    if mortos:
        print("\n💀 Jogadores eliminados:", ", ".join(map(str,mortos)), ". Fim de jogo.")
        return False
    return True

class FodinhaGame:
    def __init__(self, player_ids, initial_lives=3):
        self.jogadores = player_ids
        self.initial_lives = initial_lives
        self.vidas = {j: initial_lives for j in self.jogadores}
        
        self.dealer_idx_global = random.randint(0, len(self.jogadores) - 1) # Overall game dealer index
        self.cartas_global = 1 # Overall game card count progression
        self.crescendo_global = True # Overall game card count direction
        self.max_cartas_global = len(VALORES) * len(NAIPES) // len(self.jogadores) if self.jogadores else 0
        self.game_over_global = False

        # --- Round-specific state ---
        self.round_phase = None # e.g., "waiting_palpites", "waiting_card_play", "round_over"
        self.dealer_rodada_atual = None
        self.n_cartas_rodada_atual = 0
        self.carta_meio_rodada_atual = None
        self.manilha_rodada_atual = None
        self.maos_rodada_atual = {}
        
        self.ordem_palpites_rodada_atual = deque()
        self.palpites_feitos_rodada_atual = {}
        self.soma_palpites_rodada_atual = 0
        self.jogador_da_vez_palpite = None
        
        self.vitorias_rodada_atual = {j: 0 for j in self.jogadores}
        self.cartas_na_mesa_rodada_atual = [] # Stores (player, card) tuples for the current trick
        self.historico_cartas_rodada = {} # Stores all cards played in the round: {player_id: [card_str, ...]}
        self.jogador_da_vez_acao = None # Player whose turn it is to play a card or make a palpite
        self.truco_multiplier = 1 # For future truco implementation
        self.rodada_atual_num_tricks = 0 # How many tricks played in current round

    def start_new_round(self):
        if self.game_over_global:
            return False # Game is over

        self.round_phase = "waiting_palpites"
        self.dealer_rodada_atual = self.jogadores[self.dealer_idx_global]
        self.n_cartas_rodada_atual = self.cartas_global

        baralho = criar_baralho()
        self.carta_meio_rodada_atual = baralho.popleft()
        self.manilha_rodada_atual = definir_manilha(self.carta_meio_rodada_atual)
        
        self.maos_rodada_atual = {j: [baralho.popleft() for _ in range(self.n_cartas_rodada_atual)] for j in self.jogadores}
        
        idx_primeiro_palpite = (self.dealer_idx_global + 1) % len(self.jogadores)
        ordem_palpites_list = self.jogadores[idx_primeiro_palpite:] + self.jogadores[:idx_primeiro_palpite]
        self.ordem_palpites_rodada_atual = deque(ordem_palpites_list)
        
        self.palpites_feitos_rodada_atual = {}
        self.soma_palpites_rodada_atual = 0
        self.vitorias_rodada_atual = {j: 0 for j in self.jogadores} # Reset trick wins for the round
        self.rodada_atual_num_tricks = 0
        self.truco_multiplier = 1
        self.cartas_na_mesa_rodada_atual = [] # Clear table for new round
        self.historico_cartas_rodada = {p_id: [] for p_id in self.jogadores} # Reset history for new round

        if self.ordem_palpites_rodada_atual:
            self.jogador_da_vez_acao = self.ordem_palpites_rodada_atual.popleft()
        else: # Should not happen with >0 players
            self.jogador_da_vez_acao = None
            self.round_phase = "error" # Or handle appropriately
        
        print(f"🎲 Nova Rodada Iniciada. Dealer: {self.dealer_rodada_atual}, Cartas: {self.n_cartas_rodada_atual}, Manilha: {self.manilha_rodada_atual}")
        print(f"Mãos: {self.maos_rodada_atual}")
        print(f"Primeiro a palpitar: {self.jogador_da_vez_acao}")
        return True

    def submit_palpite(self, player_id, palpite):
        if self.round_phase != "waiting_palpites" or player_id != self.jogador_da_vez_acao:
            return {"success": False, "error": "Não é sua vez de palpitar ou fase incorreta."}

        try:
            palpite_num = int(palpite)
        except ValueError:
            return {"success": False, "error": "Palpite deve ser um número."}

        if not (0 <= palpite_num <= self.n_cartas_rodada_atual):
            return {"success": False, "error": f"Palpite deve ser entre 0 e {self.n_cartas_rodada_atual}."}

        # Regra do último palpite (dealer não pode somar igual ao número de cartas)
        is_ultimo_a_palpitar = not self.ordem_palpites_rodada_atual and (len(self.palpites_feitos_rodada_atual) == len(self.jogadores) - 1)

        if is_ultimo_a_palpitar and (self.soma_palpites_rodada_atual + palpite_num == self.n_cartas_rodada_atual):
            return {"success": False, "error": "Último palpite não pode fazer a soma igual ao número de cartas."}

        self.palpites_feitos_rodada_atual[player_id] = palpite_num
        self.soma_palpites_rodada_atual += palpite_num
        print(f"Palpite de {player_id}: {palpite_num}. Palpites feitos: {self.palpites_feitos_rodada_atual}")

        if self.ordem_palpites_rodada_atual:
            self.jogador_da_vez_acao = self.ordem_palpites_rodada_atual.popleft()
        else: # Todos palpitaram
            self.jogador_da_vez_acao = None # Or set to first player for playing cards
            self.round_phase = "waiting_card_play" # Transition to next phase
            # Determine who plays the first card (usually player after dealer or winner of last trick if applicable)
            # For now, let's set it based on who was first to bet for simplicity of starting card play.
            # This needs to follow actual game rules for who starts playing.
            idx_primeiro_palpite = (self.dealer_idx_global + 1) % len(self.jogadores)
            self.jogador_da_vez_acao = self.jogadores[idx_primeiro_palpite] # Placeholder for actual play order start
            print(f"Todos palpitaram. Próxima fase: Jogar cartas. Começa: {self.jogador_da_vez_acao}")


        return {"success": True, "next_player_to_bet": self.jogador_da_vez_acao if self.round_phase == "waiting_palpites" else None, "all_palpites_done": self.round_phase == "waiting_card_play"}

    # Implement card playing logic
    def submit_card_play(self, player_id, card_index):
        if self.round_phase != "waiting_card_play" or player_id != self.jogador_da_vez_acao:
            return {"success": False, "error": "Não é sua vez de jogar ou fase incorreta."}
        
        # Validate card_index
        if player_id not in self.maos_rodada_atual:
            return {"success": False, "error": f"Jogador {player_id} não tem cartas para jogar."}
            
        player_hand = self.maos_rodada_atual[player_id]
        if not player_hand:
            return {"success": False, "error": f"Jogador {player_id} não tem cartas para jogar."}
            
        if card_index < 0 or card_index >= len(player_hand):
            return {"success": False, "error": f"Índice de carta inválido: {card_index}"}
        
        # Get the played card and remove it from hand
        card_played = player_hand.pop(card_index)
        print(f"Jogador {player_id} jogou a carta {card_played}")
        
        # Add card to mesa_rodada_atual with player who played it
        self.cartas_na_mesa_rodada_atual.append((player_id, card_played))
        # Add to round history
        if player_id in self.historico_cartas_rodada:
            self.historico_cartas_rodada[player_id].append(str(card_played))
        else: # Should not happen if initialized correctly in start_new_round
            self.historico_cartas_rodada[player_id] = [str(card_played)]
        
        # Determine next player
        next_player_idx = (self.jogadores.index(player_id) + 1) % len(self.jogadores)
        self.jogador_da_vez_acao = self.jogadores[next_player_idx]
        
        # Check if this completes the trick (everyone played a card)
        trick_completed = len(self.cartas_na_mesa_rodada_atual) == len(self.jogadores)
        trick_winner = None
        round_over = False
        
        if trick_completed:
            # Determine the winner of the trick
            trick_winner = self._determine_trick_winner()
            
            # Update state for next trick
            self.rodada_atual_num_tricks += 1
            self.cartas_na_mesa_rodada_atual = []
            
            # Set winner as first to play in next trick
            self.jogador_da_vez_acao = trick_winner
            
            # Check if round is over (all tricks played)
            if self.rodada_atual_num_tricks >= self.n_cartas_rodada_atual:
                # Calculate round results
                round_over = True
                game_continues = self._calculate_round_results()
                
                if not game_continues:
                    # Game is over
                    return {
                        "success": True, 
                        "trick_completed": trick_completed,
                        "trick_winner": trick_winner,
                        "round_over": round_over,
                        "game_over": True
                    }
        
        return {
            "success": True, 
            "trick_completed": trick_completed,
            "trick_winner": trick_winner,
            "round_over": round_over
        }
        
    def _determine_trick_winner(self):
        """Determine winner of the current trick based on card strengths and manilha rules."""
        if not self.cartas_na_mesa_rodada_atual:
            return None
            
        print(f"Determining winner for trick: {self.cartas_na_mesa_rodada_atual}")
        
        # Find highest card based on manilha rules
        highest_strength = -1
        current_winners = []
        
        for player_id, card in self.cartas_na_mesa_rodada_atual:
            card_strength = card.forca(self.manilha_rodada_atual)
            
            if card_strength > highest_strength:
                highest_strength = card_strength
                current_winners = [(player_id, card)]
            elif card_strength == highest_strength:
                current_winners.append((player_id, card))
        
        # If there's only one winner, return player ID
        if len(current_winners) == 1:
            winner_id = current_winners[0][0]
            winner_card = current_winners[0][1]
            print(f"Player {winner_id} wins the trick with {winner_card}")
            self.vitorias_rodada_atual[winner_id] += self.truco_multiplier  # Award points based on multiplier
            self.truco_multiplier = 1  # Reset multiplier
            return winner_id
            
        # If there's a tie, handle based on rules
        print(f"Tie between cards: {current_winners}")
        
        # For the last trick, resolve by naipe
        if self.rodada_atual_num_tricks == self.n_cartas_rodada_atual - 1:
            # Find highest naipe
            best_naipe_player = None
            best_naipe_value = -1
            
            for player_id, card in current_winners:
                naipe_value = ORDEM_NAIPE_DESEMPATE[card.naipe]
                if naipe_value > best_naipe_value:
                    best_naipe_value = naipe_value
                    best_naipe_player = player_id
                    
            print(f"Last trick tie resolved by naipe. Winner: {best_naipe_player}")
            self.vitorias_rodada_atual[best_naipe_player] += self.truco_multiplier
            self.truco_multiplier = 1
            return best_naipe_player
        
        # For non-last tricks, no winner, increase multiplier
        print(f"No winner for this trick. Increasing multiplier to {self.truco_multiplier + 1}")
        self.truco_multiplier += 1
        
        # Next player is the last who played in the trick
        return self.cartas_na_mesa_rodada_atual[-1][0]

    def _calculate_round_results(self):
        # This function will be called after all cards in a round are played
        # It replaces the scoring logic from the end of old simular_rodada
        print("\n📊 Calculando resultados da rodada...")
        for j_id in self.jogadores:
            diff = abs(self.vitorias_rodada_atual.get(j_id, 0) - self.palpites_feitos_rodada_atual.get(j_id, -1)) # -1 if palpite somehow missing
            self.vidas[j_id] -= diff
            print(f"Jogador {j_id}: Vitórias {self.vitorias_rodada_atual.get(j_id,0)}, Palpite {self.palpites_feitos_rodada_atual.get(j_id,'N/A')} → Vidas: {self.vidas[j_id]}")

        mortos = [j for j, v in self.vidas.items() if v <= 0]
        if mortos:
            print("\n💀 Jogadores eliminados:", ", ".join(map(str, mortos)), ". Fim de jogo.")
            self.game_over_global = True
            self.round_phase = "game_over"
            return False # Indicates game is over

        # Update global game state for the next round
        self.cartas_global += 1 if self.crescendo_global else -1
        if self.cartas_global >= self.max_cartas_global:
            self.crescendo_global = False
            self.cartas_global = self.max_cartas_global # Adjust to play max_cartas then decrease
            if self.n_cartas_rodada_atual == self.max_cartas_global : # if we just played max cards
                 self.cartas_global = self.max_cartas_global -1


        elif self.cartas_global < 1: # Should be 1
            self.crescendo_global = True
            self.cartas_global = 1 # Adjust to play 1 then increase
            if self.n_cartas_rodada_atual == 1 and not self.crescendo_global: # if we just played 1 card going down
                 self.cartas_global = 2


        self.dealer_idx_global = (self.dealer_idx_global + 1) % len(self.jogadores)
        self.round_phase = "round_over" # Ready for a new round to be started
        return True # Indicates game continues

    def get_game_state(self):
        # Sensitive information like full hands of other players should be filtered by the server
        # before sending to a specific client.
        # For now, this sends more than it should for simplicity of backend.
        return {
            'players': self.jogadores,
            'lives': self.vidas,
            'current_dealer_global': self.jogadores[self.dealer_idx_global], # Overall game dealer
            'cards_next_round_global': self.cartas_global, # Cards for next round
            'game_over_global': self.game_over_global,
            
            # Round-specific state
            'round_phase': self.round_phase,
            'dealer_rodada_atual': self.dealer_rodada_atual,
            'n_cartas_rodada_atual': self.n_cartas_rodada_atual,
            'carta_meio_rodada_atual': str(self.carta_meio_rodada_atual) if self.carta_meio_rodada_atual else None,
            'manilha_rodada_atual': self.manilha_rodada_atual,
            'maos_rodada_atual': {p: [str(c) for c in hand] for p, hand in self.maos_rodada_atual.items()}, # Convert cards to string for serialization
            'palpites_feitos_rodada_atual': self.palpites_feitos_rodada_atual,
            'soma_palpites_rodada_atual': self.soma_palpites_rodada_atual,
            'jogador_da_vez_acao': self.jogador_da_vez_acao, # Player whose turn it is for current action
            'vitorias_rodada_atual': self.vitorias_rodada_atual, # Trick wins in current round
            'cartas_na_mesa_rodada_atual': [(p, str(c)) for p, c in self.cartas_na_mesa_rodada_atual], # Cards on table for current trick
            'historico_cartas_rodada': self.historico_cartas_rodada # All cards played in the round
        }
        
    def get_player_game_state(self, player_id):
        """
        Returns game state filtered according to what the specific player should see.
        Implements the card visibility rules:
        - In 1-card rounds during palpite phase: Players can't see their own card but can see all others'
        - In 1-card rounds during card play phase: Players can see all cards including their own
        - In 2+ card rounds: Players can only see their own cards
        """
        # Start with the base game state
        game_state = self.get_game_state()
        
        # Debug what we're starting with
        print(f"[DEBUG] get_player_game_state for {player_id}, n_cartas={self.n_cartas_rodada_atual}, phase={self.round_phase}")
        print(f"[DEBUG] Original maos_rodada_atual: {game_state['maos_rodada_atual']}")
        
        # Apply card visibility rules - filter maos_rodada_atual
        filtered_hands = {}
        
        if self.n_cartas_rodada_atual == 1:
            # In 1-card rounds with special visibility rules
            if self.round_phase == "waiting_palpites":
                # During palpite phase: Hide player's own card but show others'
                for p, hand in game_state['maos_rodada_atual'].items():
                    if p == player_id:
                        # Hide the player's own card during betting
                        filtered_hands[p] = ["HIDDEN"]
                        print(f"[DEBUG] Hiding {player_id}'s own card in 1-card round during palpite phase")
                    else:
                        # Show other players' cards
                        filtered_hands[p] = hand
                        print(f"[DEBUG] Showing {p}'s card to {player_id}: {hand}")
            else:
                # During card play or other phases: Show all cards including player's own
                filtered_hands = game_state['maos_rodada_atual']
                print(f"[DEBUG] Showing all cards including own in 1-card round during {self.round_phase} phase")
        else:
            # In 2+ card rounds, only show player's own cards
            for p in self.jogadores:
                if p == player_id:
                    # Show the player's own hand
                    filtered_hands[p] = game_state['maos_rodada_atual'].get(p, [])
                    print(f"[DEBUG] Showing {player_id}'s own cards in multi-card round: {filtered_hands[p]}")
                else:
                    # Hide other players' cards, but indicate count
                    cards_count = len(game_state['maos_rodada_atual'].get(p, []))
                    filtered_hands[p] = ["HIDDEN"] * cards_count
                    print(f"[DEBUG] Hiding {p}'s {cards_count} cards from {player_id}")
        
        # Replace the hands in the game state
        game_state['maos_rodada_atual'] = filtered_hands
        print(f"[DEBUG] Final filtered hands for {player_id}: {filtered_hands}")
        
        # Add metadata about what the player can see based on current phase
        game_state['can_see_own_cards'] = (self.n_cartas_rodada_atual > 1) or (self.round_phase != "waiting_palpites")
        game_state['can_see_others_cards'] = self.n_cartas_rodada_atual == 1
        
        return game_state

# --- This part is for local command-line testing if needed, not directly used by server ---
if __name__ == "__main__":
    # Example usage for testing FodinhaGame directly (won't use simular_rodada)
    player_ids_test = ["P1", "P2", "P3"]
    game = FodinhaGame(player_ids_test, initial_lives=3)
    
    # Start a new round
    game.start_new_round()
    print("\n--- Current Game State after starting round ---")
    print(game.get_game_state())

    # Simulate submitting palpites
    while game.round_phase == "waiting_palpites" and game.jogador_da_vez_acao:
        current_bettor = game.jogador_da_vez_acao
        # In a real scenario, this palpite would come from player input
        # For testing, let's make a random valid palpite
        test_palpite = random.randint(0, game.n_cartas_rodada_atual)
        
        is_last_to_bet_for_rule = (len(game.palpites_feitos_rodada_atual) == len(game.jogadores) - 1) and not game.ordem_palpites_rodada_atual

        if is_last_to_bet_for_rule and (game.soma_palpites_rodada_atual + test_palpite == game.n_cartas_rodada_atual):
             test_palpite = (test_palpite + 1) % (game.n_cartas_rodada_atual + 1) # Ensure it's different
             if is_last_to_bet_for_rule and (game.soma_palpites_rodada_atual + test_palpite == game.n_cartas_rodada_atual): # if still same, try another
                  test_palpite = (test_palpite + 1) % (game.n_cartas_rodada_atual + 1)


        print(f"Simulating palpite for {current_bettor}: {test_palpite}")
        result = game.submit_palpite(current_bettor, test_palpite)
        print(f"Submit palpite result: {result}")
        if not result["success"]:
            print(f"Error submitting palpite: {result.get('error')}")
            # Try a different palpite if the random one was invalid (e.g. dealer sum rule)
            if "Último palpite não pode fazer a soma igual" in result.get('error',''):
                 for p_try in range(game.n_cartas_rodada_atual + 1):
                      if not (is_last_to_bet_for_rule and (game.soma_palpites_rodada_atual + p_try == game.n_cartas_rodada_atual)):
                           print(f"Retrying palpite for {current_bettor} with {p_try}")
                           result_retry = game.submit_palpite(current_bettor, p_try)
                           print(f"Submit palpite retry result: {result_retry}")
                           if result_retry["success"]: break
                 else:
                      print("Could not find a valid palpite for dealer in test.")
                      break # Break if can't resolve
            else: # Other error
                 break 


    print("\n--- Current Game State after all palpites ---")
    print(game.get_game_state())
    
    # Placeholder for simulating card play and round completion
    # game._calculate_round_results() # This would be called after card playing phase.
    # print("\n--- Current Game State after calculating results ---")
    # print(game.get_game_state())

    # Test card progression logic
    # game.start_new_round() # To setup for next theoretical round state
    # print(f"Cards for next round would be: {game.cartas_global}")

# Remove the old procedural game loop from __main__ as it's not compatible with the class structure
# if __name__ == "__main__":
#     jogadores, vidas = [1,2,3,4], {j:3 for j in range(1,5)}
#     dealer_idx, cartas, crescendo = random.randint(0,3), 1, True
#     while simular_rodada(jogadores, cartas, vidas, dealer_idx): # This simular_rodada is the old one
#         cartas += 1 if crescendo else -1
#         max_cartas = len(VALORES)*len(NAIPES)//len(jogadores)
#         if cartas >= max_cartas: crescendo, cartas = False, cartas-1
#         elif cartas <= 1:        crescendo, cartas = True,  cartas+1
#         dealer_idx = (dealer_idx+1)%4



