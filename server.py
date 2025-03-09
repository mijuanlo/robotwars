import sys
import random
import math
import time
import logging
logging.basicConfig(level=logging.DEBUG)
from PySide2.QtWidgets import (QApplication, QMainWindow, QGraphicsView,
                             QGraphicsScene, QGraphicsEllipseItem,
                             QGraphicsTextItem, QGraphicsRectItem,
                             QGraphicsLineItem, QVBoxLayout, QWidget,
                             QPushButton, QLabel, QHBoxLayout, QDockWidget,
                             QGraphicsColorizeEffect, QGraphicsItem)
from PySide2.QtGui import QColor, QBrush, QRadialGradient, QPen
from PySide2.QtCore import Qt, QTimer, QPointF
import json
import subprocess
from threading import Thread
from queue import Queue

WIDTH = 800
HEIGHT = 600
ROBOT_RADIUS = 25
CANNON_LENGTH = 12
PROJECTILE_SPEED = 5  # Reducida velocidad de proyectil
PROJECTILE_RADIUS = 3
MOVE_SPEED = 40  # Velocidad de movimiento reducida
SHOOT_COOLDOWN = 500  # Milisegundos entre disparos
FUEL_CAPACITY = 100
ENERGY_CAPACITY = 100

class Explosion(QGraphicsEllipseItem):
    def __init__(self, x, y, scene):
        super().__init__(-10, -10, 20, 20)
        self.setPos(x, y)
        self.setZValue(2)

        # Crear gradiente radial para efecto de explosión
        gradient = QRadialGradient(0, 0, 30)
        gradient.setColorAt(0, QColor('#FFA500'))
        gradient.setColorAt(0.5, QColor('#FF4500'))
        gradient.setColorAt(1, QColor(255, 255, 255, 0))
        self.setBrush(gradient)

        # Configurar animación
        self.timer = QTimer()
        self.timer.timeout.connect(self.animate)
        self.timer.start(50)
        self.scale_factor = 1.0
        self.alpha = 1.0
        scene.addItem(self)

        self.anim_group = QParallelAnimationGroup()
        self.scale_anim = QPropertyAnimation(self, b"scale")
        self.scale_anim.setDuration(1000)
        self.scale_anim.setKeyValueAt(0, 1)
        self.scale_anim.setKeyValueAt(1, 2)

        self.opacity_anim = QPropertyAnimation(self, b"opacity")
        self.opacity_anim.setDuration(1000)
        self.opacity_anim.setKeyValueAt(0, 1)
        self.opacity_anim.setKeyValueAt(1, 0)

        self.anim_group.addAnimation(self.scale_anim)
        self.anim_group.addAnimation(self.opacity_anim)
        self.anim_group.finished.connect(self.deleteLater)
        self.anim_group.start()

    def animate(self):
        # Aumentar escala y reducir opacidad
        self.scale_factor *= 1.3
        self.alpha *= 0.8
        self.setScale(self.scale_factor)
        self.setOpacity(self.alpha)

        # Eliminar explosión cuando sea invisible
        if self.alpha < 0.1:
            self.scene().removeItem(self)
            self.timer.stop()

class Barrier(QGraphicsRectItem):
    def __init__(self, x, y, width, height):
        super().__init__(x, y, width, height)
        self.setBrush(QColor('#4A4A4A'))
        self.setPen(QPen(Qt.black, 3))

class Projectile(QGraphicsEllipseItem):
    def __init__(self, x, y, angle, shooter):
        super().__init__(0, 0, PROJECTILE_RADIUS*2, PROJECTILE_RADIUS*2)
        self.angle = angle
        self.shooter = shooter
        self.setPos(x, y)
        self.setBrush(QColor('red'))
        self.setPen(Qt.NoPen)
        self.setZValue(1)

        self.timer = QTimer()
        self.timer.timeout.connect(self.move)
        self.timer.start(50)

    def move(self):
        new_pos = self.pos() + QPointF(
            math.cos(self.angle) * PROJECTILE_SPEED,
            math.sin(self.angle) * PROJECTILE_SPEED
        )

        if not (0 < new_pos.x() < WIDTH and 0 < new_pos.y() < HEIGHT):
            self.scene().removeItem(self)
            self.timer.stop()
            return

        for item in self.scene().items():
            if isinstance(item, Robot) and item != self.shooter:
                if math.hypot(new_pos.x() - item.x(), new_pos.y() - item.y()) < ROBOT_RADIUS:
                    # Reducir daño de 20 a 5 por impacto
                    item.health = max(0, item.health - 5)
                    item.update_health()
                    self.scene().removeItem(self)
                    self.timer.stop()
                    return
            if isinstance(item, Barrier):
                barrier_rect = item.rect().translated(item.pos())
                closest_x = max(barrier_rect.left(), min(self.x(), barrier_rect.right()))
                closest_y = max(barrier_rect.top(), min(self.y(), barrier_rect.bottom()))
                dx = self.x() - closest_x
                dy = self.y() - closest_y
                if dx**2 + dy**2 < PROJECTILE_RADIUS**2:
                    self.scene().removeItem(self)
                    self.timer.stop()
                    return
        self.setPos(new_pos)

class Robot(QGraphicsEllipseItem):
    def __init__(self, x, y, color, name, scene, ai_script):
        super().__init__(-ROBOT_RADIUS, -ROBOT_RADIUS, ROBOT_RADIUS*2, ROBOT_RADIUS*2)
        self.name = name
        self.color = color
        self.locked = False
        self.health = 100
        self.fuel = FUEL_CAPACITY  # Nuevo atributo
        self.energy = ENERGY_CAPACITY  # Nuevo atributo
        self.last_shot_time = 0  # Para controlar cadencia
        self.velocity = 2
        self.angle = 0
        self.ai_script = ai_script
        self.command_queue = Queue()
        self.process = None
        self.scene_ref = scene  # Add this line to store the scene reference
        self.setPos(x,y)
        self.scene_ref.addItem(self)  # Use self.scene_ref instead of scene

        self.fuel_bar_bg = QGraphicsRectItem(
            -ROBOT_RADIUS, ROBOT_RADIUS + 20,
            ROBOT_RADIUS*2, 6, self
        )
        self.fuel_bar_bg.setBrush(QColor(30, 30, 30))

        self.fuel_bar = QGraphicsRectItem(
            -ROBOT_RADIUS, ROBOT_RADIUS + 20,
            ROBOT_RADIUS*2, 6, self
        )
        self.fuel_bar.setBrush(QColor('#45B39D'))

        self.energy_bar_bg = QGraphicsRectItem(
            -ROBOT_RADIUS, ROBOT_RADIUS + 30,
            ROBOT_RADIUS*2, 6, self
        )
        self.energy_bar_bg.setBrush(QColor(30, 30, 30))

        self.energy_bar = QGraphicsRectItem(
            -ROBOT_RADIUS, ROBOT_RADIUS + 30,
            ROBOT_RADIUS*2, 6, self
        )
        self.energy_bar.setBrush(QColor('#85C1E9'))

        # Crear cañón
        self.cannon = QGraphicsLineItem(ROBOT_RADIUS, 0, ROBOT_RADIUS + CANNON_LENGTH, 0, self)
        self.cannon.setPen(QPen(Qt.black, 3))
        # Fondo de la barra
        self.health_bar_bg = QGraphicsRectItem(
            -ROBOT_RADIUS, ROBOT_RADIUS + 10,
            ROBOT_RADIUS*2, 8, self
        )
        self.health_bar_bg.setBrush(QColor(50, 50, 50))
        self.setFlag(QGraphicsItem.ItemIsMovable)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges)
        self.setCursor(Qt.OpenHandCursor)
        # Barra de salud activa
        self.health_bar = QGraphicsRectItem(
            -ROBOT_RADIUS, ROBOT_RADIUS + 10,
            ROBOT_RADIUS*2, 8, self
        )
        self.health_bar.setBrush(QColor('#FF5722'))
        self.health_bar.setPen(QPen(Qt.black, 1))

        # --- Agregar nombre ---
        self.text = QGraphicsTextItem(name, self)
        self.text.setDefaultTextColor(Qt.black)
        self.text.setPos(-self.text.boundingRect().width()/2, -ROBOT_RADIUS - 25)
        self.start_ai_process()

    def update_status_bars(self):
        # Actualizar barra de combustible
        self.fuel_bar.setRect(
            -ROBOT_RADIUS, ROBOT_RADIUS + 20,
            ROBOT_RADIUS*2 * (self.fuel / FUEL_CAPACITY), 6
        )
        # Actualizar barra de energía
        self.energy_bar.setRect(
            -ROBOT_RADIUS, ROBOT_RADIUS + 30,
            ROBOT_RADIUS*2 * (self.energy / ENERGY_CAPACITY), 6
        )
        # Regenerar energía gradualmente
        if self.energy < ENERGY_CAPACITY:
            self.energy = min(ENERGY_CAPACITY, self.energy + 0.1)

    def terminate(self):
        if hasattr(self, 'process') and self.process:
            self.process.terminate()
            self.process = None
        if hasattr(self, 'command_queue'):
            self.command_queue.queue.clear()
    # Nuevo método para detectar colisiones
    def collides_with(self, new_pos):
        for item in self.scene().items():
            if isinstance(item, Robot) and item != self:
                if (new_pos - item.pos()).manhattanLength() < 2*ROBOT_RADIUS:
                    return True
            elif isinstance(item, Barrier):
                if self.boundingRect().translated(new_pos).intersects(item.boundingRect().translated(item.pos())):
                    return True
        return False

    def update_health(self):
        """Actualiza la barra de salud y el cañón"""
        if self.health <= 30:
            self.health_bar.setBrush(QColor('#FF0000'))
        elif self.health <= 70:
            self.health_bar.setBrush(QColor('#FFA500'))
        else:
            self.health_bar.setBrush(QColor('#00FF00'))
        self.health_bar.setRect(
            -ROBOT_RADIUS, ROBOT_RADIUS + 10,
            ROBOT_RADIUS * 2 * (self.health / 100), 8
        )
        self.update_cannon()

    def shoot(self):
        """Dispara un proyectil desde el cañón"""
        if self.energy < 20 or time.time() - self.last_shot_time < 0.5:
            return  # Requiere 20 de energía y 0.5s entre disparos
        self.energy -= 20
        self.last_shot_time = time.time()
        current_time = time.time() * 1000
        if current_time - self.last_shot_time < SHOOT_COOLDOWN:
            return  # No disparar si no ha pasado el cooldown
        if self.energy < 20:  # Coste de energía por disparo
            return
        self.energy -= 20
        self.last_shot_time = current_time

        if self.health <= 0:
            return
        # Calcular posición del cañón
        cannon_end = QPointF(
            (ROBOT_RADIUS + CANNON_LENGTH) * math.cos(self.angle),
            (ROBOT_RADIUS + CANNON_LENGTH) * math.sin(self.angle)
        )
        # Crear proyectil
        projectile = Projectile(
            self.pos().x() + cannon_end.x(),
            self.pos().y() + cannon_end.y(),
            self.angle,
            self
        )
        self.scene_ref.addItem(projectile)

    def start_ai_process(self):
        self.process = subprocess.Popen(
            [sys.executable, self.ai_script],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True,
            bufsize=1
        )
        Thread(target=self.read_commands, daemon=True).start()

    def read_commands(self):
        while True:
            try:
                output = self.process.stdout.readline().strip()
                if output:
                    logging.debug(f"Robot {self.name} received: {output}")
                    self.command_queue.put(json.loads(output))
            except Exception as e:
                logging.error(f"Error reading commands: {str(e)}")
                break

    def get_state(self):
        robot_pos = self.pos()
        state = {
            'self': {
                'x': robot_pos.x(),
                'y': robot_pos.y(),
                'health': self.health,
                'angle': self.angle
            },
            'enemies': [],
            'barriers': []
        }

        # Agregar distancia a enemigos
        for r in self.battle_field.robots:
            if r != self:
                dx = r.x() - robot_pos.x()
                dy = r.y() - robot_pos.y()
                dist = math.hypot(dx, dy)
                state['enemies'].append({
                    'x': r.x(),
                    'y': r.y(),
                    'health': r.health,
                    'distance': dist  # Agregar distancia
                })

        return state

    def update_cannon(self):
        """Actualiza la rotación del cañón según el ángulo actual"""
        self.cannon.setRotation(math.degrees(self.angle))
    def mousePressEvent(self, event):
        self.setCursor(Qt.ClosedHandCursor)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        self.setCursor(Qt.OpenHandCursor)
        super().mouseReleaseEvent(event)
    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionChange and self.scene():
            new_pos = value
            # Corregir posición si hay colisiones
            if self.collides_with(new_pos):
                return self.pos()  # Revertir movimiento
        return super().itemChange(change, value)
    def rotate_cannon(self, target_angle):
        self.angle = target_angle
        self.update_cannon()
class BattleField(QGraphicsView):
    def __init__(self):
        super().__init__()
        self.scene = QGraphicsScene()
        self.setScene(self.scene)
        self.setFixedSize(WIDTH, HEIGHT)
        self.setSceneRect(0, 0, WIDTH, HEIGHT)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.game_ended = False

        robot1 = Robot(
            random.randint(ROBOT_RADIUS, WIDTH//2 - ROBOT_RADIUS),
            random.randint(ROBOT_RADIUS, HEIGHT//2 - ROBOT_RADIUS),
            '#FF6B6B', 'Alpha', self.scene, 'robot_alpha.py'
        )
        robot2 = Robot(
            random.randint(WIDTH//2 + ROBOT_RADIUS, WIDTH - ROBOT_RADIUS),
            random.randint(HEIGHT//2 + ROBOT_RADIUS, HEIGHT - ROBOT_RADIUS),
            '#4ECDC4', 'Beta', self.scene, 'robot_beta.py'
        )

        self.robots = [ robot1 , robot2 ]
        # Añadir barreras
        self.barriers = [
            Barrier(200, 150, 100, 20),
            Barrier(500, 400, 20, 100),
            Barrier(300, 300, 150, 30)
        ]
        for barrier in self.barriers:
            self.scene.addItem(barrier)

        # Temporizador para movimiento automático (inicialmente detenido)
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_arena)

        # Asociar referencia a los robots
        for robot in self.robots:
            robot.battle_field = self

    def can_move(self):
        return self.fuel > 5  # Mínimo combustible para moverse

    def can_shoot(self):
        return self.energy >= 20 and time.time()*1000 - self.last_shot_time > SHOOT_COOLDOWN

    def update_arena(self):
        if self.game_ended:
            return

        for robot in self.robots:
            if robot.health > 0:
                # Decaimiento natural de vida
                # robot.health = max(0, robot.health - 0.005)
                # Regeneración de combustible
                #if robot.fuel < FUEL_CAPACITY:
                #    robot.fuel = min(FUEL_CAPACITY, robot.fuel + 0.05)
                # Actualizar barras
                robot.update_health()
                robot.update_status_bars()

        # Enviar estado a todos los robots
        for robot in self.robots:
            #if not robot.locked:
                #robot.health = max(0, robot.health - 0.02)  # Reducción más gradual
                #robot.update_health()

            if robot.health > 0:
                state = robot.get_state()
                json.dump(state, robot.process.stdin)
                robot.process.stdin.write('\n')
                robot.process.stdin.flush()

        # Ejecutar comandos de los robots
        for robot in self.robots:
            if robot.health > 0 and not robot.command_queue.empty():
                command = robot.command_queue.get()
                if 'move' in command:
                    self.execute_move(robot, command['move'])
                if 'shoot' in command and command['shoot']:
                    robot.shoot()
                if 'rotate' in command:  # Nuevo comando
                    robot.rotate_cannon(command['rotate'])
                if 'scan' in command:
                    radius = command['scan'].get('radius', 100)
                    robot.scan_radius = radius  # Almacenar radio de escaneo

        self.check_winner()

    def get_state(self):
        scan_radius = getattr(self, 'scan_radius', 0)
        robot_pos = self.pos()
        state = {
            'self': {
                'x': robot_pos.x(),
                'y': robot_pos.y(),
                'health': self.health,
                'angle': self.angle
            },
            'enemies': [],
            'barriers': []
        }

        # Detectar enemigos dentro del radio
        if scan_radius > 0:
            for r in self.battle_field.robots:
                if r == self:
                    continue
                dx = r.x() - robot_pos.x()
                dy = r.y() - robot_pos.y()
                dist = math.hypot(dx, dy)
                if scan_radius == 0 or dist <= scan_radius:
                    state['enemies'].append({
                        'x': r.x(),
                        'y': r.y(),
                        'health': r.health,
                        'distance': dist
                    })

        # Detectar barreras dentro del radio
        for barrier in self.battle_field.barriers:
            rect = barrier.rect().translated(barrier.pos())
            closest_x = max(rect.left(), min(robot_pos.x(), rect.right()))
            closest_y = max(rect.top(), min(robot_pos.y(), rect.bottom()))
            dist = math.hypot(robot_pos.x() - closest_x, robot_pos.y() - closest_y)
            if dist <= scan_radius:
                state['barriers'].append({
                    'x': closest_x,
                    'y': closest_y,
                    'width': rect.width(),
                    'height': rect.height(),
                    'distance': dist
                })

        if hasattr(self, 'scan_radius'):
            del self.scan_radius
        return state

    def execute_move(self, robot, target):
        if robot.health <= 0:
            return

        # Calcular distancia a mover
        dx = target['x'] - robot.x()
        dy = target['y'] - robot.y()
        distance = math.hypot(dx, dy)

        # Consumir combustible proporcional a la distancia
        robot.fuel = max(0, robot.fuel - distance * 0.1)

        # Limitar movimiento por velocidad
        if distance > MOVE_SPEED:
            angle = math.atan2(dy, dx)
            new_x = robot.x() + MOVE_SPEED * math.cos(angle)
            new_y = robot.y() + MOVE_SPEED * math.sin(angle)
        else:
            new_x = target['x']
            new_y = target['y']

        # Verificar límites ajustados por radio
        new_x = max(ROBOT_RADIUS, min(WIDTH - ROBOT_RADIUS, new_x))
        new_y = max(ROBOT_RADIUS, min(HEIGHT - ROBOT_RADIUS, new_y))

        new_pos = QPointF(new_x, new_y)
        if not robot.collides_with(new_pos):
            # Consumir combustible
            if robot.fuel > 0:
                robot.fuel = max(0, robot.fuel - distance*0.1)
                robot.setPos(new_pos)
                robot.angle = math.atan2(new_y - robot.y(), new_x - robot.x())
                robot.update_cannon()

    def check_winner(self):
        alive = [robot for robot in self.robots if robot.health > 0]
        if len(alive) == 1 and not self.game_ended:
            self.game_ended = True
            self.show_winner(alive[0])

    def show_winner(self, winner):
        # Detener todos los procesos
        self.timer.stop()
        for robot in self.robots:
            if hasattr(robot,'process'):
                robot.process.terminate()
                robot.process = None
            if hasattr(robot, 'command_queue'):
                robot.command_queue.queue.clear()
        #    robot.shoot_timer.stop()
        # self.scene.removeItem(self.winner_text)

        # Crear texto animado
        self.winner_text = QGraphicsTextItem(f"¡{winner.name} HA GANADO!")
        font = self.winner_text.font()
        font.setPointSize(40)
        self.winner_text.setFont(font)
        self.winner_text.setDefaultTextColor(QColor(255, 215, 0))
        self.winner_text.setPos(WIDTH/2 - self.winner_text.boundingRect().width()/2,
                                HEIGHT/2 - self.winner_text.boundingRect().height()/2)
        self.winner_text.setZValue(10)

        # Añadir efecto de brillo
        effect = QGraphicsColorizeEffect()
        effect.setColor(QColor(255, 215, 0))
        effect.setStrength(0.5)
        self.winner_text.setGraphicsEffect(effect)

        # Animación de escala
        self.winner_text.setScale(0.1)
        self.scene.addItem(self.winner_text)

        # Animación de pulso
        self.pulse_timer = QTimer()
        self.pulse_timer.timeout.connect(lambda: self.winner_text.setScale(
            1.5 if self.winner_text.scale() > 1 else 1))
        self.pulse_timer.start(500)

        # Desactivar interacciones
        for robot in self.robots:
            robot.setEnabled(False)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Robot Battle Arena")
        self.battle_field = BattleField()
        self.setCentralWidget(self.battle_field)

        # Panel de control
        control_widget = QWidget()
        control_layout = QHBoxLayout()

        # Botón de modo automático
        self.toggle_btn = QPushButton("Activar Automático")
        self.toggle_btn.setCheckable(True)
        self.toggle_btn.toggled.connect(self.toggle_automatic)
        control_layout.addWidget(self.toggle_btn)

        # Etiquetas de estado
        self.status_labels = []
        for robot in self.battle_field.robots:
            label = QLabel(f"{robot.name}: (0, 0) HP: 100%")
            label.setAlignment(Qt.AlignCenter)
            label.setStyleSheet("background: white; padding: 8px; border-radius: 8px;")
            self.status_labels.append(label)
            control_layout.addWidget(label)

        control_widget.setLayout(control_layout)
        self.dock = QDockWidget("Controles", self)
        self.dock.setWidget(control_widget)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.dock)

        # Temporizador de UI
        self.ui_timer = QTimer()
        self.ui_timer.timeout.connect(self.update_ui)
        self.ui_timer.start(100)

    def closeEvent(self, event):
        """Terminar todos los procesos al cerrar"""
        for robot in self.battle_field.robots:
            if hasattr(robot, 'process') and robot.process:
                robot.process.terminate()
        event.accept()

    def update_ui(self):
        """Actualiza la interfaz con los estados de los robots"""
        for i, robot in enumerate(self.battle_field.robots):
            if robot.health <= 0:
                status = "DESTRUIDO"
            else:
                pos = robot.pos()
                angle_deg = math.degrees(robot.angle) % 360
                status = (f"({pos.x():.0f}, {pos.y():.0f}) "
                        f"HP: {robot.health:.1f}% "
                        f"Ángulo: {angle_deg:.0f}°")
            # Acceder al label correspondiente mediante el índice
            self.status_labels[i].setText(f"{robot.name}: {status}")

    def toggle_automatic(self, checked):
        """Controla el modo automático"""
        if checked:
            self.battle_field.timer.start(50)
            self.toggle_btn.setText("Desactivar Automático")
        else:
            self.battle_field.timer.stop()
            self.toggle_btn.setText("Activar Automático")

    def keyPressEvent(self, event):
        """Manejo de teclas especiales"""
        if event.key() == Qt.Key_Escape:
            self.close()
        elif event.key() == Qt.Key_1:
            self.battle_field.robots[0].locked = not self.battle_field.robots[0].locked
        elif event.key() == Qt.Key_2:
            self.battle_field.robots[1].locked = not self.battle_field.robots[1].locked

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())