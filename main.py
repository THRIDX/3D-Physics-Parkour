from ursina import *
from ursina.prefabs.first_person_controller import FirstPersonController

# --- Game Constants ---
GRAVITY = 9.8
PUSH_FORCE = 5.0 
PLAYER_DEATH_Y = -10
BOX_DEATH_Y = -5
BULLET_SPEED = 60
ROCKET_JUMP_FORCE = 6 # 火箭跳的推力

# --- App Initialization ---
app = Ursina()

# --- Scene Setup ---
window.color = color.rgb(20, 20, 30)
window.title = '3D Physics Parkour'
window.borderless = False
sky = Sky()

ground = Entity(
    model='plane',
    scale=(100, 1, 100),
    color=color.lime * 0.7,
    texture='white_cube',
    texture_scale=(100, 100),
    collider='box'
)

# --- Level Generation (Fixed Layout) ---
platforms = [
    Entity(model='cube', color=color.gray, texture='white_cube', texture_scale=(5, 5), position=(0, 3, 6), scale=(6, 0.8, 6), collider='box'),
    Entity(model='cube', color=color.gray, texture='white_cube', texture_scale=(5, 5), position=(4, 6, 11), scale=(6, 0.8, 6), collider='box'),
    Entity(model='cube', color=color.gray, texture='white_cube', texture_scale=(5, 5), position=(0, 9, 16), scale=(6, 0.8, 6), collider='box')
]

# --- Goal Implementation ---
highest_platform = platforms[-1]
goal = Entity(
    model='cylinder',
    color=color.rgba(0, 255, 0, 128),
    position=highest_platform.position + Vec3(0, highest_platform.scale_y / 2 + 1, 0),
    scale=(2, 2, 2),
    collider='box'
)

# --- Spawner, Button, and Pushable Object Logic ---

class Pushable(Entity):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.model = 'cube'
        self.color = color.orange
        self.collider = 'box'
        self.is_pushable = True
        self.spawner = None
        self.velocity = Vec3(0,0,0)
        self.friction = 4.0

    def update(self):
        hit_info = raycast(self.world_position, direction=(0, -1, 0), distance=self.scale_y / 2 + 0.1, ignore=[self,])

        if not hit_info.hit:
            self.velocity.y -= GRAVITY * time.dt
        else:
            self.velocity.y = max(0, self.velocity.y)
            self.velocity.xz *= (1 - self.friction * time.dt)

        self.position += self.velocity * time.dt

        if self.y < BOX_DEATH_Y:
            if self.spawner:
                self.spawner.box = None
            destroy(self)

class Spawner:
    def __init__(self, position):
        self.position = position
        self.box = None
        self._create_console()
        self.spawn_box()

    def _create_console(self):
        console_base = Entity(model='cube', position=self.position + Vec3(2.5, -0.4, 0), scale=(1.5, 0.2, 1.5), color=color.dark_gray)
        button = Entity(parent=console_base, model='cylinder', position=(0, 0.5, 0), scale=(0.8, 1, 0.8), color=color.azure, collider='box')
        button.is_button = True
        button.spawner = self
        button.on_mouse_enter = Func(setattr, button, 'color', color.cyan)
        button.on_mouse_exit = Func(setattr, button, 'color', color.azure)

    def spawn_box(self):
        if not self.box or not self.box.enabled:
            # 在生成新方块前，销毁可能存在的旧方块
            if self.box:
                destroy(self.box)
            self.box = Pushable(position=self.position, scale=1.5)
            self.box.spawner = self
            Audio('coin_sound', pitch=random.uniform(0.8, 1.2), volume=0.5)

# --- Create Spawners for Ground and Platforms ---
spawn_points = [Vec3(5, 0.75, 5)]
for p in platforms:
    spawn_points.append(p.position + Vec3(0, p.scale_y / 2 + 0.75, 0))
spawners = [Spawner(pos) for pos in spawn_points]


# --- Player Implementation ---
player = FirstPersonController(position=(0, 1, 0), speed=8, gravity=1, health=3, start_position = (0, 1, 0), jump_height=2)
player.game_won = False

# --- UI ---
health_text = Text(text=f"Health: {player.health}", position=(-0.5, 0.4), origin=(0,0), scale=2, background=True)

# --- Gun and Bullet Implementation ---
gun = Entity(parent=camera)
gun_body = Entity(parent=gun, model='cube', position=(0.4, -0.25, 1.25), scale=(0.3, 0.2, 0.8), color=color.dark_gray)
gun_barrel = Entity(parent=gun, model='cube', position=(0.4, -0.2, 1.65), scale=(0.1, 0.15, 0.8), color=color.black)
muzzle_flash = Entity(model='quad', parent=gun, position=gun_barrel.position + Vec3(0,0,gun_barrel.scale_z/2), scale=0.4, color=color.yellow, enabled=False)

# --- Win Screen Implementation ---
win_panel = Entity(parent=camera.ui, model='quad', scale=(1, 0.5), color=color.rgba(0,0,0,180), enabled=False)
win_text = Text(parent=win_panel, text="YOU WIN!", origin=(0,0), scale=5, color=color.green, y=0.1)
restart_text = Text(parent=win_panel, text="Click to Restart", origin=(0,0), scale=2, y=-0.1)

class Bullet(Entity):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.model = 'sphere'
        self.color = color.yellow
        self.scale = 0.2
        destroy(self, delay=2)

    def update(self):
        ray = raycast(self.world_position, self.forward, distance=time.dt * BULLET_SPEED, ignore=[self, player])
        if ray.hit:
            hit_entity = ray.entity
            if hasattr(hit_entity, 'is_pushable'):
                push_direction = self.forward
                push_direction.y = 0
                push_direction.normalize()
                hit_entity.velocity += push_direction * PUSH_FORCE
            destroy(self)
        else:
            self.position += self.forward * time.dt * BULLET_SPEED

def input(key):
    # 修复：当游戏胜利时，点击鼠标左键应触发重玩
    if player.game_won and key == 'left mouse down':
        restart_game()
        return

    if player.health <= 0 or player.game_won: return

    if key == 'left mouse down':
        if mouse.hovered_entity and hasattr(mouse.hovered_entity, 'is_button'):
            mouse.hovered_entity.spawner.spawn_box()
            return
        
        Bullet(
            position=player.camera_pivot.world_position + player.camera_pivot.forward * 0.5,
            rotation=player.camera_pivot.world_rotation
        )
        muzzle_flash.enabled = True
        invoke(setattr, muzzle_flash, 'enabled', False, delay=0.05)
        Audio('saw_sound', pitch=2, volume=0.1)

    # 新增：“火箭跳”功能
    if key == 'right mouse down':
        # 向正下方发射射线
        hit_info = raycast(player.position, direction=(0, -1, 0), distance=1.5, ignore=[player,])
        if hit_info.hit:
            player.velocity = Vec3(0, ROCKET_JUMP_FORCE, 0) # 直接给玩家一个向上的速度
            muzzle_flash.enabled = True # 借用枪口火焰作为特效
            invoke(setattr, muzzle_flash, 'enabled', False, delay=0.05)
            Audio('jump_sound', volume=0.5)

# --- Game Logic (Update Loop) ---
def update():
    if player.game_won: return

    goal.rotation_y += time.dt * 50

    if player.y < PLAYER_DEATH_Y:
        player.health -= 1
        health_text.text = f"Health: {player.health}"
        player.position = player.start_position
        if player.health <= 0:
            Text("GAME OVER", origin=(0,0), scale=4, color=color.red, background=True)
            player.speed = 0

    if player.intersects(goal).hit:
        player.game_won = True
        win_panel.enabled = True # 显示胜利面板

# --- Restart Game Function ---
def restart_game():
    player.position = player.start_position
    player.health = 3
    player.game_won = False
    health_text.text = f"Health: {player.health}"
    win_panel.enabled = False
    
    # 重置所有方块
    for spawner in spawners:
        spawner.spawn_box()


# --- App Execution ---
app.run()

