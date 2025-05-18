# backend/app.py
import uuid
from flask import Flask, request
from flask_socketio import SocketIO, join_room, leave_room, emit
from game_logic import FodinhaGame

app = Flask(__name__)
app.config["SECRET_KEY"] = "dev_secret_key_ πολυ-secure!" # Changed for a bit more entropy
socketio = SocketIO(app, cors_allowed_origins="*")

# ── Lobby & Game Management ───────────────────────────────────────────────────
# games will store: { room_id: {"players": [player_id_1, player_id_2, ...], "game_instance": FodinhaGame_instance, "host_sid": sid} }
games = {}
MAX_PLAYERS_PER_LOBBY = 6
sid_to_player_map = {} # {sid: {"room_id": room_id, "player_id": player_id}}

def generate_room_id():
    """Generates a short, unique room ID."""
    # Simple 6-char ID for now, you might want something more robust for production
    return uuid.uuid4().hex[:6].upper()

# Helper to get game and check validity
def get_valid_game(room_id, sid_check=None):
    if room_id not in games:
        if sid_check: emit("error", {"msg": f"Lobby {room_id} not found."}, room=sid_check)
        return None
    lobby_data = games[room_id]
    if not lobby_data or "game_instance" not in lobby_data:
        if sid_check: emit("error", {"msg": f"Game instance not found in lobby {room_id}."}, room=sid_check)
        return None
    return lobby_data["game_instance"]

# ── Health-check route ─────────────────────────────────────────────────────────
@app.route("/")
def status():
    return {"status": "Fodinha backend alive"}

# ── Socket handlers ────────────────────────────────────────────────────────────
@socketio.on("connect")
def on_connect():
    # Let the client know they're connected.
    # We don't assign them to a room here yet, they need to create or join.
    emit("connected", {"msg": "✨ Connected to Fodinha backend. Create or join a lobby!", "sid": request.sid})

@socketio.on("create_lobby")
def on_create_lobby(data):
    """
    Host creates a new lobby.
    data = {"player_id": "P1"}
    """
    player_id = data.get("player_id")
    if not player_id:
        emit("error", {"msg": "Player ID is required to create a lobby."}, room=request.sid)
        return

    room_id = generate_room_id()
    while room_id in games: # Ensure unique room_id
        room_id = generate_room_id()

    join_room(room_id)
    # Game instance created when game starts, not on lobby creation
    games[room_id] = {
        "players": [player_id],
        "game_instance": None, 
        "host_sid": request.sid # Store host SID
    }
    sid_to_player_map[request.sid] = {"room_id": room_id, "player_id": player_id}
    
    print(f"Lobby {room_id} created by {player_id} (SID: {request.sid}). Current lobbies: {list(games.keys())}")
    emit("lobby_created", {"room_id": room_id, "players": games[room_id]["players"], "your_player_id": player_id}, room=request.sid)
    socketio.emit("lobby_state", {"room_id": room_id, "players": games[room_id]["players"], "game_state": None}, room=room_id)


@socketio.on("join_lobby")
def on_join_lobby(data):
    """
    Player joins an existing lobby.
    data = {"room_id": "XYZ123", "player_id": "P2"}
    """
    room_id = data.get("room_id")
    player_id = data.get("player_id")

    if not room_id or not player_id:
        emit("error", {"msg": "Room ID and Player ID are required to join."}, room=request.sid)
        return

    if room_id not in games:
        emit("error", {"msg": f"Lobby {room_id} not found."}, room=request.sid)
        return

    if games[room_id]["game_instance"] is not None and games[room_id]["game_instance"].round_phase not in [None, "round_over", "game_over"] :
        emit("error", {"msg": f"Game in lobby {room_id} has already started."}, room=request.sid)
        return

    if len(games[room_id]["players"]) >= MAX_PLAYERS_PER_LOBBY and player_id not in games[room_id]["players"]:
        emit("error", {"msg": f"Lobby {room_id} is full."}, room=request.sid)
        return

    if player_id in games[room_id]["players"]:
        # Player is already in the lobby, perhaps rejoining.
        # Just ensure they are in the socket.io room and update them.
        join_room(room_id)
        current_game_state = None
        if games[room_id]["game_instance"]:
            current_game_state = games[room_id]["game_instance"].get_player_game_state(player_id)
        emit("lobby_state", {"room_id": room_id, "players": games[room_id]["players"], "game_state": current_game_state}, room=request.sid)
        print(f"Player {player_id} re-joined lobby {room_id}.")
        return

    join_room(room_id)
    games[room_id]["players"].append(player_id)
    sid_to_player_map[request.sid] = {"room_id": room_id, "player_id": player_id}
    print(f"Player {player_id} (SID: {request.sid}) joined/re-joined lobby {room_id}. Players: {games[room_id]['players']}")
    current_game_state = None
    if games[room_id]["game_instance"]:
        current_game_state = games[room_id]["game_instance"].get_player_game_state(player_id)
    emit("lobby_joined", {"room_id": room_id, "players": games[room_id]["players"], "your_player_id": player_id, "game_state": current_game_state}, room=request.sid)
    
    # For all players (including the one who just joined), send lobby update
    # This ensures everyone sees the updated player list
    socketio.emit("lobby_state", {"room_id": room_id, "players": games[room_id]["players"], "game_state": None}, room=room_id)


@socketio.on("start_game")
def on_start_game(data):
    """
    Host starts the game in their lobby.
    data = {"room_id": "XYZ123"} (player_id who is starting can be inferred from request.sid if needed,
                                   but good practice to ensure they are the host or in the lobby)
    """
    room_id = data.get("room_id")
    player_info = sid_to_player_map.get(request.sid)

    if not player_info or player_info["room_id"] != room_id:
        emit("error", {"msg": "You are not part of this lobby or invalid request."}, room=request.sid)
        return

    if room_id not in games:
        emit("error", {"msg": f"Lobby {room_id} not found."}, room=request.sid)
        return
    
    lobby_data = games[room_id]
    # Optional: Check if starter is the host: if request.sid != lobby_data["host_sid"]:

    # Corrected key from "game" to "game_instance"
    if lobby_data["game_instance"] and lobby_data["game_instance"].round_phase not in [None, "round_over", "game_over"]:
        emit("error", {"msg": "Game already running in this lobby."}, room=request.sid)
        return

    current_players_in_lobby = lobby_data["players"]
    if len(current_players_in_lobby) < 2: # Min players for Fodinha
        emit("error", {"msg": "Need at least 2 players to start."}, room=request.sid)
        # Also emit to room so everyone knows
        socketio.emit("lobby_message", {"msg": "Need at least 2 players to start."}, room=room_id)
        return

    # Create and store the game instance for this room
    lobby_data["game_instance"] = FodinhaGame(player_ids=current_players_in_lobby)
    
    # Initialize the first round immediately
    start_success = lobby_data["game_instance"].start_new_round()
    if not start_success:
        emit("error", {"msg": "Failed to start the game."}, room=request.sid)
        return
    
    print(f"Game started in lobby {room_id} with players: {current_players_in_lobby}")
    
    # Wait a moment to ensure all clients are ready
    # For each player, send their player-specific game state
    for player_id in current_players_in_lobby:
        # Find all SIDs associated with this player_id
        player_sids = [sid for sid, info in sid_to_player_map.items() 
                      if info.get("room_id") == room_id and info.get("player_id") == player_id]
        
        player_game_state = lobby_data["game_instance"].get_player_game_state(player_id)
        
        # Add room_id to the game state for client-side handling
        player_game_state["room_id"] = room_id
        
        if player_sids:
            # Send to each player's connected SID
            for sid in player_sids:
                print(f"Sending game_started to {player_id} with SID {sid}")
                socketio.emit("game_started", player_game_state, room=sid)
                # Also send a general update to ensure UI transitions
                socketio.emit("game_update", player_game_state, room=sid)
        else:
            print(f"Warning: No SIDs found for player {player_id}")
            
    print(f"Game started, personalized game states sent to {len(current_players_in_lobby)} players")


@socketio.on("next_round")
def on_next_round(data):
    """
    Data should include room_id to identify which game's round to advance.
    data = {"room_id": "XYZ123"}
    """
    room_id = data.get("room_id")
    requesting_player_sid = request.sid

    if not room_id:
        emit("error", {"msg": "Room ID is required for next round."}, room=requesting_player_sid)
        return
        
    if room_id not in games or games[room_id]["game_instance"] is None:
        emit("error", {"msg": "Game not started or lobby not found."}, room=requesting_player_sid)
        return

    current_game = games[room_id]["game_instance"]
    keep_playing = current_game.next_round()

    socketio.emit("round_update", current_game.get_game_state(), room=room_id)

    if not keep_playing:
        socketio.emit("game_over", current_game.get_game_state(), room=room_id)
        print(f"Game over in lobby {room_id}. Players: {games[room_id]['players']}")
        # Clean up the game for this room, players remain for a new game or leave
        games[room_id]["game_instance"] = None 
        # Optionally, you could clear players or remove the lobby if no one wants to play again
        # For now, players stay, lobby_state remains as is until they leave or start new game.

@socketio.on("disconnect")
def on_disconnect():
    disconnected_sid = request.sid
    print(f"Player with SID {disconnected_sid} disconnected.")
    
    # Find which room (if any) the disconnected player was in
    room_to_update = None
    player_id_that_left = None

    for r_id, data in list(games.items()): # Iterate over a copy for safe modification
        # This is tricky because we only have SID, not player_id directly mapped to SID here.
        # A robust solution would be to map SID to player_id upon join.
        # For now, let's assume we need to find player by SID in SocketIO rooms and then update our 'games' dict.

        # A simpler, but less direct approach for now:
        # If a game is active, we'd need to notify it. FodinhaGame doesn't support player removal mid-game easily.
        # Let's focus on lobby player list cleanup.

        # Find the player_id associated with this SID (this is a missing piece of state)
        # To simplify, we'll just remove the room if it becomes empty.
        # A proper implementation needs to map sids to player_ids upon join.

        # Let's try to find if this SID was in any of our game rooms
        sio_rooms = socketio.server.rooms(sid=disconnected_sid)
        
        found_player_id = None # We need a way to get the player_id from the SID

        for r_id_candidate in sio_rooms:
            if r_id_candidate in games: # If the SID was in one of our managed game rooms
                # Attempt to find and remove the player. This part is IMPROVISED as we don't store player_id by SID
                # This is a placeholder for a more robust player removal logic.
                # You'd ideally get player_id during "join_lobby" and store {sid: player_id} mapping.
                
                # For this iteration, if a player disconnects from a room,
                # we'll just print a message. Proper removal requires SID-to-PlayerID mapping.
                print(f"SID {disconnected_sid} was in room {r_id_candidate}. Manual cleanup of player list might be needed if game not robust to it.")
                
                # A very basic cleanup: if a room has no one left in Socket.IO's view, try to remove it.
                # This is not perfect as player might still be in games[r_id_candidate]['players']
                # if we don't have their player_id to remove them.
                # A better disconnect handling is needed for robustness.

    # Simplified cleanup: remove empty lobbies
    for r_id, data in list(games.items()):
        # Get clients in a specific room
        clients_in_room = socketio.server.manager.get_participants(namespace='/', room=r_id)
        if not clients_in_room:
            print(f"Lobby {r_id} is empty, removing.")
            del games[r_id]
    else:
            # If someone disconnected, the remaining players should get an updated lobby_state.
            # This requires knowing which player_id left to remove them from games[r_id]['players'].
            # This part is deferred due to lack of SID-to-player_id mapping.
            pass

@socketio.on("submit_palpite_action")
def on_submit_palpite(data):
    """
    Player submits a palpite (bet).
    data = {"room_id": "XYZ123", "palpite": 2}
    """
    room_id = data.get("room_id")
    palpite = data.get("palpite")
    player_info = sid_to_player_map.get(request.sid)
    
    if not player_info or player_info["room_id"] != room_id:
        emit("action_error", {"msg": "You are not part of this lobby.", "room_id": room_id}, room=request.sid)
        return
        
    player_id = player_info["player_id"]
    game_instance = get_valid_game(room_id, request.sid)
    if not game_instance:
        return
    
    if game_instance.round_phase != "waiting_palpites":
        emit("action_error", {"msg": "Not in palpite phase.", "room_id": room_id}, room=request.sid)
        return
        
    if game_instance.jogador_da_vez_acao != player_id:
        emit("action_error", {"msg": "Not your turn to make a palpite.", "room_id": room_id}, room=request.sid)
        return
        
    result = game_instance.submit_palpite(player_id, palpite)
    
    if not result["success"]:
        emit("action_error", {"msg": result.get("error", "Unknown error processing palpite."), "room_id": room_id}, room=request.sid)
        return
    
    # Send personalized game state to each player in the room
    for pl_id in game_instance.jogadores:
        # Find all SIDs associated with this player
        player_sids = [sid for sid, info in sid_to_player_map.items() 
                     if info.get("room_id") == room_id and info.get("player_id") == pl_id]
        
        # Create personalized game state for this player
        player_game_state = game_instance.get_player_game_state(pl_id)
        player_game_state["event_type"] = "palpite_submitted"
        player_game_state["player_who_bade"] = player_id
        player_game_state["palpite_value"] = palpite
        player_game_state["room_id"] = room_id
        
        # Debug logging for card visibility
        print(f"Player {pl_id} game state - cards: {player_game_state['maos_rodada_atual']}")
        print(f"Is 1-card round: {player_game_state['n_cartas_rodada_atual'] == 1}, Can see others: {player_game_state.get('can_see_others_cards', False)}")
        
        # Send to all SIDs for this player
        for sid in player_sids:
            socketio.emit("game_update", player_game_state, room=sid)
    
    # If all palpites are done, transition to card playing phase
    if result.get("all_palpites_done"):
        for pl_id in game_instance.jogadores:
            player_sids = [sid for sid, info in sid_to_player_map.items() 
                          if info.get("room_id") == room_id and info.get("player_id") == pl_id]
            
            player_game_state = game_instance.get_player_game_state(pl_id)
            player_game_state["event_type"] = "all_palpites_completed"
            player_game_state["room_id"] = room_id
            
            for sid in player_sids:
                socketio.emit("game_update", player_game_state, room=sid)
        
    # If there's a next player to make a palpite, send them a prompt
    if result.get("next_player_to_bet"):
        next_player = result["next_player_to_bet"]
        next_player_sids = [sid for sid, info in sid_to_player_map.items() 
                           if info.get("room_id") == room_id and info.get("player_id") == next_player]
        
        for sid in next_player_sids:
            player_game_state = game_instance.get_player_game_state(next_player)
            player_game_state["jogador_da_vez_acao"] = next_player
            player_game_state["room_id"] = room_id
            socketio.emit("prompt_palpite", player_game_state, room=sid)

@socketio.on("submit_card_action")
def on_submit_card(data):
    """
    Player plays a card.
    data = {"room_id": "XYZ123", "card_index": 0}
    """
    room_id = data.get("room_id")
    card_index = data.get("card_index")
    player_info = sid_to_player_map.get(request.sid)
    
    if not player_info or player_info["room_id"] != room_id:
        emit("action_error", {"msg": "You are not part of this lobby.", "room_id": room_id}, room=request.sid)
        return
        
    player_id = player_info["player_id"]
    game_instance = get_valid_game(room_id, request.sid)
    if not game_instance:
        return
    
    if game_instance.round_phase != "waiting_card_play":
        emit("action_error", {"msg": "Not in card playing phase.", "room_id": room_id}, room=request.sid)
        return
        
    if game_instance.jogador_da_vez_acao != player_id:
        emit("action_error", {"msg": "Not your turn to play a card.", "room_id": room_id}, room=request.sid)
        return
        
    result = game_instance.submit_card_play(player_id, card_index)
    
    if not result["success"]:
        emit("action_error", {"msg": result.get("error", "Unknown error processing card play."), "room_id": room_id}, room=request.sid)
        return
    
    # Send personalized game state to each player in the room
    for pl_id in game_instance.jogadores:
        # Find all SIDs associated with this player
        player_sids = [sid for sid, info in sid_to_player_map.items() 
                     if info.get("room_id") == room_id and info.get("player_id") == pl_id]
        
        # Create personalized game state for this player
        player_game_state = game_instance.get_player_game_state(pl_id)
        player_game_state["event_type"] = "card_played"
        player_game_state["player_who_played"] = player_id
        player_game_state["room_id"] = room_id
        
        # Send to all SIDs for this player
        for sid in player_sids:
            socketio.emit("game_update", player_game_state, room=sid)
    
    # If trick is completed, send update
    if result.get("trick_completed"):
        trick_winner = result.get("trick_winner")
        
        for pl_id in game_instance.jogadores:
            player_sids = [sid for sid, info in sid_to_player_map.items() 
                         if info.get("room_id") == room_id and info.get("player_id") == pl_id]
            
            player_game_state = game_instance.get_player_game_state(pl_id)
            player_game_state["trick_winner"] = trick_winner
            player_game_state["event_type"] = "trick_completed"
            player_game_state["room_id"] = room_id
            
            for sid in player_sids:
                socketio.emit("game_update", player_game_state, room=sid)
    
    # If round is over, send results
    if result.get("round_over"):
        for pl_id in game_instance.jogadores:
            player_sids = [sid for sid, info in sid_to_player_map.items() 
                         if info.get("room_id") == room_id and info.get("player_id") == pl_id]
            
            player_game_state = game_instance.get_player_game_state(pl_id)
            player_game_state["event_type"] = "round_over"
            player_game_state["room_id"] = room_id
            
            for sid in player_sids:
                socketio.emit("round_results", player_game_state, room=sid)
        
    # If there's a next player to play a card, send them a prompt
    if game_instance.round_phase == "waiting_card_play" and game_instance.jogador_da_vez_acao:
        next_player = game_instance.jogador_da_vez_acao
        next_player_sids = [sid for sid, info in sid_to_player_map.items() 
                          if info.get("room_id") == room_id and info.get("player_id") == next_player]
        
        for sid in next_player_sids:
            player_game_state = game_instance.get_player_game_state(next_player)
            player_game_state["jogador_da_vez_acao"] = next_player
            player_game_state["room_id"] = room_id
            socketio.emit("prompt_card_play", player_game_state, room=sid)

@socketio.on("request_next_round_action")
def on_request_next_round(data):
    """
    Host requests to start the next round.
    data = {"room_id": "XYZ123"}
    """
    room_id = data.get("room_id")
    player_info = sid_to_player_map.get(request.sid)
    
    if not player_info or player_info["room_id"] != room_id:
        emit("action_error", {"msg": "You are not part of this lobby.", "room_id": room_id}, room=request.sid)
        return
        
    player_id = player_info["player_id"]
    lobby_data = games.get(room_id)
    
    if not lobby_data:
        emit("action_error", {"msg": f"Lobby {room_id} not found.", "room_id": room_id}, room=request.sid)
        return
        
    if request.sid != lobby_data.get("host_sid"):
        emit("action_error", {"msg": "Only the host can start the next round.", "room_id": room_id}, room=request.sid)
        return
        
    game_instance = lobby_data.get("game_instance")
    if not game_instance:
        emit("action_error", {"msg": "No game instance found.", "room_id": room_id}, room=request.sid)
        return
        
    if game_instance.round_phase not in ["round_over", "game_over"]:
        emit("action_error", {"msg": "Current round is not over yet.", "room_id": room_id}, room=request.sid)
        return
        
    # If the game is over (all players eliminated), create a new game instance
    if game_instance.game_over_global:
        lobby_data["game_instance"] = FodinhaGame(player_ids=lobby_data["players"])
        game_instance = lobby_data["game_instance"]
        
    # Start a new round
    success = game_instance.start_new_round()
    
    if not success:
        emit("action_error", {"msg": "Failed to start new round.", "room_id": room_id}, room=request.sid)
        return
    
    # Send personalized game state to each player in the room
    for pl_id in game_instance.jogadores:
        # Find all SIDs associated with this player
        player_sids = [sid for sid, info in sid_to_player_map.items() 
                     if info.get("room_id") == room_id and info.get("player_id") == pl_id]
        
        # Create personalized game state for this player
        player_game_state = game_instance.get_player_game_state(pl_id)
        player_game_state["event_type"] = "next_round_started"
        player_game_state["room_id"] = room_id
        
        # Send to all SIDs for this player
        for sid in player_sids:
            socketio.emit("game_update", player_game_state, room=sid)
    
    # Send prompt to first player to make a palpite
    if game_instance.round_phase == "waiting_palpites" and game_instance.jogador_da_vez_acao:
        first_player = game_instance.jogador_da_vez_acao
        player_sids = [sid for sid, info in sid_to_player_map.items() 
                     if info.get("room_id") == room_id and info.get("player_id") == first_player]
        
        player_game_state = game_instance.get_player_game_state(first_player)
        player_game_state["room_id"] = room_id
        
        for sid in player_sids:
            socketio.emit("prompt_palpite", player_game_state, room=sid)

# ── Launch locally or on Render ────────────────────────────────────────────────
if __name__ == "__main__":
    print("Starting Fodinha backend with dynamic lobbies...")
    # use_reloader=True is good for dev, but can cause issues with SocketIO sometimes
    # debug=True is also for dev
    socketio.run(app, host="0.0.0.0", port=5050, debug=True, use_reloader=False)

