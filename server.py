import socket
import threading
import random
import json
import time
import os

class GameServer:
    def __init__(self):
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.host = os.getenv('HOST', '0.0.0.0')  # Render compatible
        self.port = int(os.getenv('PORT', '10000'))
        self.server.bind((self.host, self.port))
        self.server.listen()
        
        self.rooms = {}
        self.clients = {}
        
        print(f"Server started on {self.host}:{self.port}")
    
    def broadcast(self, room_id, message, exclude_client=None):
        if room_id in self.rooms:
            for client in self.rooms[room_id]['players']:
                if client != exclude_client:
                    try:
                        client.send(message.encode('utf-8'))
                    except:
                        self.remove_client(client)
    
    def remove_client(self, client):
        if client in self.clients:
            room_id = self.clients[client]['room']
            if room_id in self.rooms and client in self.rooms[room_id]['players']:
                self.rooms[room_id]['players'].pop(client)
                self.broadcast(room_id, json.dumps({
                    'type': 'player_left',
                    'name': self.clients[client]['name']
                }))
                if len(self.rooms[room_id]['players']) == 0:
                    self.rooms.pop(room_id)
            self.clients.pop(client)
        client.close()
    
    def handle_client(self, client, address):
        try:
            info_data = client.recv(1024).decode('utf-8')
            info = json.loads(info_data)
            player_name = info.get('name', 'Player')
            room_id = info.get('room', 'default')
            password = info.get('password', '')
            
            if room_id in self.rooms and self.rooms[room_id]['password'] != password:
                client.send(json.dumps({
                    'type': 'error',
                    'message': 'Incorrect room password'
                }).encode('utf-8'))
                client.close()
                return
            
            shape = random.choice(['square', 'circle'])
            
            if room_id not in self.rooms:
                self.rooms[room_id] = {
                    'password': password,
                    'players': {}
                }
            
            self.clients[client] = {
                'room': room_id,
                'name': player_name,
                'shape': shape
            }
            
            self.rooms[room_id]['players'][client] = {
                'name': player_name,
                'shape': shape,
                'x': random.randint(50, 750),
                'y': random.randint(50, 550),
                'health': 100,
                'score': 0,
                'color': (
                    random.randint(50, 255),
                    random.randint(50, 255),
                    random.randint(50, 255)
                )
            }
            
            client.send(json.dumps({
                'type': 'welcome',
                'name': player_name,
                'shape': shape,
                'room': room_id,
                'color': self.rooms[room_id]['players'][client]['color']
            }).encode('utf-8'))
            
            self.broadcast(room_id, json.dumps({
                'type': 'player_joined',
                'name': player_name,
                'shape': shape,
                'x': self.rooms[room_id]['players'][client]['x'],
                'y': self.rooms[room_id]['players'][client]['y'],
                'color': self.rooms[room_id]['players'][client]['color']
            }), exclude_client=client)
            
            current_players = {}
            for c, info in self.rooms[room_id]['players'].items():
                if c != client:
                    current_players[info['name']] = {
                        'shape': info['shape'],
                        'x': info['x'],
                        'y': info['y'],
                        'health': info['health'],
                        'color': info['color']
                    }
            
            if current_players:
                client.send(json.dumps({
                    'type': 'current_players',
                    'players': current_players
                }).encode('utf-8'))
            
            while True:
                try:
                    data = client.recv(1024).decode('utf-8')
                    if not data:
                        break
                    
                    data = json.loads(data)
                    room_id = self.clients[client]['room']
                    
                    if data['type'] == 'move':
                        self.rooms[room_id]['players'][client]['x'] = data['x']
                        self.rooms[room_id]['players'][client]['y'] = data['y']
                        self.broadcast(room_id, json.dumps({
                            'type': 'player_moved',
                            'name': self.clients[client]['name'],
                            'x': data['x'],
                            'y': data['y']
                        }), exclude_client=client)
                    
                    elif data['type'] == 'shoot':
                        self.broadcast(room_id, json.dumps({
                            'type': 'bullet_fired',
                            'name': self.clients[client]['name'],
                            'x': data['x'],
                            'y': data['y'],
                            'dx': data['dx'],
                            'dy': data['dy'],
                            'color': self.rooms[room_id]['players'][client]['color']
                        }))
                    
                    elif data['type'] == 'hit':
                        hit_player = None
                        for c, info in self.rooms[room_id]['players'].items():
                            if info['name'] == data['target']:
                                hit_player = info
                                break
                        
                        if hit_player:
                            hit_player['health'] -= 25
                            
                            if hit_player['health'] <= 0:
                                hit_player['health'] = 100
                                hit_player['score'] -= 1
                                self.rooms[room_id]['players'][client]['score'] += 1
                                
                                hit_player['x'] = random.randint(50, 750)
                                hit_player['y'] = random.randint(50, 550)
                                
                                self.broadcast(room_id, json.dumps({
                                    'type': 'player_died',
                                    'killer': self.clients[client]['name'],
                                    'victim': data['target'],
                                    'x': hit_player['x'],
                                    'y': hit_player['y'],
                                    'scores': {
                                        p['name']: p['score'] for p in self.rooms[room_id]['players'].values()
                                    }
                                }))
                            else:
                                self.broadcast(room_id, json.dumps({
                                    'type': 'player_hit',
                                    'attacker': self.clients[client]['name'],
                                    'target': data['target'],
                                    'health': hit_player['health']
                                }))
                
                except Exception as e:
                    print(f"Error handling client {address}: {e}")
                    break
        
        except Exception as e:
            print(f"Client {address} disconnected unexpectedly: {e}")
        finally:
            self.remove_client(client)
    
    def run(self):
        while True:
            client, address = self.server.accept()
            print(f"New connection from {address}")
            threading.Thread(target=self.handle_client, args=(client, address)).start()

if __name__ == "__main__":
    server = GameServer()
    server.run()
