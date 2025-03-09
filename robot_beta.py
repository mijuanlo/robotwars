import math
import json
import sys
import random

# Configuración
SCAN_RADIUS = 200
MOVE_SPEED = 80  # Unidades por movimiento
FIRE_RANGE = 150
AVOID_DISTANCE = 50
SEARCH_STEPS = 30

# Estado interno
searching = False
current_direction = None
steps_taken = 0

def calculate_distance(x1, y1, x2, y2):
    return math.hypot(x2 - x1, y2 - y1)

def find_closest_enemy(enemies):
    if not enemies:
        return None
    return min(enemies, key=lambda e: e['distance'])

def get_movement_direction(target_x, target_y, self_x, self_y):
    angle = math.atan2(target_y - self_y, target_x - self_x)
    return {
        'x': self_x + MOVE_SPEED * math.cos(angle),
        'y': self_y + MOVE_SPEED * math.sin(angle)
    }

def get_search_direction():
    global current_direction, steps_taken, searching
    if not searching or steps_taken >= SEARCH_STEPS:
        current_direction = random.uniform(0, 2*math.pi)
        steps_taken = 0
        searching = True
    steps_taken += 1
    return {
        'x': MOVE_SPEED * math.cos(current_direction),
        'y': MOVE_SPEED * math.sin(current_direction)
    }

while True:
    state = json.loads(sys.stdin.readline())

    self_info = state['self']
    enemies = state.get('enemies', [])
    barriers = state.get('barriers', [])

    command = {}

    if enemies:
        closest = find_closest_enemy(enemies)
        dx = closest['x'] - self_info['x']
        dy = closest['y'] - self_info['y']
        distance = closest['distance']
        angle = math.atan2(dy, dx)

        # Prioridad 1: Apuntar al enemigo
        command['rotate'] = angle

        # Prioridad 2: Disparar si está en rango
        if distance < FIRE_RANGE:
            command['shoot'] = True

        # Prioridad 3: Movimiento táctico
        if distance > FIRE_RANGE * 1.5:
            # Avanzar hacia el enemigo
            move_pos = get_movement_direction(closest['x'], closest['y'],
                                             self_info['x'], self_info['y'])
            command['move'] = move_pos
        elif self_info['health'] < 50 and distance < FIRE_RANGE * 0.8:
            # Retroceder si la salud es baja
            move_pos = get_movement_direction(self_info['x'] - dx,
                                             self_info['y'] - dy,
                                             self_info['x'], self_info['y'])
            command['move'] = move_pos

        searching = False  # Reiniciar búsqueda si encontramos enemigo

    else:
        # Modo búsqueda
        if random.random() < 0.7:
            command['scan'] = {'radius': SCAN_RADIUS}
        else:
            # Movimiento aleatorio con dirección persistente
            direction = get_search_direction()
            command['move'] = {
                'x': self_info['x'] + direction['x'],
                'y': self_info['y'] + direction['y']
            }

    # Evitar colisiones con barreras
    if barriers:
        closest_barrier = min(barriers, key=lambda b: b['distance'])
        if closest_barrier['distance'] < AVOID_DISTANCE:
            # Calcular dirección de evitación
            dx = closest_barrier['x'] - self_info['x']
            dy = closest_barrier['y'] - self_info['y']
            avoid_angle = math.atan2(-dy, -dx)
            command['move'] = {
                'x': self_info['x'] + MOVE_SPEED * math.cos(avoid_angle),
                'y': self_info['y'] + MOVE_SPEED * math.sin(avoid_angle)
            }

    print(json.dumps(command))
    sys.stdout.flush()