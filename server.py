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
PROJECTILE_SPEED = 8
PROJECTILE_RADIUS = 3

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
                    item.health = max(0, item.health - 20)
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
        self.velocity = 2
        self.angle = 0
        self.ai_script = ai_script
        self.command_queue = Queue()
        self.process = None
        self.scene_ref = scene  # Add this line to store the scene reference
        self.setPos(x,y)
        self.scene_ref.addItem(self)  # Use self.scene_ref instead of scene
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
        return {
            'self': {
                'x': self.x(),
                'y': self.y(),
                'health': self.health,
                'angle': self.angle
            },
            'enemies': [{
                'x': r.x(),
                'y': r.y(),
                'health': r.health
            } for r in self.battle_field.robots if r != self]
        }

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

    def update_arena(self):
        if self.game_ended:
            return
        # Enviar estado a todos los robots
        for robot in self.robots:
            if not robot.locked:
                robot.health = max(0, robot.health - 0.02)  # Reducción más gradual
                robot.update_health()

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

        self.check_winner()

    def execute_move(self, robot, target):
        if robot.health <= 0:
            return

        # Validar coordenadas
        new_x = max(ROBOT_RADIUS, min(WIDTH - ROBOT_RADIUS, target.get('x', robot.x())))
        new_y = max(ROBOT_RADIUS, min(HEIGHT - ROBOT_RADIUS, target.get('y', robot.y())))

        # Lógica de movimiento basada en el comando recibido
        new_x = max(ROBOT_RADIUS, min(WIDTH - ROBOT_RADIUS, target['x']))
        new_y = max(ROBOT_RADIUS, min(HEIGHT - ROBOT_RADIUS, target['y']))

        # Verificar colisiones antes de mover
        new_pos = QPointF(new_x, new_y)
        if not robot.collides_with(new_pos):
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