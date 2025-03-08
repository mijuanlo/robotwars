import sys
import random
import math
import time
from PySide2.QtWidgets import (QApplication, QMainWindow, QGraphicsView,
                             QGraphicsScene, QGraphicsEllipseItem,
                             QGraphicsTextItem, QGraphicsRectItem,
                             QGraphicsLineItem, QVBoxLayout, QWidget,
                             QPushButton, QLabel, QHBoxLayout, QDockWidget,
                             QGraphicsColorizeEffect)
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

# class Robot(QGraphicsEllipseItem):
#     def __init__(self, x, y, color, name, scene):
#         super().__init__(-ROBOT_RADIUS, -ROBOT_RADIUS, ROBOT_RADIUS*2, ROBOT_RADIUS*2)
#         self.name = name
#         self.color = color
#         self.locked = False
#         self.health = 100
#         self.velocity = 2
#         self.angle = 0
#         self.last_manual = 0
#         self.scene_ref = scene
#         self.setPos(x, y)
#         self.setFlag(QGraphicsEllipseItem.ItemIsMovable, False)
#         self.setAcceptHoverEvents(True)

#         # Añadir a la escena
#         scene.addItem(self)

#         # Diseño
#         gradient = QRadialGradient(0, 0, ROBOT_RADIUS)
#         gradient.setColorAt(0, QColor(255, 255, 255, 150))
#         gradient.setColorAt(1, QColor(color))
#         self.setBrush(QBrush(gradient))
#         self.setPen(Qt.NoPen)  # Eliminar borde negro

#         # Cañón
#         self.cannon = QGraphicsLineItem(ROBOT_RADIUS, 0,
#                                        ROBOT_RADIUS + CANNON_LENGTH, 0, self)
#         self.cannon.setPen(QPen(Qt.black, 3))

#         # Barra de salud
#         self.health_bar_bg = QGraphicsRectItem(
#             -ROBOT_RADIUS, ROBOT_RADIUS + 10,
#             ROBOT_RADIUS*2, 8, self
#         )
#         self.health_bar_bg.setBrush(QColor(50, 50, 50))

#         self.health_bar = QGraphicsRectItem(
#             -ROBOT_RADIUS, ROBOT_RADIUS + 10,
#             ROBOT_RADIUS*2, 8, self
#         )
#         self.health_bar.setBrush(QColor('#FF5722'))
#         self.health_bar.setPen(QPen(Qt.black, 1))

#         # Nombre
#         self.text = QGraphicsTextItem(name, self)
#         self.text.setDefaultTextColor(Qt.black)
#         self.text.setPos(-self.text.boundingRect().width()/2, -ROBOT_RADIUS - 25)

#         # Temporizador de disparo
#         self.shoot_timer = QTimer()
#         self.shoot_timer.timeout.connect(self.shoot)
#         self.shoot_timer.start(1000)

#         # Actualizar visualización
#         self.update_health()

#     def update_health(self):
#         self.health_bar.setRect(-ROBOT_RADIUS, ROBOT_RADIUS + 10,
#                                ROBOT_RADIUS*2*(self.health/100), 8)
#         self.update_cannon()

#         # Explosión
#         if self.health <= 0:
#             # Crear explosión
#             explosion = Explosion(self.x(), self.y(), self.scene())

#             # Eliminar robot
#             self.setVisible(False)
#             self.setEnabled(False)
#             self.shoot_timer.stop()

#             if hasattr(self, 'battle_field'):
#                 QTimer.singleShot(100, self.battle_field.check_winner)

#             # Programar eliminación completa después de la explosión
#             QTimer.singleShot(500, lambda: self.scene().removeItem(self))

#     def update_cannon(self):
#         self.cannon.setRotation(math.degrees(self.angle))

#     def shoot(self):
#         if self.health <= 0:
#             return

#         cannon_end = QPointF(
#             (ROBOT_RADIUS + CANNON_LENGTH) * math.cos(self.angle),
#             (ROBOT_RADIUS + CANNON_LENGTH) * math.sin(self.angle)
#         )

#         projectile = Projectile(
#             self.pos().x() + cannon_end.x(),
#             self.pos().y() + cannon_end.y(),
#             self.angle,
#             self
#         )
#         self.scene_ref.addItem(projectile)

#     # Métodos de interacción con ratón
#     def mousePressEvent(self, event):
#         if self.locked:
#             return

#         pos = event.pos()
#         distance = math.hypot(pos.x(), pos.y())

#         if ROBOT_RADIUS - 5 <= distance <= ROBOT_RADIUS + 5:
#             self.mode = 'rotate'
#             self.setCursor(Qt.ClosedHandCursor)
#             self.start_pos = event.scenePos()
#             self.drag_offset = event.pos()
#         else:
#             self.mode = 'move'
#             self.setCursor(Qt.ClosedHandCursor)
#             self.start_move_pos = event.scenePos()
#             self.original_pos = self.pos()

#         event.accept()
#         self.last_manual = time.time()

#     def mouseMoveEvent(self, event):
#         if self.locked:
#             return

#         if hasattr(self, 'mode'):
#             if self.mode == 'rotate':
#                 new_pos = event.scenePos() - self.drag_offset
#                 self.angle = math.atan2(new_pos.y() - self.scenePos().y(),
#                                         new_pos.x() - self.scenePos().x())
#                 self.update_cannon()

#             elif self.mode == 'move':
#                 delta = event.scenePos() - self.start_move_pos
#                 new_pos = self.original_pos + delta

#                 new_x = max(ROBOT_RADIUS, min(WIDTH - ROBOT_RADIUS, new_pos.x()))
#                 new_y = max(ROBOT_RADIUS, min(HEIGHT - ROBOT_RADIUS, new_pos.y()))

#                 # Verificar colisión con otros robots
#                 collision = False
#                 for item in self.scene_ref.items():
#                     if isinstance(item, Robot) and item != self:
#                         dx = new_x - item.x()
#                         dy = new_y - item.y()
#                         dist = math.hypot(dx, dy)
#                         if dist < 2*ROBOT_RADIUS:
#                             collision = True
#                             break

#                 # Si no hay colisión con robots, verificar barreras
#                 if not collision:
#                     for item in self.scene_ref.items():
#                         if isinstance(item, Barrier):
#                             barrier_rect = item.sceneBoundingRect()
#                             closest_x = max(barrier_rect.left(), min(new_x, barrier_rect.right()))
#                             closest_y = max(barrier_rect.top(), min(new_y, barrier_rect.bottom()))
#                             dx = new_x - closest_x
#                             dy = new_y - closest_y
#                             if dx**2 + dy**2 < ROBOT_RADIUS**2:
#                                 collision = True
#                                 break

#                 # Actualizar posicion si no hay colisiones
#                 if not collision:
#                     self.setPos(new_x, new_y)
#                     self.last_manual = time.time()

#             event.accept()

#     def mouseReleaseEvent(self, event):
#         if hasattr(self, 'mode'):
#             if self.mode == 'rotate':
#                 del self.start_pos
#                 del self.drag_offset
#             elif self.mode == 'move':
#                 del self.start_move_pos
#                 del self.original_pos
#             del self.mode
#             self.setCursor(Qt.OpenHandCursor)
#             self.update_cannon()
#         event.accept()

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
        self.scene_ref.addItem(self)  # Use self.scene_ref instead of scene
        # Crear cañón
        self.cannon = QGraphicsLineItem(ROBOT_RADIUS, 0,
                                       ROBOT_RADIUS + CANNON_LENGTH, 0, self)
        self.cannon.setPen(QPen(Qt.black, 3))
        self.start_ai_process()

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
                    self.command_queue.put(json.loads(output))
            except:
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
class BattleField(QGraphicsView):
    def __init__(self):
        super().__init__()
        self.scene = QGraphicsScene()
        self.setScene(self.scene)
        self.setFixedSize(WIDTH, HEIGHT)
        self.setSceneRect(0, 0, WIDTH, HEIGHT)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        # Añadir robots
        # self.robots = [
        #     Robot(random.randint(ROBOT_RADIUS, WIDTH - ROBOT_RADIUS),
        #           random.randint(ROBOT_RADIUS, HEIGHT - ROBOT_RADIUS),
        #           '#FF6B6B', 'Alpha', self.scene),
        #     Robot(random.randint(ROBOT_RADIUS, WIDTH - ROBOT_RADIUS),
        #           random.randint(ROBOT_RADIUS, HEIGHT - ROBOT_RADIUS),
        #           '#4ECDC4', 'Beta', self.scene)
        # ]
        self.robots = [
            Robot(100, 100, '#FF6B6B', 'Alpha', self.scene, 'robot_alpha.py'),
            Robot(700, 500, '#4ECDC4', 'Beta', self.scene, 'robot_beta.py')
        ]

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

    # def update_arena(self):
    #     for robot in self.robots:
    #         if robot.health <= 0:
    #             continue

    #         if not robot.locked and time.time() - robot.last_manual > 0.5:
    #             new_angle = random.uniform(0, 2*math.pi)
    #             new_pos = robot.pos() + QPointF(
    #                 math.cos(new_angle)*robot.velocity,
    #                 math.sin(new_angle)*robot.velocity
    #             )

    #             new_x = max(ROBOT_RADIUS, min(WIDTH - ROBOT_RADIUS, new_pos.x()))
    #             new_y = max(ROBOT_RADIUS, min(HEIGHT - ROBOT_RADIUS, new_pos.y()))
    #             collision = False

    #             # Verificar colisión con otros robots
    #             for other_robot in self.robots:
    #                 if other_robot != robot and other_robot.health > 0:
    #                     dx = new_x - other_robot.x()
    #                     dy = new_y - other_robot.y()
    #                     if math.hypot(dx, dy) < 2*ROBOT_RADIUS:
    #                         collision = True
    #                         break

    #             # Verificar colisión con barreras si no hay colisión con robots
    #             if not collision:
    #                 for item in self.scene.items():
    #                     if isinstance(item, Barrier):
    #                         barrier_rect = item.sceneBoundingRect()
    #                         closest_x = max(barrier_rect.left(), min(new_x, barrier_rect.right()))
    #                         closest_y = max(barrier_rect.top(), min(new_y, barrier_rect.bottom()))
    #                         dx = new_x - closest_x
    #                         dy = new_y - closest_y
    #                         if dx**2 + dy**2 < ROBOT_RADIUS**2:
    #                             collision = True
    #                             break

    #             # Actualizar posición si no hay colisiones
    #             if not collision:
    #                 robot.setPos(new_x, new_y)
    #                 robot.angle = math.atan2(new_y - robot.y(), new_x - robot.x())
    #                 robot.update_cannon()

    #         # Actualizar salud
    #         if not robot.locked:
    #             robot.health = max(0, robot.health - 0.05)
    #         robot.update_health()

    def update_arena(self):
        # Enviar estado a todos los robots
        for robot in self.robots:
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

    def execute_move(self, robot, target):
        # Lógica de movimiento basada en el comando recibido
        new_x = max(ROBOT_RADIUS, min(WIDTH - ROBOT_RADIUS, target['x']))
        new_y = max(ROBOT_RADIUS, min(HEIGHT - ROBOT_RADIUS, target['y']))
        robot.setPos(new_x, new_y)
        robot.angle = math.atan2(new_y - robot.y(), new_x - robot.x())
        robot.update_cannon()

    def check_winner(self):
        alive = [robot for robot in self.robots if robot.health > 0]
        if len(alive) == 1:
            self.show_winner(alive[0])

    def show_winner(self, winner):
        # Detener todos los procesos
        self.timer.stop()
        for robot in self.robots:
            robot.shoot_timer.stop()
        self.scene.removeItem(self.winner_text)

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

# class MainWindow(QMainWindow):
#     def __init__(self):
#         super().__init__()
#         self.setWindowTitle("Robot Battle Arena")
#         self.battle_field = BattleField()
#         self.setCentralWidget(self.battle_field)

#         # Panel de control
#         control_widget = QWidget()
#         control_layout = QHBoxLayout()

#         self.toggle_btn = QPushButton("Activar Automático")
#         self.toggle_btn.setCheckable(True)
#         self.toggle_btn.toggled.connect(self.toggle_automatic)

#         self.status_labels = []
#         for robot in self.battle_field.robots:
#             label = QLabel(f"{robot.name}: (0, 0) HP: 100% Ángulo: 0°")
#             label.setAlignment(Qt.AlignCenter)
#             label.setStyleSheet("background: white; padding: 8px; border-radius: 8px;")
#             self.status_labels.append(label)
#             control_layout.addWidget(label)

#         control_layout.addWidget(self.toggle_btn)
#         control_widget.setLayout(control_layout)

#         self.dock = QDockWidget("Controles", self)
#         self.dock.setWidget(control_widget)
#         self.dock.setFeatures(QDockWidget.NoDockWidgetFeatures)
#         self.addDockWidget(Qt.BottomDockWidgetArea, self.dock)

#         # Temporizador de UI
#         self.ui_timer = QTimer()
#         self.ui_timer.timeout.connect(self.update_ui)
#         self.ui_timer.start(100)

#         self.battle_field.winner_text = QGraphicsTextItem()

#     def update_ui(self):
#         for i, robot in enumerate(self.battle_field.robots):
#             angle_deg = math.degrees(robot.angle) % 360
#             self.status_labels[i].setText(
#                 f"{robot.name}: ({robot.x():.0f}, {robot.y():.0f}) "
#                 f"HP: {robot.health:.1f}% Ángulo: {angle_deg:.0f}° {'🔒' if robot.locked else ''}"
#             )

#     def toggle_automatic(self, checked):
#         if checked:
#             self.battle_field.timer.start(50)
#             self.toggle_btn.setText("Desactivar Automático")
#         else:
#             self.battle_field.timer.stop()
#             self.toggle_btn.setText("Activar Automático")

#     def keyPressEvent(self, event):
#         if event.key() == Qt.Key_Escape:
#             self.close()
#         elif event.key() == Qt.Key_1:
#             self.battle_field.robots[0].locked = not self.battle_field.robots[0].locked
#         elif event.key() == Qt.Key_2:
#             self.battle_field.robots[1].locked = not self.battle_field.robots[1].locked

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