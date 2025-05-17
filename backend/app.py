from flask import Flask, request
from flask_socketio import SocketIO, join_room, leave_room, emit
from game_logic import FodinhaGame

app = Flask(__name__)
app.config["SECRET_KEY"] = "dev_only_change_me"
socketio = SocketIO(app, cors_allowed_origins="*")  # * simplifies local tests

# --- In-memory lobby (single game for now) ---
LOBBY_ID = "default"
games = {}          # {room_id: FodinhaGame}

# -- HTTP route just to verify the server is up --
@app.route("/")
def index():
    return {"status": "Fodinha backend alive"}

# -- Socket events --
@socketio.on("connect")
def handle_connect():
    emit("connected", {"message": "Welcome to Fodinha!"})

@socketio.on("join")
def handle_join(data):
    """
    data = {"player_id": <int>}
    """
    pid = int(data["player_id"])
    join_room(LOBBY_ID)
    if LOBBY_ID not in games:
        games[LOBBY_ID] = FodinhaGame([pid])
    else:
        games[LOBBY_ID].players.append(pid)
    emit("lobby_state", {"players": games[LOBBY_ID].players}, room=LOBBY_ID)

# Add more events later: 'start_game', 'play_card', etc.

if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000, debug=True)
