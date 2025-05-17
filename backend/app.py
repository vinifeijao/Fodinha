from flask import Flask, request
from flask_socketio import SocketIO, join_room, emit
from game_logic import FodinhaGame

# ── Flask + Socket.IO basic setup ───────────────────────────────────────────────
app = Flask(__name__)
app.config["SECRET_KEY"] = "change_me_later"
socketio = SocketIO(app, cors_allowed_origins="*")        # allow local tests

# ── In-memory store (single lobby for now) ──────────────────────────────────────
ROOM_ID  = "default"          # think of this as the game table
players  = []                 # list of player IDs who joined
games    = {}                 # {ROOM_ID: FodinhaGame}

# ── Simple “is server alive?” route ─────────────────────────────────────────────
@app.route("/")
def index():
    return {"status": "Fodinha backend alive"}

# ── Socket events ───────────────────────────────────────────────────────────────
@socketio.on("connect")
def handle_connect():
    emit("connected", {"msg": "✨ Connected to Fodinha backend"})

@socketio.on("join")
def handle_join(data):
    """
    Client sends → {"player_id": "P1"}
    """
    pid = data["player_id"]
    join_room(ROOM_ID)
    if pid not in players:
        players.append(pid)
    emit("lobby_state", {"players": players}, room=ROOM_ID)

@socketio.on("start_game")
def handle_start_game(data):
    """
    Host sends → {"num_players": 2}
    """
    if ROOM_ID in games:
        emit("error", {"msg": "Game already running"}, room=request.sid)
        return

    num_players = data.get("num_players", len(players))
    games[ROOM_ID] = FodinhaGame(num_players)  # FodinhaGame(2) for two-player test
    emit("game_started", games[ROOM_ID].get_game_state(), room=ROOM_ID)

@socketio.on("next_round")
def handle_next_round():
    game = games.get(ROOM_ID)
    if not game:
        emit("error", {"msg": "Game not started"}, room=request.sid)
        return

    keep_playing = game.next_round()
    emit("round_update", game.get_game_state(), room=ROOM_ID)

    if not keep_playing:
        emit("game_over", game.get_game_state(), room=ROOM_ID)
        del games[ROOM_ID]

# ── Run server ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # Port 5050 avoids clashes with other dev servers
    socketio.run(app, host="0.0.0.0", port=5050, debug=True, use_reloader=False)

