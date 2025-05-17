# simple_client.py
import sys, time, socketio, random

ROOM   = "demo"                    # change if you like
MY_ID  = sys.argv[1]               # pass a unique id per terminal

sio = socketio.Client()
@sio.event
def connect():
    print(f"[{MY_ID}] ✅ connected");          

@sio.on("connected")
def on_welcome(data):
    print(f"[{MY_ID}] {data}")

@sio.on("game_started")
def on_started(state):
    print(f"[{MY_ID}] 🎮 start:", state)

@sio.on("round_update")
def on_round(state):
    print(f"[{MY_ID}] 🃏 round:", state)

@sio.on("game_over")
def on_over(state):
    print(f"[{MY_ID}] 💀 game over", state)
    sio.disconnect()

@sio.event
def disconnect():
    print(f"[{MY_ID}] 🔌 bye!")

sio.connect("http://localhost:5050")
sio.emit("join", {"room_id": ROOM, "player_id": MY_ID})  # you’ll add this handler next
time.sleep(1)

# Player 1 will be the host that starts rounds
if MY_ID == "P1":
    num_players = 3                    # total clients you’ll launch
    sio.emit("start_game", {"room_id": ROOM, "num_players": num_players})
    time.sleep(1)
    for _ in range(10):                # play 10 rounds
        sio.emit("next_round", {"room_id": ROOM})
        time.sleep(0.5)
    print("[P1] done sending rounds")
    time.sleep(2)
    sio.disconnect()
else:
    sio.wait()                         # other players just listen
