import socket
import threading
import pickle
import time

HOST = "localhost"
PORT = 5555

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.bind((HOST, PORT))
server.listen()
print("[SERVER STARTED] Waiting for connections...")

rooms = {}
lock = threading.Lock()

def handle_client(conn, addr):
    try:
        data = pickle.loads(conn.recv(1024))
        if isinstance(data, dict) and data.get("request") == "room_list":
            conn.send(pickle.dumps(list(rooms.keys())))
            conn.close()
            return

        username = data.get("username")
        conn.send(b"ok")
        room_name = pickle.loads(conn.recv(1024))

        with lock:
            if room_name not in rooms:
                rooms[room_name] = {
                    "players": {},
                    "usernames": {},
                    "bullets": [],
                    "scores": {},
                    "respawn_times": {}
                }

            player_id = len(rooms[room_name]["players"])
            rooms[room_name]["players"][player_id] = [100 + player_id * 60, 100, 100]  # x, y, health
            rooms[room_name]["usernames"][player_id] = username
            rooms[room_name]["scores"][player_id] = 0
            rooms[room_name]["respawn_times"][player_id] = 0

        conn.send(pickle.dumps((
            player_id,
            rooms[room_name]["players"],
            rooms[room_name]["usernames"],
            rooms[room_name]["scores"]
        )))

        while True:
            try:
                data = pickle.loads(conn.recv(4096))
                if not data:
                    break

                pid = data["id"]
                player = data["player"]
                new_bullets = data["bullets"]
                wants_respawn = data.get("respawn", False)

                with lock:
                    if pid in rooms[room_name]["players"]:
                        if wants_respawn and rooms[room_name]["players"][pid][2] <= 0:
                            # Respawn player
                            rooms[room_name]["players"][pid] = [100 + pid * 60, 100, 100]
                            rooms[room_name]["respawn_times"][pid] = 0
                        elif rooms[room_name]["players"][pid][2] > 0:
                            # Only update position if alive
                            rooms[room_name]["players"][pid][:2] = player[:2]

                    # Add new bullets (only from alive players)
                    for b in new_bullets:
                        if b["owner"] in rooms[room_name]["players"] and rooms[room_name]["players"][b["owner"]][2] > 0:
                            rooms[room_name]["bullets"].append(b)

                    # Update bullets and check collisions
                    updated_bullets = []
                    for bullet in rooms[room_name]["bullets"]:
                        bullet["x"] += bullet["dx"]
                        bullet["y"] += bullet["dy"]
                        hit = False

                        # Check if bullet is out of bounds
                        if not (0 <= bullet["x"] <= 800 and 0 <= bullet["y"] <= 600):
                            hit = True
                        else:
                            # Check player collisions
                            for target_id, target in rooms[room_name]["players"].items():
                                if target_id != bullet["owner"] and target[2] > 0:  # Only hit alive players
                                    if (target[0] < bullet["x"] < target[0] + 50 and 
                                        target[1] < bullet["y"] < target[1] + 50):
                                        target[2] -= 10
                                        if target[2] <= 0:
                                            rooms[room_name]["scores"][bullet["owner"]] += 1
                                            rooms[room_name]["respawn_times"][target_id] = time.time() * 1000  # Current time in ms
                                        hit = True
                                        break
                        
                        if not hit:
                            updated_bullets.append(bullet)

                    rooms[room_name]["bullets"] = updated_bullets

                    # Send game state to client
                    conn.send(pickle.dumps((
                        rooms[room_name]["players"],
                        rooms[room_name]["bullets"],
                        rooms[room_name]["usernames"],
                        rooms[room_name]["scores"],
                        rooms[room_name]["respawn_times"]
                    )))
            except (pickle.PickleError, KeyError) as e:
                print(f"[ERROR] Data error with {addr}: {e}")
                break

    except Exception as e:
        print(f"[ERROR] {addr}: {e}")
    finally:
        with lock:
            if room_name in rooms:
                if player_id in rooms[room_name]["players"]:
                    del rooms[room_name]["players"][player_id]
                    del rooms[room_name]["usernames"][player_id]
                    del rooms[room_name]["scores"][player_id]
                    if player_id in rooms[room_name]["respawn_times"]:
                        del rooms[room_name]["respawn_times"][player_id]
        print(f"[DISCONNECT] {username} left {room_name}")
        conn.close()

while True:
    conn, addr = server.accept()
    threading.Thread(target=handle_client, args=(conn, addr)).start()
