import json
import math
import sys

def ai_logic(state):
    self_pos = state['self']
    enemies = state['enemies']

    if not enemies:
        return {'move': {'x': self_pos['x'], 'y': self_pos['y']}, 'shoot': False}

    target = enemies[0]
    dx = target['x'] - self_pos['x']
    dy = target['y'] - self_pos['y']

    return {
        'move': {
            'x': self_pos['x'] + dx * 0.1,
            'y': self_pos['y'] + dy * 0.1
        },
        'shoot': math.hypot(dx, dy) < 200
    }

while True:
    state = json.loads(sys.stdin.readline())
    self_pos = state['self']
    enemies = state['enemies']

    if enemies:
        enemy = enemies[0]
        dx = enemy['x'] - self_pos['x']
        dy = enemy['y'] - self_pos['y']
        angle = math.atan2(dy, dx)  # Ángulo hacia el enemigo

        # Enviar comando para rotar el cañón
        command = {'rotate': angle}
        print(json.dumps(command))
        sys.stdout.flush()