import math
import json
import sys
import random

def calculate_distance(x1, y1, x2, y2):
    return math.hypot(x2 - x1, y2 - y1)

while True:
    state = json.loads(sys.stdin.readline())

    # Extraer información del estado
    self_x = state['self']['x']
    self_y = state['self']['y']
    enemies = state.get('enemies', [])
    angle = state['self']['angle']

    command = {}

    if enemies:
        # Encontrar enemigo más cercano
        closest = min(enemies, key=lambda e: e['distance'])
        dx = closest['x'] - self_x
        dy = closest['y'] - self_y
        target_angle = math.atan2(dy, dx)

        # Apuntar al enemigo
        command['rotate'] = target_angle

        # Disparar si está cerca
        if closest['distance'] < 150:
            command['shoot'] = True
    else:
        # Si no hay enemigos, explorar aleatoriamente
        if random.random() < 0.3:
            # Escanear área ampliada
            command['scan'] = {'radius': 300}
        else:
            # Movimiento aleatorio con dirección preferente
            direction = random.choice([0, math.pi/2, math.pi, 3*math.pi/2])
            new_x = self_x + 100 * math.cos(direction)
            new_y = self_y + 100 * math.sin(direction)
            command['move'] = {'x': new_x, 'y': new_y}

    # Enviar comando
    print(json.dumps(command))
    sys.stdout.flush()