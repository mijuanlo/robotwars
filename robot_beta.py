import json
import sys
import random

def ai_logic(state):
    self_pos = state['self']
    enemies = state['enemies']

    if not enemies:
        return {'move': {'x': self_pos['x'], 'y': self_pos['y']}, 'shoot': False}

    target = enemies[0]
    return {
        'move': {
            'x': self_pos['x'] + (random.random() - 0.5)*5,
            'y': self_pos['y'] + (random.random() - 0.5)*5
        },
        'shoot': random.random() > 0.9
    }

while True:
    state = json.loads(sys.stdin.readline())
    command = ai_logic(state)
    print(json.dumps(command))
    sys.stdout.flush()